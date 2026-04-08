"""Easy incident scenario."""

SCENARIO = {
    "task_id": "alert-triage-easy",
    "severity": "P3",
    "max_steps": 8,
    "initial_phase": "triage",
    "alert_summary": "P3 auth-service login latency above 2s for 5m",
    "initial_feedback": "Acknowledge the alert and investigate before escalating.",
    "initial_metrics": {
        "service": "auth-service",
        "cpu": 12.0,
        "error_rate": 0.02,
        "p95_latency_ms": 2210,
    },
    "service_logs": {
        "auth-service": (
            "2026-04-07T22:40:18Z WARN jwt.validator DeprecationWarning: "
            "legacy JWT validation path in use; refresh library before next rollout"
        ),
    },
    "correct_runbook": "RB-017",
    "root_cause": "jwt-library-deprecation",
    "runbook_hint": "Logs point to a code-level issue rather than CPU pressure.",
    "recommended_services": ["auth-service"],
    "resolve_metrics": {
        "service": "auth-service",
        "cpu": 11.5,
        "error_rate": 0.01,
        "p95_latency_ms": 640,
    },
    "available_runbooks": ["RB-003", "RB-017", "RB-099"],
}
