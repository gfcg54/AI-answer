from app.main import app
from app.api.dependencies import get_quiz_service
from app.services.quiz_service import QuizService


class FakeQuizGenerator:
    def __init__(self, quiz_payload, error=None):
        self.quiz_payload = quiz_payload
        self.error = error
        self.calls = 0

    async def generate(self, user_input):
        self.calls += 1
        if self.error:
            raise self.error
        return self.quiz_payload


def test_generate_returns_fixed_quiz_in_standard_envelope(
    mysql_client,
    login_headers,
    quiz_payload,
):
    generator = FakeQuizGenerator(quiz_payload)
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(generator)
    headers = login_headers(mysql_client)

    try:
        response = mysql_client.post(
            "/api/v1/quiz/generate",
            headers=headers,
            json={"user_input": "为什么夜晚山间容易出现雾？"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["source_type"] == "text"
    assert len(body["data"]["questions"]) == 5
    assert [question["type"] for question in body["data"]["questions"]].count(
        "single"
    ) == 3
    assert generator.calls == 1


def test_generate_rejects_empty_input_with_standard_error_envelope(
    mysql_client,
    login_headers,
    quiz_payload,
):
    generator = FakeQuizGenerator(quiz_payload)
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(generator)
    headers = login_headers(mysql_client)

    try:
        response = mysql_client.post(
            "/api/v1/quiz/generate",
            headers=headers,
            json={"user_input": "  "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == 4000
    assert generator.calls == 0


def test_generate_blocks_configured_sensitive_terms(
    mysql_client,
    login_headers,
    quiz_payload,
):
    generator = FakeQuizGenerator(quiz_payload)
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(generator)
    headers = login_headers(mysql_client)

    try:
        response = mysql_client.post(
            "/api/v1/quiz/generate",
            headers=headers,
            json={"user_input": "如何自杀"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == 4003
    assert generator.calls == 0


def test_generation_provider_failure_is_reported_as_service_error(
    mysql_client,
    login_headers,
):
    from app.core.exceptions import QuizGenerationError

    generator = FakeQuizGenerator({}, error=QuizGenerationError())
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(generator)
    headers = login_headers(mysql_client)

    try:
        response = mysql_client.post(
            "/api/v1/quiz/generate",
            headers=headers,
            json={"user_input": "雾是如何形成的"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json()["code"] == 5001


def test_health_check_uses_standard_success_envelope():
    from fastapi.testclient import TestClient

    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "ok",
        "data": {"status": "ok"},
    }


def test_missing_deepseek_key_is_reported_without_fake_success(
    mysql_client,
    login_headers,
    monkeypatch,
):
    from app.core.config import Settings
    from app.llm.quiz_chain import LangChainQuizGenerator, create_quiz_chain

    monkeypatch.setattr(
        "app.llm.langchain_factory.get_settings",
        lambda: Settings(deepseek_api_key=""),
    )
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(
        LangChainQuizGenerator(create_quiz_chain())
    )
    headers = login_headers(mysql_client)
    response = mysql_client.post(
        "/api/v1/quiz/generate",
        headers=headers,
        json={"user_input": "雾是如何形成的"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == 5002
    assert response.json()["data"] is None


def test_langchain_chains_build_with_documented_json_mode(monkeypatch):
    from pydantic import SecretStr

    from app.core.config import Settings
    from app.llm.quiz_chain import create_quiz_chain
    from app.llm.report_chain import create_report_chain

    settings = Settings(
        deepseek_api_key=SecretStr("test-key"),
        deepseek_model="deepseek-flash",
    )
    monkeypatch.setattr("app.llm.langchain_factory.get_settings", lambda: settings)

    quiz_chain = create_quiz_chain()
    report_chain = create_report_chain()

    assert quiz_chain.get_input_schema()
    assert report_chain.get_input_schema()


def test_quiz_service_retries_invalid_structured_output(
    mysql_client,
    login_headers,
    quiz_payload,
):
    from app.services.quiz_service import QuizService

    class RetryGenerator:
        def __init__(self):
            self.calls = 0

        async def generate(self, user_input):
            self.calls += 1
            if self.calls == 1:
                return {"title": "不完整", "summary": "缺少题目", "questions": []}
            return quiz_payload

    generator = RetryGenerator()
    headers = login_headers(mysql_client)
    app.dependency_overrides[get_quiz_service] = lambda: QuizService(generator)

    try:
        response = mysql_client.post(
            "/api/v1/quiz/generate",
            headers=headers,
            json={"user_input": "雾是如何形成的"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert generator.calls == 2
