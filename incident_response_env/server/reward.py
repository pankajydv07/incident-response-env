"""Dense step reward logic."""

from __future__ import annotations

from incident_response_env.models import IncidentAction, IncidentState


def compute_step_reward(
    action: IncidentAction,
    prev_state: IncidentState,
    new_state: IncidentState,
    *,
    is_relevant_service: bool,
    is_correct_next_step: bool,
    is_redundant: bool,
) -> float:
    reward = 0.0

    if action.action_type == "check_logs" and is_relevant_service:
        reward += 0.10

    if new_state.phase != prev_state.phase:
        reward += 0.15

    if action.action_type == "execute_runbook_step":
        reward += 0.20 if is_correct_next_step else -0.10

    if is_redundant:
        reward -= 0.05

    if action.action_type == "escalate" and new_state.severity == "P3":
        reward -= 0.15

    if action.action_type == "resolve" and new_state.resolved:
        reward += 0.30

    return reward
