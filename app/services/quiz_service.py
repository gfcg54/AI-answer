from uuid import uuid4

from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from app.core.content_filter import ensure_content_allowed
from app.core.exceptions import QuizGenerationError
from app.llm.quiz_chain import LangChainQuizGenerator
from app.models.quiz import QuizContent, QuizResponse


class QuizService:
    def __init__(self, generator: LangChainQuizGenerator) -> None:
        self._generator = generator

    async def generate(self, user_input: str) -> QuizResponse:
        ensure_content_allowed(user_input)
        last_error: ValidationError | OutputParserException | None = None

        for _ in range(2):
            try:
                generated = await self._generator.generate(user_input)
                content = QuizContent.model_validate(generated)
                ensure_content_allowed(content.model_dump_json())
                return QuizResponse(
                    quiz_id=f"quiz_{uuid4().hex}",
                    title=content.title,
                    summary=content.summary,
                    user_input=user_input,
                    questions=content.questions,
                )
            except (ValidationError, OutputParserException) as error:
                last_error = error

        raise QuizGenerationError() from last_error
