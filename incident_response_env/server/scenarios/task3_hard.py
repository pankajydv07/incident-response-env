"""Hard incident scenario."""

SCENARIO = {
    "task_id": "postmortem-p1-hard",
    "severity": "P1",
    "max_steps": 25,
    "initial_phase": "triage",
    "alert_summary": "P1 payments-service IntegrityError on 23% of transactions",
    "initial_feedback": "This incident needs diagnosis, ordered recovery, and a postmortem.",
    "initial_metrics": {
        "service": "payments-service",
        "cpu": 67.0,
        "error_rate": 0.23,
        "p95_latency_ms": 5200,
    },
    "service_logs": {
        "payments-service": (
            "2026-04-07T22:42:03Z ERROR sqlalchemy.exc.IntegrityError on ledger write "
            "constraint customer_payment_fk missing in schema_v14"
        ),
        "migration-runner": (
            "2026-04-07T21:55:00Z INFO deploy payments-release-2026.04.07.1 "
            "applied orm migration bundle v14"
        ),
        "db-primary": (
            "2026-04-07T22:42:11Z WARN 3 rows in payments_ledger left dirty after partial rollback"
        ),
        "rollback-worker": (
            "2026-04-07T22:42:20Z ERROR rollback stopped before data repair step completed"
        ),
    },
    "deploy_history": (
        "payments-release-2026.04.07.1 deployed 47 minutes ago; "
        "migration 14 removed explicit constraint guard in ORM layer"
    ),
    "correct_runbook": "RB-901",
    "root_cause": "orm-migration-missing-constraint",
    "runbook_hint": "Correlate deploy history with schema and partial rollback state.",
    "recommended_services": [
        "payments-service",
        "migration-runner",
        "db-primary",
        "rollback-worker",
    ],
    "resolve_metrics": {
        "service": "payments-service",
        "cpu": 35.0,
        "error_rate": 0.01,
        "p95_latency_ms": 690,
    },
    "required_resolution_steps": [
        "rollback-deploy",
        "apply-constraint",
        "repair-dirty-rows",
        "restart-payments",
        "verify-integrity",
    ],
    "available_runbooks": ["RB-315", "RB-622", "RB-901"],
}
