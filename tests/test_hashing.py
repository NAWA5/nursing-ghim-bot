import main


def test_question_signature_normalization():
    assert main.question_signature("What is your name?") == main.question_signature("what is your name??")


def test_dedupe_rows():
    sig = main.question_signature("duplicate question")
    rows = [
        ["t", "2025-01-01", "1", "u", "duplicate question", "No", ""],
        ["t", "2025-01-01", "2", "u2", "duplicate question!!", "No", ""],
        ["t", "2025-01-01", "3", "u3", "unique question", "No", ""],
    ]
    deduped = main.dedupe_rows(rows, {sig})
    assert len(deduped) == 1
    assert deduped[0][4] == "unique question"
    assert deduped[0][-1] == main.question_signature("unique question")
