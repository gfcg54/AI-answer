import hashlib
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationRequiredError
from app.database import get_db_session, utcnow
from app.db_models import LoginSessionRecord, UserRecord
from app.llm.quiz_chain import LangChainQuizGenerator, create_quiz_chain
from app.llm.report_chain import LangChainReportGenerator, create_report_chain
from app.services.quiz_service import QuizService
from app.services.report_service import ReportService
from app.services.wechat_service import WechatClient


bearer_scheme = HTTPBearer(auto_error=False)


def get_quiz_service() -> QuizService:
    return QuizService(LangChainQuizGenerator(create_quiz_chain()))


def get_report_service() -> ReportService:
    return ReportService(LangChainReportGenerator(create_report_chain()))


def get_wechat_client() -> WechatClient:
    return WechatClient()


def hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationRequiredError()

    result = await session.execute(
        select(LoginSessionRecord, UserRecord)
        .join(UserRecord, UserRecord.id == LoginSessionRecord.user_id)
        .where(
            LoginSessionRecord.token_hash == hash_access_token(
                credentials.credentials
            ),
            LoginSessionRecord.expires_at > utcnow(),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise AuthenticationRequiredError()
    return row[1]
