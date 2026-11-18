from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuizQuestionType(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    JUDGE = "judge"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1, max_length=160)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    type: QuizQuestionType
    stem: str = Field(min_length=1, max_length=500)
    options: list[QuestionOption] = Field(min_length=2, max_length=4)
    answer: list[Literal["A", "B", "C", "D"]] = Field(
        min_length=1,
        max_length=4,
    )
    explanation: str = Field(min_length=1, max_length=1200)
    knowledge_point: str = Field(min_length=1, max_length=120)
    difficulty: Difficulty

    @model_validator(mode="after")
    def validate_answer_shape(self) -> "Question":
        option_keys = [option.key for option in self.options]
        if len(set(option_keys)) != len(option_keys):
            raise ValueError("选项编号不能重复")
        if len(set(self.answer)) != len(self.answer):
            raise ValueError("正确答案不能重复")
        if not set(self.answer).issubset(option_keys):
            raise ValueError("正确答案必须对应已有选项")

        if self.type == QuizQuestionType.SINGLE:
            if len(self.options) != 4 or len(self.answer) != 1:
                raise ValueError("单选题必须有 4 个选项和 1 个正确答案")
        elif self.type == QuizQuestionType.MULTIPLE:
            if len(self.options) != 4 or len(self.answer) < 2:
                raise ValueError("多选题必须有 4 个选项和至少 2 个正确答案")
        elif self.type == QuizQuestionType.JUDGE:
            if len(self.options) != 2 or len(self.answer) != 1:
                raise ValueError("判断题必须有 2 个选项和 1 个正确答案")
        return self


class QuizContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=300)
    questions: list[Question] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_quiz_format(self) -> "QuizContent":
        ids = [question.id for question in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("题目编号不能重复")
        types = [question.type for question in self.questions]
        expected = [
            QuizQuestionType.SINGLE,
            QuizQuestionType.SINGLE,
            QuizQuestionType.SINGLE,
            QuizQuestionType.MULTIPLE,
            QuizQuestionType.JUDGE,
        ]
        if sorted(types, key=lambda item: item.value) != sorted(
            expected,
            key=lambda item: item.value,
        ):
            raise ValueError("题库必须包含 3 道单选、1 道多选和 1 道判断题")
        return self


class QuizGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_input: str = Field(min_length=1, max_length=160)

    @field_validator("user_input")
    @classmethod
    def normalize_user_input(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("请输入想学习的主题")
        return normalized


class QuizResponse(BaseModel):
    quiz_id: str
    title: str
    summary: str
    source_type: Literal["text"] = "text"
    user_input: str
    questions: list[Question]


class AnswerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str = Field(min_length=1, max_length=40)
    selected_answers: list[Literal["A", "B", "C", "D"]] = Field(
        default_factory=list,
        max_length=4,
    )
    is_correct: bool | None = None
    duration_ms: int = Field(default=0, ge=0)

    @field_validator("selected_answers")
    @classmethod
    def unique_selected_answers(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("所选答案不能重复")
        return value
