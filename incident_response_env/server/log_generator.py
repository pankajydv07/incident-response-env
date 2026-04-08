"""Static fixtures for logs and metrics used by the scenarios."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


def clone_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Return a detached copy to avoid mutating scenario fixtures."""

    return deepcopy(metrics)
