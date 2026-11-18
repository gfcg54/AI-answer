import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    bearer_scheme,
    get_current_user,
    get_db_session,
    get_wechat_client,
    hash_access_token,
)
from app.core.config import get_settings
from app.core.exceptions import WechatConfigurationError
from app.database import utcnow
from app.db_models import LoginSessionRecord, UserRecord
from app.models.common import ApiResponse
from app.models.user import AuthResponse, UserProfile, WechatLoginRequest
from app.services.wechat_service import WechatClient


router = APIRouter()


def _hash_openid(openid: str) -> str:
    secret = get_settings().wechat_openid_hash_secret
    if secret is None:
        raise WechatConfigurationError()
    return hmac.new(
        secret.get_secret_value().encode("utf-8"),
        openid.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _user_profile(user: UserRecord) -> UserProfile:
    return UserProfile(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


@router.post(
    "/auth/wechat-login",
    response_model=ApiResponse[AuthResponse],
)
async def wechat_login(
    request: WechatLoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    wechat: Annotated[WechatClient, Depends(get_wechat_client)],
) -> ApiResponse[AuthResponse]:
    openid = await wechat.exchange_code(request.code)
    openid_hash = _hash_openid(openid)
    user = await session.scalar(
        select(UserRecord).where(UserRecord.wechat_openid_hash == openid_hash)
    )

    if user is None:
        user = UserRecord(wechat_openid_hash=openid_hash)
        session.add(user)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            user = await session.scalar(
                select(UserRecord).where(
                    UserRecord.wechat_openid_hash == openid_hash
                )
            )
            if user is None:
                raise

    now = utcnow()
    access_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(days=get_settings().auth_token_ttl_days)
    session.add(
        LoginSessionRecord(
            user_id=user.id,
            token_hash=hash_access_token(access_token),
            expires_at=expires_at,
        )
    )
    await session.commit()

    return ApiResponse(
        data=AuthResponse(
            access_token=access_token,
            expires_at=expires_at,
            user=_user_profile(user),
        )
    )


@router.post("/auth/logout", response_model=ApiResponse[None])
async def logout(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[None]:
    if credentials is not None:
        await session.execute(
            delete(LoginSessionRecord).where(
                LoginSessionRecord.user_id == user.id,
                LoginSessionRecord.token_hash
                == hash_access_token(credentials.credentials),
            )
        )
        await session.commit()
    return ApiResponse(data=None)
