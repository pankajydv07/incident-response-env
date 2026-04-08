"""Client for the incident response environment."""

from __future__ import annotations

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from .models import IncidentAction, IncidentObservation, IncidentState


class IncidentResponseEnv(
    EnvClient[IncidentAction, IncidentObservation, IncidentState]
):
    """WebSocket client for the incident response environment."""

    def _step_payload(self, action: IncidentAction) -> Dict[str, Any]:
        return action.model_dump(mode="json")

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[IncidentObservation]:
        obs_data = payload.get("observation", {})
        observation = IncidentObservation(
            alert_summary=obs_data.get("alert_summary", ""),
            log_snippet=obs_data.get("log_snippet", ""),
            metrics_snapshot=obs_data.get("metrics_snapshot", {}),
            runbook_hint=obs_data.get("runbook_hint"),
            phase=obs_data.get("phase", "triage"),
            feedback=obs_data.get("feedback", ""),
            done=payload.get("done", obs_data.get("done", False)),
            reward=payload.get("reward", obs_data.get("reward")),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> IncidentState:
        return IncidentState(**payload)
