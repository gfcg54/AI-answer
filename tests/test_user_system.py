import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_quiz_service,
    get_report_service,
)
from app.main import app
from app.services.quiz_service import QuizService
from app.services.report_service import ReportService


class FakeQuizGenerator:
    def __init__(self, quiz_payload):
        self.quiz_payload = quiz_payload
        self.calls = 0

    async def generate(self, user_input):
        self.calls += 1
        return self.quiz_payload


class FakeReportGenerator:
    def __init__(self):
        self.calls = 0

    async def generate(self, topic, questions, answer_records, score):
        self.calls += 1
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
def user_client(mysql_client, quiz_payload):
    quiz_generator = FakeQuizGenerator(quiz_payload)
    report_generator = FakeReportGenerator()
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(
        quiz_generator
    )
    app.dependency_overrides[get_report_service] = lambda: ReportService(
        report_generator
    )

    mysql_client.quiz_generator = quiz_generator
    mysql_client.report_generator = report_generator
    yield mysql_client


def login(client: TestClient, code: str = "first-user"):
    response = client.post(
        "/api/v1/auth/wechat-login",
        json={"code": code},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_login_creates_account_and_reuses_it_for_same_wechat_identity(user_client):
    first = login(user_client)
    second = login(user_client)

    assert first["user"]["id"] == second["user"]["id"]
    assert first["access_token"] != second["access_token"]
    assert first["user"]["nickname"]
    assert first["user"]["avatar_url"] == ""


def test_invalid_wechat_code_is_reported_without_creating_a_session(user_client):
    response = user_client.post(
        "/api/v1/auth/wechat-login",
        json={"code": "invalid-code"},
    )

    assert response.status_code == 401
    assert response.json()["data"] is None


def test_profile_update_logout_and_account_deletion_are_authenticated(user_client):
    auth = login(user_client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    updated = user_client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"nickname": "问道学友", "avatar_url": "https://example.com/a.png"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["nickname"] == "问道学友"
    assert updated.json()["data"]["avatar_url"] == "https://example.com/a.png"

    logged_out = user_client.post("/api/v1/auth/logout", headers=headers)
    assert logged_out.status_code == 200
    stale_session = user_client.get("/api/v1/users/me", headers=headers)
    assert stale_session.status_code == 401

    second_auth = login(user_client)
    second_headers = {
        "Authorization": f"Bearer {second_auth['access_token']}"
    }
    deleted = user_client.delete("/api/v1/users/me", headers=second_headers)
    assert deleted.status_code == 200

    deleted_user = user_client.get(
        "/api/v1/users/me",
        headers=second_headers,
    )
    assert deleted_user.status_code == 401


def test_learning_requires_authentication(user_client):
    response = user_client.post(
        "/api/v1/quiz/generate",
        json={"user_input": "雾是如何形成的"},
    )

    assert response.status_code == 401
    assert user_client.quiz_generator.calls == 0


def test_completed_quiz_persists_history_xp_and_is_idempotent(
    user_client,
    quiz_payload,
):
    auth = login(user_client)
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    quiz_response = user_client.post(
        "/api/v1/quiz/generate",
        headers=headers,
        json={"user_input": "为什么夜晚山间容易出现雾？"},
    )
    assert quiz_response.status_code == 200
    quiz_id = quiz_response.json()["data"]["quiz_id"]

    answer_records = [
        {
            "question_id": question["id"],
            "selected_answers": question["answer"],
            "is_correct": False,
            "duration_ms": 1000,
        }
        for question in quiz_payload["questions"]
    ]
    report_payload = {
        "quiz_id": quiz_id,
        "answer_records": answer_records,
    }

    report = user_client.post(
        "/api/v1/report/generate",
        headers=headers,
        json=report_payload,
    )
    repeated_report = user_client.post(
        "/api/v1/report/generate",
        headers=headers,
        json=report_payload,
    )

    assert report.status_code == 200
    assert report.json()["data"]["accuracy"] == 100
    assert report.json()["data"]["xp_earned"] == 40
    assert repeated_report.json()["data"] == report.json()["data"]
    assert user_client.report_generator.calls == 1

    summary = user_client.get("/api/v1/users/me/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["data"]["total_xp"] == 40
    assert summary.json()["data"]["completed_quizzes"] == 1

    history = user_client.get("/api/v1/users/me/history", headers=headers)
    assert history.status_code == 200
    assert len(history.json()["data"]["items"]) == 1
    assert history.json()["data"]["items"][0]["quiz_id"] == quiz_id

    analytics = user_client.get(
        "/api/v1/users/me/analytics?days=7",
        headers=headers,
    )
    assert analytics.status_code == 200
    daily = analytics.json()["data"]["daily"]
    assert len(daily) == 7
    assert sum(day["question_count"] for day in daily) == 5

    deleted = user_client.delete("/api/v1/users/me", headers=headers)
    assert deleted.status_code == 200
    deleted_history = user_client.get(
        "/api/v1/users/me/history",
        headers=headers,
    )
    assert deleted_history.status_code == 401


def test_learning_records_are_isolated_between_users(user_client, quiz_payload):
    first_auth = login(user_client, "first")
    second_auth = login(user_client, "second")
    first_headers = {"Authorization": f"Bearer {first_auth['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second_auth['access_token']}"}
    quiz = user_client.post(
        "/api/v1/quiz/generate",
        headers=first_headers,
        json={"user_input": "雾的形成"},
    ).json()["data"]

    response = user_client.post(
        "/api/v1/report/generate",
        headers=second_headers,
        json={
            "quiz_id": quiz["quiz_id"],
            "answer_records": [
                {
                    "question_id": question["id"],
                    "selected_answers": question["answer"],
                    "duration_ms": 1000,
                }
                for question in quiz_payload["questions"]
            ],
        },
    )

    assert response.status_code == 404


def test_missing_bearer_token_is_rejected(user_client):
    response = user_client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["data"] is None
