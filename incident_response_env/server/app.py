"""FastAPI entrypoint for the incident response environment."""

from __future__ import annotations

from openenv.core import create_app

from incident_response_env.models import IncidentAction, IncidentObservation
from incident_response_env.server.environment import IncidentResponseEnvironment

app = create_app(
    IncidentResponseEnvironment,
    IncidentAction,
    IncidentObservation,
    env_name="incident-response-env",
    max_concurrent_envs=4,
)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
