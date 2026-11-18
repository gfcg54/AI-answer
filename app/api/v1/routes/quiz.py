from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session, get_quiz_service
from app.db_models import LearningRecord, UserRecord
from app.models.common import ApiResponse
from app.models.quiz import QuizGenerateRequest, QuizResponse
from app.services.quiz_service import QuizService


router = APIRouter()


@router.post(
    "/quiz/generate",
    response_model=ApiResponse[QuizResponse],
)
async def generate_quiz(
    request: QuizGenerateRequest,
    service: Annotated[QuizService, Depends(get_quiz_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ApiResponse[QuizResponse]:
    user_id = user.id
    await session.rollback()
    quiz = await service.generate(request.user_input)
    session.add(
        LearningRecord(
            quiz_id=quiz.quiz_id,
            user_id=user_id,
            topic=quiz.user_input,
            quiz_data=quiz.model_dump(mode="json"),
            total_count=len(quiz.questions),
        )
    )
    await session.commit()
    return ApiResponse(data=quiz)
