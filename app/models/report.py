from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.quiz import AnswerRecord, Question


class ScoreSummary(BaseModel):
    correct_count: int = Field(ge=0)
    total_count: int = Field(gt=0)
    accuracy: int = Field(ge=0, le=100)
    xp_earned: int = Field(ge=0)


class ReportGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_id: str = Field(min_length=1, max_length=80)
    topic: str = Field(min_length=1, max_length=160)
    questions: list[Question] = Field(min_length=5, max_length=5)
    answer_records: list[AnswerRecord] = Field(min_length=5, max_length=5)

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请输入学习主题")
        return normalized

    @model_validator(mode="after")
    def validate_answer_records(self) -> "ReportGenerateRequest":
        question_ids = [question.id for question in self.questions]
        record_ids = [record.question_id for record in self.answer_records]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("题目编号不能重复")
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("每道题只能提交一条作答记录")
        if set(question_ids) != set(record_ids):
            raise ValueError("必须为每道题提供一条作答记录")

        options_by_question = {
            question.id: {option.key for option in question.options}
            for question in self.questions
        }
        for record in self.answer_records:
            if not set(record.selected_answers).issubset(
                options_by_question[record.question_id]
            ):
                raise ValueError("作答记录包含不存在的选项")
        return self


class ReportSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiz_id: str = Field(min_length=1, max_length=80)
    answer_records: list[AnswerRecord] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_unique_answer_records(self) -> "ReportSubmissionRequest":
        question_ids = [record.question_id for record in self.answer_records]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("每道题只能提交一条作答记录")
        return self


class ReportContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mastered_points: list[str] = Field(max_length=8)
    weak_points: list[str] = Field(max_length=8)
    three_line_summary: list[str] = Field(min_length=3, max_length=3)
    advice: list[str] = Field(min_length=1, max_length=5)
    share_quote: str = Field(min_length=1, max_length=120)


class ReportResponse(ReportContent):
    accuracy: int = Field(ge=0, le=100)
    correct_count: int = Field(ge=0)
    total_count: int = Field(gt=0)
    xp_earned: int = Field(ge=0)
