## Copyright 2024 Kaden Bilyeu (ktbilyeu) (https://github.com/ktbilyeu) (https://kadenbilyeu.com)
## Use of this source code is governed by an GNU Affero General Public License v3.0
## license that can be found in the LICENSE file.

import os
import re
from urllib.parse import urlsplit


DEFAULT_ALLOWED_ADMIN_ORIGINS = {
    "https://kadenbilyeu.com",
    "http://localhost:5173",
}


def normalized_origin(origin: str) -> str | None:
    try:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            return None
        if parsed.query or parsed.fragment:
            return None

        host = parsed.hostname.lower()
        port = parsed.port
        if (parsed.scheme == "https" and port in {None, 443}) or (
            parsed.scheme == "http" and port in {None, 80}
        ):
            return f"{parsed.scheme}://{host}"
        return f"{parsed.scheme}://{host}:{port}"
    except ValueError:
        return None


def configured_origins(env_variable: str, defaults: set[str]) -> list[str]:
    """Read exact origins from private runtime configuration; reject malformed entries."""
    configured = os.getenv(env_variable)
    values = configured.split(",") if configured is not None else defaults
    return list(dict.fromkeys(
        normalized
        for value in values
        if (normalized := normalized_origin(value.strip())) is not None
    ))


def cors_preview_origin_regex() -> str | None:
    """Opt in to explicit Cloudflare project previews without arbitrary regex input."""
    domains = {
        value.strip().lower()
        for value in os.getenv("CORS_PREVIEW_DOMAINS", "").split(",")
        if re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.pages\.dev", value.strip().lower())
    }
    if not domains:
        return None
    alternatives = "|".join(re.escape(domain) for domain in sorted(domains))
    return rf"^https://[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.(?:{alternatives})$"


def is_admin_origin_allowed(origin: str, env_variable: str) -> bool:
    allowed = configured_origins(env_variable, DEFAULT_ALLOWED_ADMIN_ORIGINS)
    normalized = normalized_origin(origin)
    return normalized is not None and normalized in allowed
