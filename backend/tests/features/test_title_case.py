from backend.sessions.services.auto_title import title_case


def test_words_are_capitalized_but_small_joiners_stay_lower():
    assert (
        title_case("median best paid jobs in the world")
        == "Median Best Paid Jobs in the World"
    )
    assert title_case("random wikipedia article") == "Random Wikipedia Article"


def test_urls_paths_and_identifiers_stay_as_written():
    assert (
        title_case("http://127.0.0.1:3000/?s=S0EF0V024M")
        == "http://127.0.0.1:3000/?s=S0EF0V024M"
    )
    assert title_case("fix src/app_main.py") == "fix src/app_main.py"
    assert title_case("use iPhone 16 Pro") == "Use iPhone 16 Pro"
