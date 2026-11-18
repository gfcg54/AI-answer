from app.models.quiz import AnswerRecord, Question
from app.services.scoring_service import calculate_score


def test_score_compares_answer_sets_and_ignores_client_correctness(quiz_payload):
    questions = [Question.model_validate(item) for item in quiz_payload["questions"]]
    records = [
        AnswerRecord(question_id="q1", selected_answers=["A"], is_correct=False),
        AnswerRecord(
            question_id="q4",
            selected_answers=["D", "A", "B"],
            is_correct=False,
        ),
    ]

    score = calculate_score(questions, records)

    assert score.correct_count == 2
    assert score.total_count == 5
    assert score.accuracy == 40
    assert score.xp_earned == 16


def test_incomplete_or_extra_selections_do_not_receive_xp(quiz_payload):
    questions = [Question.model_validate(item) for item in quiz_payload["questions"]]
    records = [
        AnswerRecord(question_id="q4", selected_answers=["A", "B"]),
        AnswerRecord(question_id="q1", selected_answers=["A", "B"]),
    ]

    score = calculate_score(questions, records)

    assert score.correct_count == 0
    assert score.xp_earned == 0
