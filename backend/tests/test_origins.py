import re

from origins import configured_origins, cors_preview_origin_regex, is_admin_origin_allowed


def test_defaults_accept_only_canonical_and_local_admin_origins(monkeypatch):
    monkeypatch.delenv("TERMINAL_ALLOWED_ORIGINS", raising=False)
    assert is_admin_origin_allowed("https://kadenbilyeu.com", "TERMINAL_ALLOWED_ORIGINS")
    assert is_admin_origin_allowed("http://localhost:5173", "TERMINAL_ALLOWED_ORIGINS")
    for origin in ("https://status.kadenbilyeu.com", "https://kadenbilyeu.com.evil.test",
                   "https://kadenbilyeu.com@evil.test", "https://kadenbilyeu.com/path"):
        assert not is_admin_origin_allowed(origin, "TERMINAL_ALLOWED_ORIGINS")


def test_private_origin_override_is_exact_and_empty_denies(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://kadenbilyeu.com,https://legacy.example,https://bad.example/path,https://user@bad.example")
    assert configured_origins("CORS_ALLOWED_ORIGINS", {"https://kadenbilyeu.com"}) == [
        "https://kadenbilyeu.com", "https://legacy.example",
    ]
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    assert configured_origins("CORS_ALLOWED_ORIGINS", {"https://kadenbilyeu.com"}) == []


def test_previews_require_explicit_project_and_reject_confusable_hosts(monkeypatch):
    monkeypatch.delenv("CORS_PREVIEW_DOMAINS", raising=False)
    assert cors_preview_origin_regex() is None
    monkeypatch.setenv("CORS_PREVIEW_DOMAINS", "example.pages.dev,.*.pages.dev,pages.dev,https://other.pages.dev")
    pattern = cors_preview_origin_regex()
    assert re.fullmatch(pattern, "https://branch-123.example.pages.dev")
    for origin in ("https://branch.other.pages.dev", "https://example.pages.dev.evil.test",
                   "https://branch.example.pages.dev.evil.test", "http://branch.example.pages.dev",
                   "https://a.b.example.pages.dev", "https://branch.example.pages.dev/path"):
        assert not re.fullmatch(pattern, origin)


def test_cors_middleware_only_credentials_explicit_runtime_origins(monkeypatch):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://kadenbilyeu.com,https://legacy.example")
    monkeypatch.setenv("CORS_PREVIEW_DOMAINS", "example.pages.dev")
    app = FastAPI()
    app.add_middleware(CORSMiddleware,
                       allow_origins=configured_origins("CORS_ALLOWED_ORIGINS", set()),
                       allow_origin_regex=cors_preview_origin_regex(),
                       allow_credentials=True, allow_methods=["GET"])
    client = TestClient(app)
    for origin, allowed in (
        ("https://kadenbilyeu.com", True),
        ("https://legacy.example", True),
        ("https://branch.example.pages.dev", True),
        ("https://legacy.example.evil.test", False),
        ("https://status.kadenbilyeu.com", False),
        ("https://branch.other.pages.dev", False),
    ):
        response = client.options("/", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
