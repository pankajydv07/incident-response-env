"""Incident response environment implementation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment

from incident_response_env.models import IncidentAction, IncidentObservation, IncidentState
from incident_response_env.server.graders import grade_task1, grade_task2, grade_task3
from incident_response_env.server.log_generator import clone_metrics
from incident_response_env.server.reward import compute_step_reward
from incident_response_env.server.runbook_store import RUNBOOK_STORE
from incident_response_env.server.scenarios.task1_easy import SCENARIO as TASK1
from incident_response_env.server.scenarios.task2_medium import SCENARIO as TASK2
from incident_response_env.server.scenarios.task3_hard import SCENARIO as TASK3

SCENARIOS = {
    TASK1["task_id"]: TASK1,
    TASK2["task_id"]: TASK2,
    TASK3["task_id"]: TASK3,
}


class IncidentResponseEnvironment(
    Environment[IncidentAction, IncidentObservation, IncidentState]
):
    """Simulated SRE on-call incident response environment."""

    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self) -> None:
        self._state = IncidentState(episode_id=str(uuid4()))
        self._scenario: Dict[str, Any] = deepcopy(TASK1)
        self._last_log_snippet = ""
        self._last_metrics = clone_metrics(self._scenario["initial_metrics"])
        self._last_feedback = ""

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        **kwargs: Any,
    ) -> IncidentObservation:
        del seed
        task_id = kwargs.get("task_id", TASK1["task_id"])
        if task_id not in SCENARIOS:
            raise ValueError(f"Unknown task_id: {task_id}")

        self._scenario = deepcopy(SCENARIOS[task_id])
        self._state = IncidentState(
            episode_id=episode_id or str(uuid4()),
            task_id=task_id,
            severity=self._scenario["severity"],
            phase=self._scenario["initial_phase"],
        )
        self._last_log_snippet = "No logs fetched yet."
        self._last_metrics = clone_metrics(self._scenario["initial_metrics"])
        self._last_feedback = self._scenario["initial_feedback"]
        return self._make_observation(reward=self._grade_current_task(), done=False)

    def step(
        self,
        action: IncidentAction,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> IncidentObservation:
        del timeout_s, kwargs
        prev_state = self._state.model_copy(deep=True)
        self._state.step_count += 1

        handler = getattr(self, f"_handle_{action.action_type}", None)
        if handler is None:
            self._last_feedback = f"Unsupported action: {action.action_type}"
            return self._make_observation(reward=self._grade_current_task(), done=False)

        is_redundant = self._is_redundant(action)
        if is_redundant:
            self._state.redundant_actions += 1

        is_relevant_service = False
        is_correct_next_step = False
        result = handler(action)
        if isinstance(result, dict):
            is_relevant_service = result.get("is_relevant_service", False)
            is_correct_next_step = result.get("is_correct_next_step", False)

        done = self._state.resolved and (
            self._state.task_id != "postmortem-p1-hard" or self._state.postmortem_written
        )

        if self._state.step_count >= self._scenario["max_steps"] and not done:
            done = True
            self._last_feedback = (
                f"{self._last_feedback} Step budget exhausted before full resolution."
            ).strip()

        # Always use the bounded grader score as the reward.
        # The evaluator interprets observation.reward as the task score,
        # which must be strictly between 0 and 1.
        reward = self._grade_current_task()
        return self._make_observation(reward=reward, done=done)

    @property
    def state(self) -> IncidentState:
        return self._state

    def _make_observation(self, *, reward: float, done: bool) -> IncidentObservation:
        metadata = {
            "task_id": self._state.task_id,
            "severity": self._state.severity,
            "score": self._grade_current_task(),
            "available_runbooks": self._scenario.get("available_runbooks", []),
            "runbook_store": RUNBOOK_STORE,
        }
        return IncidentObservation(
            alert_summary=self._scenario["alert_summary"],
            log_snippet=self._last_log_snippet,
            metrics_snapshot=clone_metrics(self._last_metrics),
            runbook_hint=self._scenario.get("runbook_hint") if self._state.correct_runbook_found else None,
            phase="resolved" if self._state.resolved and done else self._state.phase,
            feedback=self._last_feedback,
            reward=reward,
            done=done,
            metadata=metadata,
        )

    def _handle_check_logs(self, action: IncidentAction) -> Dict[str, bool]:
        service = str(action.parameters.get("service", "")).strip()
        logs = self._scenario.get("service_logs", {})
        if service not in logs:
            self._last_feedback = f"No relevant logs found for service '{service}'."
            self._last_log_snippet = "No new logs."
            return {"is_relevant_service": False}

        self._last_log_snippet = logs[service]
        if service not in self._state.services_checked:
            self._state.services_checked.append(service)

        if self._state.task_id == "alert-triage-easy" and service == "auth-service":
            self._state.root_cause_identified = self._scenario["root_cause"]
            self._state.phase = "diagnosis"
            self._last_feedback = "Auth logs implicate JWT deprecation rather than resource saturation."
        elif self._state.task_id == "multi-service-incident-medium" and service == "db-replica":
            self._state.root_cause_identified = self._scenario["root_cause"]
            self._state.phase = "diagnosis"
            self._last_feedback = "Replica lag is the real bottleneck behind the gateway symptoms."
        elif self._state.task_id == "postmortem-p1-hard" and service == "db-primary":
            self._last_feedback = "Database logs confirm dirty rows after an incomplete rollback."
        else:
            self._last_feedback = f"Checked logs for {service}. Continue correlating evidence."

        return {"is_relevant_service": service in self._scenario.get("recommended_services", [])}

    def _handle_check_metrics(self, action: IncidentAction) -> Dict[str, bool]:
        del action
        self._state.metrics_checked = True
        if self._state.steps_executed:
            self._state.metrics_after_fix = clone_metrics(self._scenario["resolve_metrics"])
            self._last_metrics = clone_metrics(self._scenario["resolve_metrics"])
            self._last_feedback = "Post-fix metrics look healthy."
            if self._state.phase == "resolution":
                self._state.phase = "postmortem" if self._state.task_id == "postmortem-p1-hard" else "resolution"
        else:
            self._last_metrics = clone_metrics(self._scenario["initial_metrics"])
            self._last_feedback = "Metrics confirm the visible symptom; combine with logs before acting."
        return {}

    def _handle_acknowledge_alert(self, action: IncidentAction) -> Dict[str, bool]:
        del action
        self._state.acknowledged_alert = True
        self._last_feedback = "Alert acknowledged. Continue diagnosis."
        return {}

    def _handle_execute_runbook_step(self, action: IncidentAction) -> Dict[str, bool]:
        step_id = str(action.parameters.get("step_id", "")).strip()
        runbook_id = str(action.parameters.get("runbook_id", "")).strip()

        self._state.selected_runbook = runbook_id or self._state.selected_runbook
        if runbook_id == self._scenario["correct_runbook"]:
            self._state.correct_runbook_found = True

        expected_steps = self._expected_steps()
        next_step = expected_steps[len(self._state.steps_executed)] if len(self._state.steps_executed) < len(expected_steps) else None
        is_correct_next_step = step_id == next_step

        if is_correct_next_step:
            self._state.steps_executed.append(step_id)
            self._state.phase = "resolution"
            self._last_feedback = f"Executed runbook step '{step_id}' successfully."
            if step_id == "repair-dirty-rows":
                self._state.dirty_rows_repaired = True
            if self._state.task_id == "multi-service-incident-medium" and step_id == "kill-query-RB-042":
                self._state.root_cause_identified = self._scenario["root_cause"]
            if (
                self._state.task_id == "postmortem-p1-hard"
                and step_id == "verify-integrity"
            ):
                self._state.metrics_after_fix = clone_metrics(self._scenario["resolve_metrics"])
        else:
            self._last_feedback = (
                f"Runbook step '{step_id}' is out of order for this incident."
            )
        return {"is_correct_next_step": is_correct_next_step}

    def _handle_check_deploy_history(self, action: IncidentAction) -> Dict[str, bool]:
        del action
        deploy_history = self._scenario.get("deploy_history")
        self._state.deploy_history_checked = True
        self._last_log_snippet = deploy_history or "No deploy history available for this scenario."
        if self._state.task_id == "postmortem-p1-hard" and deploy_history:
            self._state.root_cause_identified = self._scenario["root_cause"]
            self._state.phase = "diagnosis"
            self._last_feedback = "Deploy history links the incident to the bad ORM migration."
        else:
            self._last_feedback = "Checked deploy history."
        return {}

    def _handle_escalate(self, action: IncidentAction) -> Dict[str, bool]:
        del action
        self._last_feedback = f"Escalation recorded at severity {self._state.severity}."
        return {}

    def _handle_write_postmortem(self, action: IncidentAction) -> Dict[str, bool]:
        text = str(action.parameters.get("text", "")).strip()
        self._state.postmortem_text = text
        self._state.postmortem_written = bool(text)
        self._state.phase = "postmortem"
        self._last_feedback = "Postmortem captured. Resolve once remediation is verified."
        return {}

    def _handle_resolve(self, action: IncidentAction) -> Dict[str, bool]:
        del action
        ready_for_resolution = bool(self._state.steps_executed) and (
            self._state.metrics_after_fix.get("error_rate", 1.0) < 0.05
            or self._state.task_id == "alert-triage-easy"
        )
        if self._state.task_id == "postmortem-p1-hard":
            ready_for_resolution = ready_for_resolution and self._state.postmortem_written
        self._state.resolved = ready_for_resolution
        self._last_feedback = (
            "Incident resolved and verified."
            if ready_for_resolution
            else "Resolution attempt rejected; verification is incomplete."
        )
        return {}

    def _expected_steps(self) -> list[str]:
        if self._state.task_id == "alert-triage-easy":
            return ["review-jwt-library-version"]
        if self._state.task_id == "multi-service-incident-medium":
            return ["kill-query-RB-042"]
        return list(self._scenario.get("required_resolution_steps", []))

    def _is_redundant(self, action: IncidentAction) -> bool:
        if action.action_type == "check_logs":
            service = str(action.parameters.get("service", "")).strip()
            return service in self._state.services_checked
        if action.action_type == "check_metrics":
            return self._state.metrics_checked and not self._state.steps_executed
        return False

    def _grade_current_task(self) -> float:
        if self._state.task_id == "alert-triage-easy":
            return grade_task1(self._state)
        if self._state.task_id == "multi-service-incident-medium":
            return grade_task2(self._state)
        return grade_task3(self._state)
