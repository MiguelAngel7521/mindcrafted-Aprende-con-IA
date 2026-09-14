import pytest


@pytest.mark.parametrize(
    "forbidden",
    [
        "multiple_choice",
        "true_false",
        "plain_quiz",
        "question_answer"
    ]
)
def test_main_puzzles_are_not_quizzes(world_spec, forbidden):

    mandatory = [
        puzzle
        for puzzle in world_spec["puzzles"]
        if puzzle.get("mandatory", False)
    ]

    for puzzle in mandatory:
        assert puzzle["archetype"] != forbidden
