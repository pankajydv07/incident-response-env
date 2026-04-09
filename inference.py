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

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.tokenfactory.us-central1.nebius.com/v1/")
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-ai/DeepSeek-R1-0528-fast")
API_KEY = (
    os.environ.get("NEBIUS_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or os.environ.get("HF_TOKEN")
)
IMAGE_NAME = os.environ.get("IMAGE_NAME", "openenv-incident-response-env:latest")
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.0"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "512"))

TASKS = [
    ("alert-triage-easy", 8, 1.0, 0.60),
    ("multi-service-incident-medium", 15, 1.0, 0.55),
    ("postmortem-p1-hard", 25, 1.0, 0.45),
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


# ---------------------------------------------------------------------------
# Helpers to clamp any score/reward to the strictly open interval (0, 1)
# ---------------------------------------------------------------------------
MIN_SCORE = 0.0001
MAX_SCORE = 0.9999


def _clamp(value: float) -> float:
    """Clamp a value to the strict open interval (0, 1)."""
    return min(max(value, MIN_SCORE), MAX_SCORE)


def log_start(task: str, env: str, model: str) -> None:
    print(f'[START] {{"task": "{task}", "env": "{env}", "model": "{model}"}}', flush=True)



def log_step(step: int, action: str, reward: float, done: bool, error: str | None) -> None:
    # Clamp reward to (0, 1) before logging
    clamped_reward = _clamp(reward)
    print(
        f'[STEP] {{"step": {step}, "action": {action!r}, "reward": {clamped_reward}, '
        f'"done": {str(done).lower()}, "error": {error!r}}}',
        flush=True,
    )



def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    # Clamp the final score to (0, 1) before logging
    clamped_score = _clamp(score)
    clamped_rewards = [_clamp(r) for r in rewards]
    print(
        f'[END] {{"success": {str(success).lower()}, "steps": {steps}, '
        f'"score": {clamped_score:.4f}, "rewards": {clamped_rewards}}}',
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
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text", 
                            "text": user_prompt
                        }
                    ]
                },
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
    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    # CRITICAL: Initialize score to a valid value inside (0, 1), never 0.0
    score = MIN_SCORE
    success = False
    log_start(task=task_id, env="incident-response-env", model=MODEL_NAME)
    env = None
    try:
        env = await IncidentResponseEnv.from_docker_image(IMAGE_NAME)
        result = await env.reset(task_id=task_id)
        last_reward = float(result.reward or MIN_SCORE)
        for step in range(1, max_steps + 1):
            if result.done:
                break
            raw_action = get_model_action(client, step, result, last_reward, history)
            if "</think>" in raw_action:
                clean_json = raw_action.split("</think>")[-1].strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json.split("```json")[-1].split("```")[0].strip()
            else:
                clean_json = raw_action.strip()

            try:
                action_dict = json.loads(clean_json)
            except Exception:
                action_dict = {
                    "action_type": "check_logs",
                    "parameters": {"service": "api-gateway"},
                }
            try:
                action = IncidentAction(**action_dict)
            except Exception as exc:
                print(f"[DEBUG] Validation failed: {exc}", flush=True)
                action = IncidentAction(action_type="check_logs", parameters={"service": "api-gateway"})
            
            result = await env.step(action)
            # The environment returns the cumulative grader score as reward.
            # It is always in (0.0001, 0.9999) thanks to _bounded_score().
            reward = _clamp(float(result.reward or MIN_SCORE))
            rewards.append(reward)
            steps_taken = step
            last_reward = reward
            log_step(step=step, action=raw_action, reward=reward, done=result.done, error=None)
            history.append(f"Step {step}: {raw_action!r} -> reward {reward:+.4f}")
            if result.done:
                break
        # The reward from the environment is the cumulative grader score (0.0001–0.9999).
        # Use the LAST reward as the task score since it represents total progress.
        score = rewards[-1] if rewards else MIN_SCORE
        score = _clamp(score)
        success = score >= threshold
    except Exception as exc:
        print(f"[ERROR] Task {task_id} failed with unhandled exception: {exc}", flush=True)
        # Even on error, emit a valid score inside (0, 1)
        log_step(step=steps_taken + 1, action="error", reward=MIN_SCORE, done=True, error=str(exc))
        # Use last known reward if we have any, otherwise MIN_SCORE
        score = _clamp(rewards[-1] if rewards else MIN_SCORE)
    finally:
        if env:
            try:
                await env.close()
            except Exception as exc_close:
                print(f"[ERROR] Failed to close env: {exc_close}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


async def main() -> None:
    for task_id, max_steps, max_reward, threshold in TASKS:
        try:
            await run_task(task_id, max_steps, max_reward, threshold)
        except Exception as exc:
            print(f"[CRITICAL] Unhandled exception in main for {task_id}: {exc}", flush=True)
            # Even if run_task itself crashes, emit a valid [END] with valid score
            log_end(success=False, steps=0, score=MIN_SCORE, rewards=[MIN_SCORE])


if __name__ == "__main__":
    asyncio.run(main())
