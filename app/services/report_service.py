from langchain_core.exceptions import OutputParserException
from pydantic import ValidationError

from app.core.content_filter import ensure_content_allowed
from app.core.exceptions import ReportGenerationError
from app.llm.report_chain import LangChainReportGenerator
from app.models.report import (
    ReportContent,
    ReportGenerateRequest,
    ReportResponse,
)
from app.services.scoring_service import calculate_score


class ReportService:
    def __init__(self, generator: LangChainReportGenerator) -> None:
        self._generator = generator

    async def generate(self, request: ReportGenerateRequest) -> ReportResponse:
        ensure_content_allowed(request.topic)
        score = calculate_score(request.questions, request.answer_records)
        last_error: ValidationError | OutputParserException | None = None

        for _ in range(2):
            try:
                generated = await self._generator.generate(
                    topic=request.topic,
                    questions=request.questions,
                    answer_records=request.answer_records,
                    score=score,
                )
                content = ReportContent.model_validate(generated)
                ensure_content_allowed(content.model_dump_json())
                return ReportResponse(
                    accuracy=score.accuracy,
                    correct_count=score.correct_count,
                    total_count=score.total_count,
                    xp_earned=score.xp_earned,
                    **content.model_dump(),
                )
            except (ValidationError, OutputParserException) as error:
                last_error = error

        raise ReportGenerationError() from last_error
