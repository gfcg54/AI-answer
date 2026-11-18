from app.models.quiz import AnswerRecord, Question
from app.models.report import ScoreSummary


XP_PER_CORRECT_ANSWER = 8


def calculate_score(
    questions: list[Question],
    answer_records: list[AnswerRecord],
) -> ScoreSummary:
    answers_by_id = {
        record.question_id: set(record.selected_answers)
        for record in answer_records
    }
    correct_count = sum(
        set(question.answer) == answers_by_id.get(question.id, set())
        for question in questions
    )
    total_count = len(questions)
    accuracy = round(correct_count * 100 / total_count) if total_count else 0

    return ScoreSummary(
        correct_count=correct_count,
        total_count=total_count,
        accuracy=accuracy,
        xp_earned=correct_count * XP_PER_CORRECT_ANSWER,
    )
