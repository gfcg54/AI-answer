from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session, get_report_service
from app.core.exceptions import AppError, UserNotFoundError
from app.database import utcnow
from app.db_models import LearningRecord, UserRecord
from app.models.common import ApiResponse
from app.models.quiz import QuizResponse
from app.models.report import (
    ReportGenerateRequest,
    ReportResponse,
    ReportSubmissionRequest,
)
from app.services.report_service import ReportService


router = APIRouter()


@router.post(
    "/report/generate",
    response_model=ApiResponse[ReportResponse],
)
async def generate_report(
    request: ReportSubmissionRequest,
    service: Annotated[ReportService, Depends(get_report_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ApiResponse[ReportResponse]:
    user_id = user.id
    record = await session.scalar(
        select(LearningRecord).where(
            LearningRecord.quiz_id == request.quiz_id,
            LearningRecord.user_id == user_id,
        )
    )
    if record is None:
        raise UserNotFoundError()
    if record.completed_at is not None and record.report_data is not None:
        return ApiResponse(data=ReportResponse.model_validate(record.report_data))

    quiz = QuizResponse.model_validate(record.quiz_data)
    answer_ids = {answer.question_id for answer in request.answer_records}
    question_ids = {question.id for question in quiz.questions}
    if answer_ids != question_ids:
        raise AppError(422, 4000, "必须为每道题提供一条作答记录。")

    options_by_question = {
        question.id: {option.key for option in question.options}
        for question in quiz.questions
    }
    for answer in request.answer_records:
        if not set(answer.selected_answers).issubset(
            options_by_question[answer.question_id]
        ):
            raise AppError(422, 4000, "作答记录包含不存在的选项。")

    report_request = ReportGenerateRequest(
        quiz_id=request.quiz_id,
        topic=quiz.user_input,
        questions=quiz.questions,
        answer_records=request.answer_records,
    )
    await session.rollback()
    report = await service.generate(report_request)
    question_by_id = {question.id: question for question in quiz.questions}
    stored_answers = []
    for answer in request.answer_records:
        question = question_by_id[answer.question_id]
        is_correct = set(question.answer) == set(answer.selected_answers)
        stored_answers.append(
            answer.model_copy(update={"is_correct": is_correct}).model_dump(
                mode="json"
            )
        )

    locked_record = await session.scalar(
        select(LearningRecord)
        .where(
            LearningRecord.quiz_id == request.quiz_id,
            LearningRecord.user_id == user_id,
        )
        .with_for_update()
    )
    if locked_record is None:
        raise UserNotFoundError()
    if (
        locked_record.completed_at is not None
        and locked_record.report_data is not None
    ):
        return ApiResponse(
            data=ReportResponse.model_validate(locked_record.report_data)
        )

    locked_record.answer_records = stored_answers
    locked_record.report_data = report.model_dump(mode="json")
    locked_record.correct_count = report.correct_count
    locked_record.total_count = report.total_count
    locked_record.accuracy = report.accuracy
    locked_record.xp_earned = report.xp_earned
    locked_record.duration_ms = sum(
        answer.duration_ms for answer in request.answer_records
    )
    locked_record.completed_at = utcnow()
    await session.commit()
    return ApiResponse(data=report)
