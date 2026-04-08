"""Mock runbook data used by all scenarios."""

RUNBOOK_STORE = {
    "RB-017": {
        "title": "JWT library deprecation remediation",
        "steps": [
            "review-jwt-library-version",
            "pin-supported-jwt-library",
            "schedule-safe-rollout",
        ],
    },
    "RB-042": {
        "title": "Replica lag from runaway analytics query",
        "steps": [
            "confirm-replica-lag",
            "identify-analytics-query",
            "kill-query-RB-042",
            "verify-replication-recovery",
        ],
    },
    "RB-901": {
        "title": "Payments integrity recovery",
        "steps": [
            "rollback-deploy",
            "apply-constraint",
            "repair-dirty-rows",
            "restart-payments",
            "verify-integrity",
        ],
    },
}
