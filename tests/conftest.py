import asyncio
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def quiz_payload():
    return {
        "title": "山间雾气",
        "summary": "了解雾的形成条件。",
        "questions": [
            {
                "id": "q1",
                "type": "single",
                "stem": "雾是什么？",
                "options": [
                    {"key": "A", "text": "近地面的小水滴"},
                    {"key": "B", "text": "地底蒸汽"},
                    {"key": "C", "text": "灰尘"},
                    {"key": "D", "text": "冰块"},
                ],
                "answer": ["A"],
                "explanation": "雾由悬浮在近地面的微小水滴组成。",
                "knowledge_point": "雾的定义",
                "difficulty": "easy",
            },
            {
                "id": "q2",
                "type": "single",
                "stem": "雾形成时空气通常会怎样？",
                "options": [
                    {"key": "A", "text": "升温"},
                    {"key": "B", "text": "冷却"},
                    {"key": "C", "text": "消失"},
                    {"key": "D", "text": "变成固体"},
                ],
                "answer": ["B"],
                "explanation": "空气冷却到露点后，水汽容易凝结。",
                "knowledge_point": "露点",
                "difficulty": "easy",
            },
            {
                "id": "q3",
                "type": "single",
                "stem": "雾通常出现在哪里？",
                "options": [
                    {"key": "A", "text": "近地面"},
                    {"key": "B", "text": "地核"},
                    {"key": "C", "text": "太空"},
                    {"key": "D", "text": "深海底部"},
                ],
                "answer": ["A"],
                "explanation": "雾是贴近地面的云。",
                "knowledge_point": "雾的位置",
                "difficulty": "easy",
            },
            {
                "id": "q4",
                "type": "multiple",
                "stem": "雾形成需要哪些条件？",
                "options": [
                    {"key": "A", "text": "空气含有水汽"},
                    {"key": "B", "text": "空气冷却到露点"},
                    {"key": "C", "text": "空气完全干燥"},
                    {"key": "D", "text": "水汽发生凝结"},
                ],
                "answer": ["A", "B", "D"],
                "explanation": "水汽、冷却和凝结共同促成雾。",
                "knowledge_point": "雾的形成条件",
                "difficulty": "medium",
            },
            {
                "id": "q5",
                "type": "judge",
                "stem": "雾中的小水滴悬浮在近地面。",
                "options": [
                    {"key": "A", "text": "正确"},
                    {"key": "B", "text": "错误"},
                ],
                "answer": ["A"],
                "explanation": "雾由近地面悬浮的小水滴组成。",
                "knowledge_point": "雾的组成",
                "difficulty": "easy",
            },
        ],
    }


@pytest.fixture
def report_payload(quiz_payload):
    return {
        "quiz_id": "quiz_test",
        "topic": "山间雾气",
        "questions": quiz_payload["questions"],
        "answer_records": [
            {
                "question_id": "q1",
                "selected_answers": ["A"],
                "is_correct": False,
                "duration_ms": 1000,
            },
            {
                "question_id": "q2",
                "selected_answers": ["B"],
                "is_correct": False,
                "duration_ms": 1000,
            },
            {
                "question_id": "q3",
                "selected_answers": ["A"],
                "is_correct": False,
                "duration_ms": 1000,
            },
            {
                "question_id": "q4",
                "selected_answers": ["A", "B", "D"],
                "is_correct": False,
                "duration_ms": 1000,
            },
            {
                "question_id": "q5",
                "selected_answers": ["B"],
                "is_correct": True,
                "duration_ms": 1000,
            },
        ],
    }


class TestWechatClient:
    async def exchange_code(self, code: str) -> str:
        if code.startswith("invalid"):
            from app.core.exceptions import WechatLoginError

            raise WechatLoginError()
        return f"test-openid-{code}"


class TestQuizGenerator:
    def __init__(self, quiz_payload):
        self.quiz_payload = quiz_payload
        self.calls = 0

    async def generate(self, user_input):
        self.calls += 1
        return self.quiz_payload


class TestReportGenerator:
    async def generate(self, topic, questions, answer_records, score):
        return {
            "mastered_points": ["雾的定义"],
            "weak_points": ["辐射雾的条件"],
            "three_line_summary": [
                "雾是近地面的云。",
                "空气冷却后水汽凝结。",
                "露点是关键条件。",
            ],
            "advice": ["复习露点与凝结的关系。"],
            "share_quote": "一步步弄懂，知识就会留下。",
        }


@pytest.fixture
def mysql_client(quiz_payload, monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("设置 TEST_DATABASE_URL 后运行 MySQL 集成测试")

    monkeypatch.setenv("WECHAT_OPENID_HASH_SECRET", "test-openid-hash-secret")
    from app.api.dependencies import (
        get_db_session,
        get_quiz_service,
        get_report_service,
        get_wechat_client,
    )
    from app.core.config import get_settings
    from app.database import Base
    from app.main import app
    from app.services.quiz_service import QuizService
    from app.services.report_service import ReportService

    get_settings.cache_clear()
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare_database())

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_wechat_client] = lambda: TestWechatClient()
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(
        TestQuizGenerator(quiz_payload)
    )
    app.dependency_overrides[get_report_service] = lambda: ReportService(
        TestReportGenerator()
    )

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
        get_settings.cache_clear()


@pytest.fixture
def login_headers():
    def _login(client, code="default-user"):
        response = client.post(
            "/api/v1/auth/wechat-login",
            json={"code": code},
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login
