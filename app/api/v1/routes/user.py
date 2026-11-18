from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    get_db_session,
)
from app.core.content_filter import ensure_content_allowed
from app.database import utcnow
from app.db_models import LearningRecord, UserRecord
from app.models.common import ApiResponse
from app.models.user import (
    DailyLearningStat,
    LearningAnalytics,
    LearningHistory,
    LearningHistoryItem,
    LearningSummary,
    UserProfile,
    UserProfileUpdateRequest,
)


router = APIRouter()


def _profile(user: UserRecord) -> UserProfile:
    return UserProfile(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


def _weak_points(records: list[LearningRecord]) -> list[str]:
    incorrect_counts: Counter[str] = Counter()
    for record in records:
        questions = {
            question["id"]: question
            for question in record.quiz_data["questions"]
        }
        for answer in record.answer_records or []:
            if answer["is_correct"]:
                continue
            question = questions.get(answer["question_id"])
            if question is not None:
                incorrect_counts[question["knowledge_point"]] += 1
    return [
        point
        for point, _ in sorted(
            incorrect_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:3]
    ]


@router.get(
    "/users/me",
    response_model=ApiResponse[UserProfile],
)
async def get_profile(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> ApiResponse[UserProfile]:
    return ApiResponse(data=_profile(user))


@router.patch(
    "/users/me",
    response_model=ApiResponse[UserProfile],
)
async def update_profile(
    request: UserProfileUpdateRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[UserProfile]:
    if request.nickname is not None:
        ensure_content_allowed(request.nickname)
        user.nickname = request.nickname
    if request.avatar_url is not None:
        user.avatar_url = request.avatar_url
    user.updated_at = utcnow()
    await session.commit()
    await session.refresh(user)
    return ApiResponse(data=_profile(user))


@router.delete("/users/me", response_model=ApiResponse[None])
async def delete_account(
    user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[None]:
    await session.delete(user)
    await session.commit()
    return ApiResponse(data=None)


@router.get(
    "/users/me/summary",
    response_model=ApiResponse[LearningSummary],
)
async def get_learning_summary(
    user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApiResponse[LearningSummary]:
    records = list(
        (
            await session.scalars(
                select(LearningRecord).where(
                    LearningRecord.user_id == user.id,
                    LearningRecord.completed_at.is_not(None),
                )
            )
        ).all()
    )
    recent_cutoff = utcnow() - timedelta(days=30)
    recent_records = [
        record for record in records if record.completed_at >= recent_cutoff
    ]
    count = len(records)
    summary = LearningSummary(
        total_xp=sum(record.xp_earned for record in records),
        completed_quizzes=count,
        average_accuracy=(
            round(sum(record.accuracy for record in records) / count)
            if count
            else 0
        ),
        study_minutes=round(
            sum(record.duration_ms for record in records) / 60000
        ),
        weak_points=_weak_points(recent_records),
    )
    return ApiResponse(data=summary)


@router.get(
    "/users/me/history",
    response_model=ApiResponse[LearningHistory],
)
async def get_learning_history(
    user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[LearningHistory]:
    records = (
        await session.scalars(
            select(LearningRecord)
            .where(
                LearningRecord.user_id == user.id,
                LearningRecord.completed_at.is_not(None),
            )
            .order_by(LearningRecord.completed_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return ApiResponse(
        data=LearningHistory(
            items=[
                LearningHistoryItem(
                    quiz_id=record.quiz_id,
                    topic=record.topic,
                    title=record.quiz_data["title"],
                    accuracy=record.accuracy,
                    correct_count=record.correct_count,
                    total_count=record.total_count,
                    xp_earned=record.xp_earned,
                    completed_at=record.completed_at,
                )
                for record in records
            ]
        )
    )


@router.get(
    "/users/me/analytics",
    response_model=ApiResponse[LearningAnalytics],
)
async def get_learning_analytics(
    user: Annotated[UserRecord, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> ApiResponse[LearningAnalytics]:
    now = utcnow()
    first_day = now.date() - timedelta(days=days - 1)
    records = list(
        (
            await session.scalars(
                select(LearningRecord).where(
                    LearningRecord.user_id == user.id,
                    LearningRecord.completed_at
                    >= datetime.combine(first_day, datetime.min.time()),
                )
            )
        ).all()
    )

    question_counts: defaultdict[date, int] = defaultdict(int)
    correct_counts: defaultdict[date, int] = defaultdict(int)
    quiz_counts: defaultdict[date, int] = defaultdict(int)
    durations_ms: defaultdict[date, int] = defaultdict(int)
    for record in records:
        if record.completed_at is None:
            continue
        record_date = record.completed_at.date()
        question_counts[record_date] += record.total_count
        correct_counts[record_date] += record.correct_count
        quiz_counts[record_date] += 1
        durations_ms[record_date] += record.duration_ms

    daily = []
    for day_offset in range(days):
        learning_date = first_day + timedelta(days=day_offset)
        question_count = question_counts[learning_date]
        correct_count = correct_counts[learning_date]
        daily.append(
            DailyLearningStat(
                date=learning_date.isoformat(),
                question_count=question_count,
                correct_count=correct_count,
                completed_quizzes=quiz_counts[learning_date],
                study_minutes=round(durations_ms[learning_date] / 60000),
                accuracy=(
                    round(correct_count * 100 / question_count)
                    if question_count
                    else 0
                ),
            )
        )

    return ApiResponse(
        data=LearningAnalytics(
            days=days,
            daily=daily,
            weak_points=_weak_points(records),
        )
    )
