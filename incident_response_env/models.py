"""Pydantic models for the incident response environment."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


ActionType = Literal[
    "check_logs",
    "check_metrics",
    "acknowledge_alert",
    "execute_runbook_step",
    "check_deploy_history",
    "escalate",
    "write_postmortem",
    "resolve",
]

IncidentPhase = Literal["triage", "diagnosis", "resolution", "postmortem", "resolved"]


class IncidentAction(Action):
    """Action taken by the agent during an incident."""

    action_type: ActionType = Field(..., description="The action being executed")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action parameters such as service name, runbook id, or postmortem text",
    )


class IncidentObservation(Observation):
    """Observation returned after reset or step."""

    alert_summary: str = Field(default="", description="Current active alert summary")
    log_snippet: str = Field(default="", description="Most relevant log lines")
    metrics_snapshot: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current metrics snapshot for the incident",
    )
    runbook_hint: Optional[str] = Field(
        default=None,
        description="Hint about likely remediation when the agent is on track",
    )
    phase: IncidentPhase = Field(default="triage", description="Current workflow phase")
    feedback: str = Field(default="", description="Feedback on the previous action")


class IncidentState(State):
    """Internal environment state tracked across the episode."""

    task_id: str = Field(default="", description="Current scenario id")
    severity: str = Field(default="P2", description="Incident severity")
    phase: IncidentPhase = Field(default="triage", description="Current workflow phase")
    acknowledged_alert: bool = Field(default=False)
    correct_runbook_found: bool = Field(default=False)
    selected_runbook: Optional[str] = Field(default=None)
    root_cause_identified: Optional[str] = Field(default=None)
    services_checked: List[str] = Field(default_factory=list)
    metrics_checked: bool = Field(default=False)
    deploy_history_checked: bool = Field(default=False)
    steps_executed: List[str] = Field(default_factory=list)
    redundant_actions: int = Field(default=0)
    postmortem_written: bool = Field(default=False)
    postmortem_text: str = Field(default="")
    dirty_rows_repaired: bool = Field(default=False)
    resolved: bool = Field(default=False)
    metrics_after_fix: Dict[str, Any] = Field(default_factory=dict)
