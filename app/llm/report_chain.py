import json

from langchain_core.prompts import ChatPromptTemplate
from openai import APIError

from app.core.exceptions import ReportGenerationError
from app.llm.langchain_factory import create_chat_model
from app.models.report import ReportContent, ScoreSummary
from app.models.quiz import AnswerRecord, Question
from app.prompts.report_prompt import REPORT_SYSTEM_PROMPT, REPORT_USER_PROMPT


def create_report_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", REPORT_SYSTEM_PROMPT),
            ("human", REPORT_USER_PROMPT),
        ]
    )
    structured_model = create_chat_model(temperature=0.5).with_structured_output(
        ReportContent,
        method="json_mode",
    )
    return prompt | structured_model


class LangChainReportGenerator:
    def __init__(self, chain=None) -> None:
        self._chain = chain

    async def generate(
        self,
        topic: str,
        questions: list[Question],
        answer_records: list[AnswerRecord],
        score: ScoreSummary,
    ) -> ReportContent:
        chain = self._chain if self._chain is not None else create_report_chain()
        try:
            return await chain.ainvoke(
                {
                    "topic": topic,
                    "quiz_json": json.dumps(
                        [
                            question.model_dump(mode="json")
                            for question in questions
                        ],
                        ensure_ascii=False,
                    ),
                    "answer_records_json": json.dumps(
                        [
                            {
                                "question_id": record.question_id,
                                "selected_answers": record.selected_answers,
                                "duration_ms": record.duration_ms,
                            }
                            for record in answer_records
                        ],
                        ensure_ascii=False,
                    ),
                    "score_json": json.dumps(
                        score.model_dump(mode="json"),
                        ensure_ascii=False,
                    ),
                    "schema_json": json.dumps(
                        ReportContent.model_json_schema(),
                        ensure_ascii=False,
                    ),
                }
            )
        except APIError as error:
            raise ReportGenerationError() from error
