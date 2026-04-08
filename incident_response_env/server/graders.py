"""Deterministic graders for the three benchmark tasks."""

from __future__ import annotations

from incident_response_env.models import IncidentState

MIN_SCORE = 0.0001
MAX_SCORE = 0.9999


def _bounded_score(score: float) -> float:
    """Keep task scores strictly inside the open interval (0, 1)."""

    return min(max(score, MIN_SCORE), MAX_SCORE)


def grade_task1(state: IncidentState) -> float:
    score = 0.0
    if "auth-service" in state.services_checked:
        score += 0.25
    if state.metrics_checked:
        score += 0.15
    if state.acknowledged_alert:
        score += 0.20
    if state.selected_runbook == "RB-017":
        score += 0.30
    if state.step_count > 0 and state.step_count <= 6 and state.selected_runbook == "RB-017":
        score += 0.10
    return _bounded_score(score)


def grade_task2(state: IncidentState) -> float:
    score = 0.0
    checked = set(state.services_checked)
    if "api-gateway" in checked:
        score += 0.15
    if "db-replica" in checked:
        score += 0.20
    if state.root_cause_identified == "db-replica-lag":
        score += 0.25
    if "kill-query-RB-042" in state.steps_executed:
        score += 0.20
    if state.metrics_after_fix.get("error_rate", 1.0) < 0.05:
        score += 0.15
    if state.step_count > 0 and state.step_count <= 12 and "kill-query-RB-042" in state.steps_executed:
        score += 0.05
    return _bounded_score(score)


def grade_task3(state: IncidentState) -> float:
    score = 0.0
    checked = set(state.services_checked)
    if state.acknowledged_alert:
        score += 0.10
    if "payments-service" in checked:
        score += 0.10
    if state.deploy_history_checked:
        score += 0.10
    if state.root_cause_identified == "orm-migration-missing-constraint":
        score += 0.20

    required = [
        "rollback-deploy",
        "apply-constraint",
        "repair-dirty-rows",
        "restart-payments",
        "verify-integrity",
    ]
    positions = [state.steps_executed.index(step) for step in required if step in state.steps_executed]
    if len(positions) == len(required) and positions == sorted(positions):
        score += 0.20
    if state.dirty_rows_repaired:
        score += 0.10

    postmortem = state.postmortem_text.lower()
    for section in ("timeline", "impact", "root cause", "action items"):
        if section in postmortem:
            score += 0.05
    return _bounded_score(score)
