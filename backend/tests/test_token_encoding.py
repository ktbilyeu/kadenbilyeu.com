"""Session revocation must reject alternate encodings of the same signature."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from unittest.mock import Mock

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from auth import create_access_token, create_refresh_token, verify_token, verify_refresh_token
from config import ACCESS_TOKEN_SECRET, JWT_AUDIENCE, JWT_ISSUER
from database import BlacklistedTokenModel, get_db, func_add_token_to_blacklist
from main import app
from routes.auth import _get_verified_expiry


def variants(token):
    header, payload, signature = token.split(".")
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    # HS256's last sextet has two unused bits. Flipping one preserves bytes.
    alias = signature[:-1] + alphabet[alphabet.index(signature[-1]) | 1]
    assert base64.urlsafe_b64decode(alias + "=") == base64.urlsafe_b64decode(signature + "=")
    return [token + "!!!!", token + "=", f"{header}.{payload}.{alias}"]


@pytest.mark.parametrize("factory,verify", [
    (create_access_token, verify_token),
    (create_refresh_token, verify_refresh_token),
])
def test_token_encoding_has_only_one_accepted_representation(factory, verify):
    token = factory({"sub": "admin"})
    assert verify(token).username == "admin"
    for alternate in variants(token):
        with pytest.raises(HTTPException) as error:
            verify(alternate)
        assert error.value.status_code == 401


def test_logout_rejects_original_and_alternate_access_tokens():
    token = create_access_token({"sub": "admin"})
    with TestClient(app) as client:
        client.cookies.set("access_token", token)
        assert client.get("/auth/check").json()["authenticated"] is True
        assert client.post("/logout").status_code == 200
        for replay in [token, *variants(token)]:
            client.cookies.set("access_token", replay)
            assert client.get("/auth/check").json()["authenticated"] is False
            assert client.post("/blog", json={"title": "Revocation test", "content": "Test", "author": "admin"}).status_code == 401


def test_refresh_rotation_rejects_replays_and_issues_a_distinct_token():
    token = create_refresh_token({"sub": "admin"})
    with TestClient(app) as client:
        client.cookies.set("refresh_token", token)
        response = client.post("/refresh")
        assert response.status_code == 200
        replacement = response.cookies["refresh_token"]
        assert replacement != token
        for replay in [token, *variants(token)]:
            client.cookies.clear()
            client.cookies.set("refresh_token", replay)
            assert client.post("/refresh").status_code == 401
        client.cookies.clear()
        client.cookies.set("refresh_token", replacement)
        assert client.post("/refresh").status_code == 200


def test_terminal_rejects_revoked_and_alternate_tokens():
    token = create_access_token({"sub": "admin"})
    db = next(get_db())
    try:
        func_add_token_to_blacklist(db, token, datetime.now(timezone.utc) + timedelta(hours=1))
    finally:
        db.close()
    with TestClient(app) as client:
        for replay in [token, *variants(token)]:
            client.cookies.set("access_token", replay)
            with pytest.raises(WebSocketDisconnect) as error:
                with client.websocket_connect("/admin/terminal/ws", headers={"origin": "https://kadenbilyeu.com"}):
                    pass
            assert error.value.code == 1008


def test_legacy_canonical_token_without_jti_remains_valid():
    token = jwt.encode({
        "sub": "admin", "token_type": "access", "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE, "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }, ACCESS_TOKEN_SECRET, algorithm="HS256")
    assert verify_token(token).username == "admin"


def test_logout_can_revoke_expired_canonical_token_but_not_an_alias():
    token = create_access_token({"sub": "admin"}, timedelta(seconds=-1))
    assert _get_verified_expiry(token, ACCESS_TOKEN_SECRET, "access") < datetime.now(timezone.utc)
    for alternate in variants(token):
        with pytest.raises(jwt.InvalidTokenError):
            _get_verified_expiry(alternate, ACCESS_TOKEN_SECRET, "access")


@pytest.mark.parametrize("claim,value", [("iss", "wrong"), ("aud", "wrong"), ("token_type", "refresh")])
def test_claim_validation_stays_enforced(claim, value):
    payload = {"sub": "admin", "token_type": "access", "iss": JWT_ISSUER,
               "aud": JWT_AUDIENCE, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    payload[claim] = value
    token = jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        verify_token(token)
    assert error.value.status_code == 401


def test_concurrent_refresh_consumption_has_exactly_one_winner(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent-revocation.db'}")
    BlacklistedTokenModel.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    ready = Barrier(2)
    token = create_refresh_token({"sub": "admin"})
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    def consume():
        with sessions() as db:
            ready.wait(timeout=5)
            return func_add_token_to_blacklist(db, token, expires_at)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: consume(), range(2)))
        assert sorted(results) == [False, True]
        with sessions() as db:
            assert db.query(BlacklistedTokenModel).count() == 1
    finally:
        engine.dispose()


def test_refresh_rejects_token_consumed_by_another_request(monkeypatch):
    import routes.auth as auth_routes

    monkeypatch.setattr(auth_routes, "is_token_blacklisted", lambda token: False)
    monkeypatch.setattr(auth_routes, "func_add_token_to_blacklist", lambda *args: False)
    with TestClient(app) as client:
        client.cookies.set("refresh_token", create_refresh_token({"sub": "admin"}))
        response = client.post("/refresh")
    assert response.status_code == 401
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("endpoint,cookie,factory", [
    ("/refresh", "refresh_token", create_refresh_token),
    ("/logout", "access_token", create_access_token),
    ("/logout", "refresh_token", create_refresh_token),
])
def test_revocation_storage_failure_cannot_report_success(monkeypatch, endpoint, cookie, factory):
    import routes.auth as auth_routes

    def unavailable(*args):
        raise OperationalError("INSERT", {}, RuntimeError("database unavailable"))

    monkeypatch.setattr(auth_routes, "func_add_token_to_blacklist", unavailable)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.set(cookie, factory({"sub": "admin"}))
        response = client.post(endpoint)
    assert response.status_code == 500
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("error", [
    OperationalError("INSERT", {}, RuntimeError("database unavailable")),
    IntegrityError("INSERT", {}, RuntimeError("unrelated constraint failure")),
])
def test_blacklist_storage_errors_propagate_and_roll_back(error):
    db = Mock()
    db.commit.side_effect = error
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(type(error)):
        func_add_token_to_blacklist(db, "token", datetime.now(timezone.utc))
    db.rollback.assert_called_once()
