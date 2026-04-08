# Product Requirements Document
## OpenEnv Environment: DevOps Incident Response (`incident-response-env`)

**Version:** 1.0 | **Author:** Pankaj Yadav | **Deadline:** April 8, 2026 11:59 PM

---

## 1. Executive Summary

This document defines the requirements for **`incident-response-env`**, an OpenEnv-compliant agentic environment that simulates real-world **production incident response** workflows. An AI agent receives simulated alerts, log snippets, and metric dashboards from a mock cloud system, then must diagnose root causes, execute runbook steps, and write post-mortems — exactly what an on-call SRE does at 3 AM.

The environment targets the RL/agent training community for training agents that can reduce MTTR (Mean Time To Resolve) in production systems — a gap no existing OpenEnv environment fills.

---

## 2. Problem Statement

On-call engineers face alert fatigue, context-switching, and knowledge gaps during incidents. Automating the first-responder tier (L1 triage) with a trained AI agent could cut mean time to resolution by 40–60% in real SRE workflows. This environment enables training and evaluation of exactly such agents in a safe, reproducible sandbox.

---

## 3. Environment Domain & Motivation

### Why This Domain Scores High

| Criterion | This Environment |
|---|---|
| Real-world utility (30%) | Directly mirrors on-call SRE workflows used at every tech company |
| Task & grader quality (25%) | 3 tasks with deterministic, programmatic graders |
| Environment design (20%) | Rich partial-reward signal across the full diagnosis trajectory |
| Code quality (15%) | Full OpenEnv spec, typed models, validated via `openenv validate` |
| Creativity & novelty (10%) | No existing OpenEnv environment in the DevOps/incident-response domain |

---

## 4. Functional Requirements

### 4.1 Real-World Task Simulation

The environment simulates an incident response session with:
- A **mock monitoring system** (Prometheus-style alerts in JSON)
- **Simulated log lines** from services (auth-service, api-gateway, db-replica)
- **Metric snapshots** (CPU, error rate, latency percentiles)
- A **runbook store** (a dict of known incident patterns → resolution steps)

The agent must take actions like `check_logs`, `run_diagnostic`, `acknowledge_alert`, `execute_runbook_step`, and `write_postmortem` against this simulated system. The state machine validates each action and returns updated observations with partial rewards.

### 4.2 OpenEnv Spec Compliance

Every component follows the official OpenEnv interface:

```
reset()       → StepResult(observation, reward=0.0, done=False)
step(action)  → StepResult(observation, reward, done, info)
state()       → IncidentState(episode_id, step_count, severity, phase)
```

All models are typed Pydantic dataclasses. The `openenv.yaml` includes full metadata. Validation via `openenv validate --verbose` must pass before submission.

### 4.3 Typed Model Definitions (`models.py`)

```python
from dataclasses import dataclass, field
from typing import Literal, Optional, List
from openenv_core import Action, Observation, State

@dataclass
class IncidentAction(Action):
    action_type: Literal[
        "check_logs", "check_metrics", "acknowledge_alert",
        "execute_runbook_step", "escalate", "write_postmortem", "resolve"
    ]
    parameters: dict = field(default_factory=dict)
    # e.g. {"service": "auth-service", "time_window": "5m"}
    # e.g. {"step_id": "db-restart-1", "runbook_id": "RB-042"}

@dataclass
class IncidentObservation(Observation):
    alert_summary: str           # Current active alerts
    log_snippet: str             # Most recent relevant log lines
    metrics_snapshot: dict       # {"cpu": 94.2, "error_rate": 0.38, ...}
    runbook_hint: Optional[str]  # Hint if agent is on the right track
    phase: str                   # "triage" | "diagnosis" | "resolution" | "postmortem"
    feedback: str                # Textual feedback on last action

@dataclass
class IncidentState(State):
    episode_id: str
    step_count: int = 0
    task_id: str = ""
    severity: str = "P2"
    phase: str = "triage"
    correct_runbook_found: bool = False
    steps_executed: List[str] = field(default_factory=list)
    postmortem_written: bool = False
    resolved: bool = False
```

---

## 5. Task Specifications

### Task 1 — `alert-triage-easy` 🟢 (Easy)

**Scenario:** A `P3` alert fires: `auth-service` login endpoint latency > 2s. Logs show a JWT validation library throwing `DeprecationWarning`. Metrics show CPU at 12%, error rate at 0.02.

**Agent Objective:** Correctly identify the root cause (library deprecation, not resource exhaustion), acknowledge the alert, and select the correct runbook from 3 options.

**Max Steps:** 8 | **Max Total Reward:** 4.0

**Grader Logic:**

```python
def grade_task1(trajectory) -> float:
    score = 0.0
    if "check_logs" in trajectory.actions:          score += 0.25  # looked at logs
    if "check_metrics" in trajectory.actions:       score += 0.15  # checked metrics
    if trajectory.acknowledged_alert:               score += 0.20  # acknowledged
    if trajectory.selected_runbook == "RB-017":     score += 0.30  # correct runbook
    if trajectory.steps <= 6:                       score += 0.10  # efficiency bonus
    return min(score, 1.0)
```

**Difficulty justification:** Single root cause, clear log signal, shallow runbook tree. A weak model should score ~0.55.

---

### Task 2 — `multi-service-incident-medium` 🟡 (Medium)

**Scenario:** Cascading `P2` incident. `api-gateway` shows 503s (error rate 0.38). Logs from `api-gateway` blame `db-replica` timeouts. `db-replica` logs show replica lag > 120s caused by a long-running analytics query hogging I/O.

**Agent Objective:** Trace the dependency chain across 3 services, identify the analytics query as the root cause (not the gateway), kill the offending query via `execute_runbook_step`, and verify resolution via `check_metrics` after the fix.

**Max Steps:** 15 | **Max Total Reward:** 8.0

**Grader Logic:**

```python
def grade_task2(trajectory) -> float:
    score = 0.0
    services_checked = set(a.parameters.get("service") for a in trajectory.actions
                           if a.action_type == "check_logs")
    if "api-gateway" in services_checked:                          score += 0.15
    if "db-replica" in services_checked:                           score += 0.20
    if trajectory.root_cause_identified == "db-replica-lag":       score += 0.25
    if "kill-query-RB-042" in trajectory.steps_executed:           score += 0.20
    post_fix_metric = trajectory.metrics_after_fix.get("error_rate", 1.0)
    if post_fix_metric < 0.05:                                     score += 0.15
    if trajectory.step_count <= 12:                                score += 0.05
    return min(score, 1.0)
```

**Difficulty justification:** Requires multi-hop log correlation. Models that only check the first alerting service will score ≤ 0.35.

---

### Task 3 — `postmortem-p1-hard` 🔴 (Hard)

**Scenario:** Full `P1` database-corruption incident. `payments-service` throws `IntegrityError` on 23% of transactions. Root cause requires correlating: (a) a deploy 47 minutes ago that changed an ORM migration, (b) a missing DB constraint in `schema_v14`, and (c) an incomplete rollback that left 3 rows in a dirty state. The agent must: triage, diagnose across 4 services + deployment history, execute a 5-step recovery runbook in correct order, then write a structured post-mortem covering timeline, impact, root cause, and action items.

**Max Steps:** 25 | **Max Total Reward:** 12.0

**Grader Logic:**

```python
def grade_task3(trajectory) -> float:
    score = 0.0
    # Triage phase (0.0 → 0.20)
    if trajectory.severity_classified == "P1":               score += 0.10
    if "payments-service" in trajectory.services_checked:    score += 0.10
    # Diagnosis phase (0.20 → 0.50)
    if trajectory.deploy_history_checked:                    score += 0.10
    if trajectory.root_cause == "orm-migration-missing-constraint":
                                                             score += 0.20
    # Resolution phase (0.50 → 0.80)
    runbook_steps_correct = [
        "rollback-deploy", "apply-constraint", "repair-dirty-rows",
        "restart-payments", "verify-integrity"
    ]
    executed = trajectory.steps_executed
    ordered_correctly = all(
        executed.index(s) < executed.index(runbook_steps_correct[i+1])
        for i, s in enumerate(runbook_steps_correct[:-1]) if s in executed
    )
    if ordered_correctly:                                    score += 0.20
    if trajectory.dirty_rows_repaired:                       score += 0.10
    # Postmortem phase (0.80 → 1.0)
    pm = trajectory.postmortem_text or ""
    for section in ["timeline", "impact", "root cause", "action items"]:
        if section in pm.lower():                            score += 0.05
    return min(score, 1.0)
```

**Difficulty justification:** Multi-phase, order-dependent runbook execution + free-text generation scoring. Frontier models (GPT-4o) expected to score ~0.72; weaker models ~0.30.

---

## 6. Reward Function Design

The reward function provides **dense, trajectory-level signal** (not sparse end-of-episode).

```python
def compute_step_reward(action, prev_state, new_state) -> float:
    reward = 0.0

    # +0.10 for each new relevant service checked (caps at 3 services)
    if action.action_type == "check_logs" and is_relevant_service(action):
        reward += 0.10

    # +0.15 for correctly identifying phase transition
    if new_state.phase != prev_state.phase:
        reward += 0.15

    # +0.20 for executing a correct runbook step (in the right order)
    if action.action_type == "execute_runbook_step":
        reward += 0.20 if is_correct_next_step(action, new_state) else -0.10

    # -0.05 per redundant action (same service checked twice)
    if is_redundant(action, prev_state):
        reward -= 0.05

    # -0.15 for escalating a P3 (overreaction penalized)
    if action.action_type == "escalate" and new_state.severity == "P3":
        reward -= 0.15

    # +0.30 for correct resolution + verified metrics
    if action.action_type == "resolve" and new_state.resolved:
        reward += 0.30

    return reward
```

**Key design properties:**
- Partial progress is rewarded at every phase transition — no sparse rewards
- Inefficiency (redundant actions, over-escalation) is penalized
- Correct ordering of runbook steps is enforced and rewarded
- Post-mortem quality uses keyword presence scoring (deterministic)

---

## 7. Project Structure

```
incident-response-env/
├── __init__.py
├── README.md
├── openenv.yaml
├── client.py
├── models.py
├── inference.py               ← Baseline inference script (root level, required)
├── pyproject.toml
├── uv.lock
└── server/
    ├── __init__.py
    ├── app.py                 ← FastAPI via create_fastapi_app()
    ├── environment.py         ← IncidentResponseEnvironment class
    ├── scenarios/
    │   ├── task1_easy.py
    │   ├── task2_medium.py
    │   └── task3_hard.py
    ├── graders.py             ← grade_task1/2/3 functions
    ├── reward.py              ← compute_step_reward()
    ├── runbook_store.py       ← Mock runbooks dict
    ├── log_generator.py       ← Synthetic log/metric fixtures
    └── Dockerfile
```

---

## 8. `openenv.yaml` Specification

```yaml
name: incident-response-env
version: "1.0.0"
description: >
  A real-world DevOps incident response environment where an AI agent
  triages production alerts, diagnoses root causes across services,
  executes remediation runbooks, and writes post-mortems.
author: pankaj-yadav
tags:
  - openenv
  - devops
  - incident-response
  - sre
  - rl-environment
tasks:
  - id: alert-triage-easy
    difficulty: easy
    max_steps: 8
    max_total_reward: 4.0
  - id: multi-service-incident-medium
    difficulty: medium
    max_steps: 15
    max_total_reward: 8.0
  - id: postmortem-p1-hard
    difficulty: hard
    max_steps: 25
    max_total_reward: 12.0
action_space: IncidentAction
observation_space: IncidentObservation
reward_range: [0.0, 1.0]
```

---

## 9. Baseline Inference Script (`inference.py`)

The script must be named `inference.py` at the project root and use the OpenAI client.  
Required environment variables: `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`, `OPENAI_API_KEY`.

```python
import asyncio, os, json
from typing import List
from openai import OpenAI
from incident_response_env import IncidentResponseEnv, IncidentAction

API_BASE_URL = os.environ["API_BASE_URL"]
MODEL_NAME   = os.environ["MODEL_NAME"]
API_KEY      = os.environ.get("OPENAI_API_KEY", os.environ.get("HF_TOKEN"))
IMAGE_NAME   = "openenv-incident-response-env:latest"
TEMPERATURE  = 0.0
MAX_TOKENS   = 512

TASKS = [
    ("alert-triage-easy",             8,  4.0, 0.60),
    ("multi-service-incident-medium", 15,  8.0, 0.55),
    ("postmortem-p1-hard",            25, 12.0, 0.45),
]

SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE) responding
to a production incident. Analyze alerts, logs, and metrics carefully before
acting. Always check logs before executing runbook steps. Follow the least
invasive resolution path. Your response must be a valid JSON action like:
{"action_type": "check_logs", "parameters": {"service": "auth-service"}}"""

def log_start(task, env, model):
    print(f'[START] {{"task": "{task}", "env": "{env}", "model": "{model}"}}', flush=True)

def log_step(step, action, reward, done, error):
    print(f'[STEP] {{"step": {step}, "action": {repr(action)}, ' +
          f'"reward": {reward}, "done": {done}, "error": {repr(error)}}}', flush=True)

def log_end(success, steps, score, rewards):
    print(f'[END] {{"success": {str(success).lower()}, "steps": {steps}, ' +
          f'"score": {score:.4f}, "rewards": {rewards}}}', flush=True)

def get_model_action(client, step, obs, last_reward, history):
    history_text = "\n".join(history[-5:])
    user_prompt = (
        f"Step {step}. Last reward: {last_reward:.2f}\n"
        f"Alert: {obs.alert_summary}\n"
        f"Logs: {obs.log_snippet}\n"
        f"Metrics: {obs.metrics_snapshot}\n"
        f"Phase: {obs.phase}\n"
        f"Feedback: {obs.feedback}\n"
        f"History:\n{history_text}\n\n"
        "Respond with your next JSON action."
    )
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return '{"action_type": "check_logs", "parameters": {"service": "api-gateway"}}'

async def run_task(task_id, max_steps, max_total_reward, threshold):
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
            raw_action = get_model_action(client, step, result.observation, last_reward, history)
            try:
                action_dict = json.loads(raw_action)
            except Exception:
                action_dict = {"action_type": "check_logs",
                               "parameters": {"service": "api-gateway"}}
            action = IncidentAction(**action_dict)
            result = await env.step(action)
            reward = result.reward or 0.0
            done   = result.done
            rewards.append(reward)
            steps_taken = step
            last_reward = reward
            log_step(step=step, action=raw_action, reward=reward, done=done, error=None)
            history.append(f"Step {step}: {raw_action!r} -> reward {reward:+.2f}")
            if done:
                break
        score = sum(rewards) / max_total_reward if max_total_reward > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= threshold
    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score

async def main():
    for task_id, max_steps, max_reward, threshold in TASKS:
        await run_task(task_id, max_steps, max_reward, threshold)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 10. Dockerfile

```dockerfile
ARG BASE_IMAGE=openenv-base:latest
FROM ${BASE_IMAGE} AS builder

WORKDIR /app
ARG BUILD_MODE=standalone
ARG ENV_NAME=incident-response-env

COPY . /app/env
WORKDIR /app/env

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-install-project --no-editable; \
    else \
        uv sync --no-install-project --no-editable; \
    fi

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-editable; \
    else \
        uv sync --no-editable; \
    fi

FROM ${BASE_IMAGE}
WORKDIR /app

COPY --from=builder /app/env/.venv /app/.venv
COPY --from=builder /app/env /app/env

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/env:$PYTHONPATH"

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "cd /app/env && uvicorn server.app:app --host 0.0.0.0 --port 8000"]
```

---

## 11. Non-Functional Requirements

| Requirement | Specification |
|---|---|
| Runtime | Inference script completes < 20 min on 2 vCPU / 8 GB RAM |
| Deployment | Hugging Face Space tagged `openenv`, responds to `reset()` with HTTP 200 |
| Validation | `openenv validate --verbose` exits 0; `openenv build` succeeds |
| Reproducibility | `TEMPERATURE=0.0`, fixed random seeds in scenario generators |
| Resource usage | Scenarios are pure Python dicts/strings — no DB, no external calls |

---

## 12. Expected Baseline Scores

| Task | Difficulty | GPT-4o-mini (est.) | Notes |
|---|---|---|---|
| `alert-triage-easy` | Easy 🟢 | ~0.70 | Clear single root cause |
| `multi-service-incident-medium` | Medium 🟡 | ~0.50 | Multi-hop trace required |
| `postmortem-p1-hard` | Hard 🔴 | ~0.38 | Order-sensitive + free text |

---

## 13. Pre-Submission Checklist

- [ ] `openenv validate --verbose` passes  
- [ ] `docker build && docker run` succeeds locally  
- [ ] HF Space URL returns HTTP 200 and responds to `reset()`  
- [ ] `inference.py` at root, uses `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`  
- [ ] `[START]`, `[STEP]`, `[END]` log format strictly followed  
- [ ] All 3 task graders return scores in `[0.0, 1.0]`  
- [ ] `openenv.yaml` includes all required metadata fields  
- [ ] `README.md` covers environment description, action/observation spaces, task descriptions, setup instructions, and baseline scores  

---

## 14. Submission Timeline

| Date | Milestone |
|---|---|
| April 7 (today) | Scaffold with `openenv init`, implement models + scenarios |
| April 8 AM | Implement graders, reward function, FastAPI server |
| April 8 Afternoon | Write `inference.py`, run baseline, fix bugs |
| April 8 Evening | `openenv push` to HF Space, run pre-submission validator |
| **April 8 11:59 PM** | **Submit ✅** |

---

*The core differentiator of this environment is that no existing OpenEnv submission targets DevOps/SRE workflows, making it immediately novel for the judges. The dense reward signal — rewarding correct phase transitions, penalizing over-escalation, and scoring runbook ordering — directly addresses the "meaningful reward function" criterion, and the post-mortem generation task in Task 3 creates a genuinely hard challenge that will separate frontier models from weaker baselines.*
