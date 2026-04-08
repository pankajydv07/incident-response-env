"""Baseline inference loop for the incident response environment."""

from __future__ import annotations

import asyncio
import json
import os
from typing import List

from openai import OpenAI

from incident_response_env import IncidentAction, IncidentResponseEnv

# Load .env from the same directory as this script (no extra dependency)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
MODEL_NAME = os.environ.get("MODEL_NAME", "meta-llama/Meta-Llama-3.1-8B-Instruct-fast")
API_KEY = (
    os.environ.get("NEBIUS_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("HF_TOKEN")
)
IMAGE_NAME = os.environ.get("IMAGE_NAME", "openenv-incident-response-env:latest")
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.0"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "512"))

TASKS = [
    ("alert-triage-easy", 8, 4.0, 0.60),
    ("multi-service-incident-medium", 15, 8.0, 0.55),
    ("postmortem-p1-hard", 25, 12.0, 0.45),
]

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer responding to a \
production incident. Analyze alerts, logs, metrics, and deploy history before \
acting. Use JSON only.

Allowed actions:
- {"action_type":"check_logs","parameters":{"service":"auth-service"}}
- {"action_type":"check_metrics","parameters":{}}
- {"action_type":"acknowledge_alert","parameters":{}}
- {"action_type":"execute_runbook_step","parameters":{"runbook_id":"RB-017","step_id":"review-jwt-library-version"}}
- {"action_type":"check_deploy_history","parameters":{}}
- {"action_type":"write_postmortem","parameters":{"text":"Timeline: ... Impact: ... Root cause: ... Action items: ..."}}
- {"action_type":"resolve","parameters":{}}
"""


if not API_KEY:
    raise RuntimeError(
        "Set one of NEBIUS_API_KEY, OPENAI_API_KEY, or HF_TOKEN before running inference.py"
    )



def log_start(task: str, env: str, model: str) -> None:
    print(f'[START] {{"task": "{task}", "env": "{env}", "model": "{model}"}}', flush=True)



def log_step(step: int, action: str, reward: float, done: bool, error: str | None) -> None:
    print(
        f'[STEP] {{"step": {step}, "action": {action!r}, "reward": {reward}, '
        f'"done": {str(done).lower()}, "error": {error!r}}}',
        flush=True,
    )



def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    print(
        f'[END] {{"success": {str(success).lower()}, "steps": {steps}, '
        f'"score": {score:.4f}, "rewards": {rewards}}}',
        flush=True,
    )



def get_model_action(client: OpenAI, step: int, result, last_reward: float, history: List[str]) -> str:
    obs = result.observation
    history_text = "\n".join(history[-5:])
    user_prompt = (
        f"Step {step}. Last reward: {last_reward:.2f}\n"
        f"Alert: {obs.alert_summary}\n"
        f"Logs: {obs.log_snippet}\n"
        f"Metrics: {obs.metrics_snapshot}\n"
        f"Phase: {obs.phase}\n"
        f"Feedback: {obs.feedback}\n"
        f"Metadata: {obs.metadata}\n"
        f"History:\n{history_text}\n\n"
        "Respond with the next JSON action only."
    )
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return '{"action_type":"check_logs","parameters":{"service":"api-gateway"}}'


async def run_task(task_id: str, max_steps: int, max_total_reward: float, threshold: float) -> float:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = await IncidentResponseEnv.from_docker_image(IMAGE_NAME)
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    log_start(task=task_id, env="incident-response-env", model=MODEL_NAME)
    try:
        result = await env.reset(task_id=task_id)
        last_reward = 0.0
        for step in range(1, max_steps + 1):
            if result.done:
                break
            raw_action = get_model_action(client, step, result, last_reward, history)
            try:
                action_dict = json.loads(raw_action)
            except Exception:
                action_dict = {
                    "action_type": "check_logs",
                    "parameters": {"service": "api-gateway"},
                }
            action = IncidentAction(**action_dict)
            result = await env.step(action)
            reward = float(result.reward or 0.0)
            rewards.append(reward)
            steps_taken = step
            last_reward = reward
            log_step(step=step, action=raw_action, reward=reward, done=result.done, error=None)
            history.append(f"Step {step}: {raw_action!r} -> reward {reward:+.2f}")
            if result.done:
                break
        score = sum(rewards) / max_total_reward if max_total_reward > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= threshold
    finally:
        await env.close()
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


async def main() -> None:
    for task_id, max_steps, max_reward, threshold in TASKS:
        await run_task(task_id, max_steps, max_reward, threshold)


if __name__ == "__main__":
    asyncio.run(main())
