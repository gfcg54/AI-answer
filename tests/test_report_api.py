from app.main import app
from app.api.dependencies import get_report_service
from app.services.report_service import ReportService


class FakeReportGenerator:
    def __init__(self):
        self.received_score = None

    async def generate(self, topic, questions, answer_records, score):
        self.received_score = score
        return {
            "mastered_points": ["雾的定义"],
            "weak_points": ["辐射雾的条件"],
            "three_line_summary": ["雾是近地面的云。", "空气冷却后水汽凝结。", "露点是关键条件。"],
            "advice": ["复习露点与凝结的关系。"],
            "share_quote": "一步步弄懂，知识就会留下。",
        }


def _create_quiz(client, headers):
    response = client.post(
        "/api/v1/quiz/generate",
        headers=headers,
        json={"user_input": "山间雾气"},
    )
    assert response.status_code == 200
    return response.json()["data"]["quiz_id"]


def test_report_uses_server_calculated_score_and_returns_summary(
    mysql_client,
    login_headers,
    report_payload,
):
    generator = FakeReportGenerator()
    app.dependency_overrides[get_report_service] = lambda: ReportService(generator)
    headers = login_headers(mysql_client)
    quiz_id = _create_quiz(mysql_client, headers)
    payload = {
        "quiz_id": quiz_id,
        "answer_records": report_payload["answer_records"],
    }

    try:
        response = mysql_client.post(
            "/api/v1/report/generate",
            headers=headers,
            json=payload,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["accuracy"] == 80
    assert body["data"]["correct_count"] == 4
    assert body["data"]["total_count"] == 5
    assert body["data"]["xp_earned"] == 32
    assert generator.received_score.correct_count == 4
    assert generator.received_score.xp_earned == 32
    assert body["data"]["share_quote"]


def test_report_requires_a_record_for_every_question(
    mysql_client,
    login_headers,
    report_payload,
):
    generator = FakeReportGenerator()
    app.dependency_overrides[get_report_service] = lambda: ReportService(generator)
    headers = login_headers(mysql_client)
    quiz_id = _create_quiz(mysql_client, headers)
    payload = {
        "quiz_id": quiz_id,
        "answer_records": report_payload["answer_records"][:-1],
    }

    try:
        response = mysql_client.post(
            "/api/v1/report/generate",
            headers=headers,
            json=payload,
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == 4000
    assert generator.received_score is None
