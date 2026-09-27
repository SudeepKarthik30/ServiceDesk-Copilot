import pytest

from ai.decide import decide
from tickets.models import AIDecision, Category, Team, Urgency

TOP5 = [{"id": 1, "score": 0.9}, {"id": 2, "score": 0.6}]
GOOD_ANSWER = {
    "can_solve": True,
    "confidence": "high",
    "steps": [{"text": "Restart the VPN client.", "source": "1"}],
}


@pytest.fixture
def safe_category(db):
    team = Team.objects.create(name="Networking")
    return Category.objects.create(name="VPN Access", team=team, safe_to_auto_solve=True)


@pytest.fixture
def unsafe_category(db):
    team = Team.objects.create(name="Networking")
    return Category.objects.create(name="Network Outage", team=team, safe_to_auto_solve=False)


def decide_with(**overrides):
    kwargs = dict(
        ai_error=None,
        top5=TOP5,
        answer=GOOD_ANSWER,
        category=None,
        urgency=Urgency.P3,
        threshold=0.5,
    )
    kwargs.update(overrides)
    return decide(**kwargs)


def test_ai_error_always_escalates(safe_category):
    decision, reasons = decide_with(ai_error="timeout", category=safe_category)
    assert decision == AIDecision.ESCALATE
    assert "ai_error: timeout" in reasons


def test_no_candidates_escalates(safe_category):
    decision, _ = decide_with(top5=[], category=safe_category)
    assert decision == AIDecision.ESCALATE


def test_cannot_solve_escalates(safe_category):
    decision, _ = decide_with(answer={"can_solve": False, "confidence": "high", "steps": []}, category=safe_category)
    assert decision == AIDecision.ESCALATE


def test_low_confidence_escalates(safe_category):
    answer = {**GOOD_ANSWER, "confidence": "medium"}
    decision, _ = decide_with(answer=answer, category=safe_category)
    assert decision == AIDecision.ESCALATE


def test_score_below_threshold_escalates(safe_category):
    decision, _ = decide_with(top5=[{"id": 1, "score": 0.2}], category=safe_category)
    assert decision == AIDecision.ESCALATE


def test_uncited_step_escalates(safe_category):
    answer = {**GOOD_ANSWER, "steps": [{"text": "Do X.", "source": "999"}]}
    decision, _ = decide_with(answer=answer, category=safe_category)
    assert decision == AIDecision.ESCALATE


def test_unsafe_category_escalates(unsafe_category):
    decision, _ = decide_with(category=unsafe_category)
    assert decision == AIDecision.ESCALATE


def test_missing_category_escalates():
    decision, _ = decide_with(category=None)
    assert decision == AIDecision.ESCALATE


def test_p1_urgency_escalates(safe_category):
    decision, _ = decide_with(category=safe_category, urgency=Urgency.P1)
    assert decision == AIDecision.ESCALATE


def test_all_checks_pass_auto_answers(safe_category):
    decision, reasons = decide_with(category=safe_category)
    assert decision == AIDecision.AUTO_ANSWER
    assert reasons == ["all_checks_passed"]
