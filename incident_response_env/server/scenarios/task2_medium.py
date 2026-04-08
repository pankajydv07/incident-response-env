"""Medium incident scenario."""

SCENARIO = {
    "task_id": "multi-service-incident-medium",
    "severity": "P2",
    "max_steps": 15,
    "initial_phase": "triage",
    "alert_summary": "P2 api-gateway 503 error rate at 38% for checkout requests",
    "initial_feedback": "The first noisy service is not always the root cause.",
    "initial_metrics": {
        "service": "api-gateway",
        "cpu": 51.0,
        "error_rate": 0.38,
        "p95_latency_ms": 4100,
    },
    "service_logs": {
        "api-gateway": (
            "2026-04-07T22:41:00Z ERROR upstream timeout waiting for db-replica "
            "after 3000ms while serving /checkout"
        ),
        "db-replica": (
            "2026-04-07T22:41:15Z WARN replication lag=128s source=analytics-query-77 "
            "io_wait=high"
        ),
        "analytics-worker": (
            "2026-04-07T22:41:18Z INFO query-77 full-table scan on revenue_events "
            "running for 742s"
        ),
    },
    "correct_runbook": "RB-042",
    "root_cause": "db-replica-lag",
    "runbook_hint": "Follow the dependency chain one hop deeper than the gateway.",
    "recommended_services": ["api-gateway", "db-replica", "analytics-worker"],
    "resolve_metrics": {
        "service": "api-gateway",
        "cpu": 36.0,
        "error_rate": 0.03,
        "p95_latency_ms": 820,
    },
    "available_runbooks": ["RB-011", "RB-042", "RB-088"],
}
