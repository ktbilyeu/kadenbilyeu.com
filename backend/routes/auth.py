## Copyright 2024 Kaden Bilyeu (ktbilyeu) (https://github.com/ktbilyeu) (https://github.com/ktbilyeu/kadenbilyeu.com) (https://kadenbilyeu.com)
## Use of this source code is governed by an GNU Affero General Public License v3.0
## license that can be found in the LICENSE file.

import jwt

from fastapi import APIRouter, Request, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config import ADMIN_USER, limiter, SECURE_COOKIES
from auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_refresh_token,
    decode_session_token,
    is_token_blacklisted
)
from database import get_db, func_add_token_to_blacklist

router = APIRouter()


def _get_verified_expiry(token:str, secret:str, expected_type:str):
    """Verify a token while allowing logout to revoke a just-expired credential."""
    import jwt
    from datetime import datetime, timezone
    payload = decode_session_token(token, secret, verify_exp=False)
    if(payload.get("token_type") != expected_type or payload.get("sub") != ADMIN_USER):
        raise jwt.InvalidTokenError("Unexpected token claims")

    return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)


@router.get("/auth/check")
async def check_auth(request: Request, access_token: str = Cookie(None, alias="access_token")):
    """
    Check if the current user is authenticated

    Args:
    request (Request): The request object
    access_token (str): The access token from cookie

    Returns:
    dict: Authentication status
    """
    if not access_token:
        return {"authenticated": False}

    if is_token_blacklisted(access_token):
        return {"authenticated": False}

    try:
        token_data = verify_token(access_token)
        if token_data.username != ADMIN_USER:
            return {"authenticated": False}
        return {"authenticated": True, "user": token_data.username}
    except:
        return {"authenticated": False}


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    access_token: str = Cookie(None, alias="access_token"),
    refresh_token: str = Cookie(None, alias="refresh_token"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Logout endpoint - clears authentication cookies and blacklists tokens

    Args:
    request (Request): The request object
    access_token (str): The access token to blacklist
    refresh_token (str): The refresh token to blacklist
    db (Session): Database session

    Returns:
    JSONResponse: Success message with cleared cookies
    """
    from config import ACCESS_TOKEN_SECRET, REFRESH_TOKEN_SECRET

    if access_token:
        try:
            exp = _get_verified_expiry(access_token, ACCESS_TOKEN_SECRET, "access")
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
            pass
        else:
            func_add_token_to_blacklist(db, access_token, exp)

    if refresh_token:
        try:
            exp = _get_verified_expiry(refresh_token, REFRESH_TOKEN_SECRET, "refresh")
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
            pass
        else:
            func_add_token_to_blacklist(db, refresh_token, exp)

    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="Lax"
    )
    response.delete_cookie(
        key="refresh_token",
        path="/",
        secure=SECURE_COOKIES,
        httponly=True,
        samesite="Lax"
    )
    return response

@router.post("/refresh")
@limiter.limit("60/minute")
async def refresh_token(
    request: Request,
    refresh_token: str = Cookie(None, alias="refresh_token"),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """
    Refresh the access token using the refresh token

    Args:
    request (Request): The request object
    refresh_token (str): The refresh token from cookie
    db (Session): Database session

    Returns:
    JSONResponse: Success message with new tokens set as HttpOnly cookies
    """
    from config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES
    from datetime import timedelta

    if(refresh_token is None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No refresh token provided")

    if is_token_blacklisted(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    token_data = verify_refresh_token(refresh_token)
    if token_data.username != ADMIN_USER:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if not func_add_token_to_blacklist(db, refresh_token, token_data.expires_at):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": token_data.username}, expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    new_refresh_token = create_refresh_token(
        data={"sub": token_data.username}, expires_delta=refresh_token_expires
    )

    response = JSONResponse(content={"message": "Token refreshed", "token_type": "bearer"})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="Lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="Lax",
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60
    )
    return response
