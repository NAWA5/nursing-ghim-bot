import main


def test_categorize_question_matches_keywords():
    cats = main.categorize_question("A pediatric dose question about a drug")
    assert "pediatrics" in cats
    assert "pharmacology" in cats

