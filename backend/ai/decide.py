"""Pure decision function - no DB/network calls, so it's cheap to unit-test and to re-tune
RERANK_THRESHOLD against in the Phase 7 evaluation."""

from tickets.models import AIDecision, Urgency


def decide(*, ai_error, top5, answer, category, urgency, threshold):
    """Auto-answer only if every one of these holds, otherwise escalate. See CLAUDE.md "How
    triage works" step 6 for the spec this implements."""
    if ai_error:
        return AIDecision.ESCALATE, [f"ai_error: {ai_error}"]

    if not top5:
        return AIDecision.ESCALATE, ["no_candidates"]

    if not answer or not answer.get("can_solve"):
        return AIDecision.ESCALATE, ["cannot_solve"]

    if answer.get("confidence") != "high":
        return AIDecision.ESCALATE, [f"confidence_not_high:{answer.get('confidence')}"]

    top_score = top5[0]["score"]
    if top_score < threshold:
        return AIDecision.ESCALATE, [f"rerank_score_below_threshold:{top_score:.3f}<{threshold}"]

    steps = answer.get("steps") or []
    if not steps:
        return AIDecision.ESCALATE, ["no_steps"]

    valid_sources = {str(c["id"]) for c in top5}
    for step in steps:
        if str(step.get("source")) not in valid_sources:
            return AIDecision.ESCALATE, [f"uncited_step_source:{step.get('source')}"]

    if category is None or not category.safe_to_auto_solve:
        return AIDecision.ESCALATE, ["category_not_safe_to_auto_solve"]

    if urgency == Urgency.P1:
        return AIDecision.ESCALATE, ["urgency_p1"]

    return AIDecision.AUTO_ANSWER, ["all_checks_passed"]
