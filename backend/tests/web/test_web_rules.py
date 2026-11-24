import pytest
from backend.governance.services.rules import RuleContext, decide_rules, parse_rule
from dot_contracts.permissions import Decision

CTX = RuleContext(workspace="/w", home="/home/u")


def verdict(rule: str, decision: Decision, url: str, tool: str = "WebFetch"):
    hit = decide_rules([parse_rule(decision, rule)], tool, {"url": url}, CTX)
    return hit.decision if hit else None


@pytest.mark.parametrize(
    ("url", "matches"),
    [
        ("https://example.com/a", True),
        ("https://www.example.com/a", True),
        ("https://EXAMPLE.com/", True),
        ("https://example.com./", True),  # trailing dot
        ("  https://example.com/x", True),  # padded url
        ("https://example.com:8443/", True),
        ("https://user@example.com/", True),
        ("https://good.com@example.com/", True),  # real host is after @
        ("https://example.com@good.com/", False),
        ("https://notexample.com/", False),
        ("https://example.com.evil.net/", False),
        ("https://evil.net/?u=example.com", False),
    ],
)
def test_domain_specifier(url: str, matches: bool):
    assert (
        verdict("WebFetch(domain:example.com)", Decision.DENY, url) is not None
    ) is matches


def test_domain_rules_cover_ask_and_other_tools():
    assert (
        verdict("WebFetch(domain:example.com)", Decision.ASK, "https://a.example.com/")
        == Decision.ASK
    )
    rule = "BrowserNavigate(domain:example.com)"
    assert (
        verdict(rule, Decision.DENY, "https://example.com/", "BrowserNavigate")
        == Decision.DENY
    )


def test_deny_beats_allow_for_a_domain():
    rules = [
        parse_rule(Decision.ALLOW, "WebFetch(domain:example.com)"),
        parse_rule(Decision.DENY, "WebFetch(domain:evil.example.com)"),
    ]
    hit = decide_rules(rules, "WebFetch", {"url": "https://evil.example.com/"}, CTX)
    assert hit is not None
    assert hit.decision == Decision.DENY
    assert hit.rule == "WebFetch(domain:evil.example.com)"
