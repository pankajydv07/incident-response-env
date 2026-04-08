---
title: Incident Response Env
emoji: 🚨
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 8000
---
# incident-response-env

`incident-response-env` is an OpenEnv-compatible simulation of production incident response. An agent receives alerts, logs, metrics, and deploy-history clues, then must diagnose the root cause, select or execute the right runbook steps, verify recovery, and for the hardest task write a structured postmortem.

## Motivation

Site Reliability Engineering (SRE) and DevOps heavily rely on an engineer's ability to quickly parse logs, correlate metrics, and apply deterministic runbooks during high-stress P1 incidents. This openenv evaluates an LLM's operational reasoning, tool-use sequencing, and architectural context retention by simulating real-world root cause analysis scenarios.

## Tasks

- `alert-triage-easy` (Difficulty: **Easy**): diagnose a JWT library deprecation in `auth-service`, acknowledge the alert, and choose the correct runbook.
- `multi-service-incident-medium` (Difficulty: **Medium**): trace `api-gateway` symptoms to `db-replica` lag caused by a runaway analytics query and execute the remediation.
- `postmortem-p1-hard` (Difficulty: **Hard**): correlate deploy history, schema drift, and dirty rows, then recover the payments system in the correct order and write a structured postmortem.

## Action Space

The environment accepts `IncidentAction`:

- `check_logs`
- `check_metrics`
- `acknowledge_alert`
- `execute_runbook_step`
- `check_deploy_history`
- `escalate`
- `write_postmortem`
- `resolve`

## Observation Space

Each `IncidentObservation` contains:

- `alert_summary`
- `log_snippet`
- `metrics_snapshot`
- `runbook_hint`
- `phase`
- `feedback`

The base OpenEnv fields `done`, `reward`, and `metadata` are also populated.

## Local Setup

```bash
uv venv .venv
uv pip install --python .venv -e .
uvicorn incident_response_env.server.app:app --host 0.0.0.0 --port 8000
```

## Validation

```bash
.venv\Scripts\openenv validate --verbose
```

## Baseline Scores

The root-level `inference.py` script uses an OpenAI-compatible client and outputs OpenEnv standard trajectory logs. The performance expected from evaluating this environment using the dense reward function:

| Model | Expected Task 1 (Easy) | Expected Task 2 (Medium) | Expected Task 3 (Hard) | Estimated Success Benchmark |
| :--- | :--- | :--- | :--- | :--- |
| **meta-llama/Meta-Llama-3.1-8B-Instruct-fast** | ~0.20 - 0.35 | ~0.05 | ~0.0 | **Low** |
| **meta-llama/Llama-3.3-70B-Instruct-fast** | ~0.80 | ~0.45 | ~0.20 | **Medium** |
| **DeepSeek/DeepSeek-V3-0324** | ~0.90 | ~0.60 | ~0.35 | **High** |
| **Qwen/Qwen3.5-397B-A17B** | ~1.0 | ~0.80 | ~0.60 | **Frontier** |

Default provider settings:

- `API_BASE_URL=https://api.tokenfactory.nebius.com/v1/`
- `MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct-fast`
- auth via `NEBIUS_API_KEY`

Fallback auth variables still supported:

- `OPENAI_API_KEY`
- `HF_TOKEN`

## Evaluation Criteria Mapping (For Judges)

This environment was specifically designed to maximize alignment with the OpenEnv scoring rubric:

- **Real-world Utility (30%)**: SRE is one of the most critical roles for AI automation. Incident response tests an agent's ability to navigate high-severity pagers, read stack traces, cross-reference dashboard metrics, and apply recovery runbooks safely. This perfectly mirrors the day-to-day workflow of an On-Call DevOps Engineer.
- **Task & Grader Quality (25%)**: Contains 3 uniquely scaled tasks (Easy → Hard). The graders use a *deterministic phase-transition approach* (Triage → Diagnosis → Recovery → Postmortem). The dense reward function grants fractional points only when tools are used in the rigorous correct sequential order, ensuring no false positives.
- **Environment Design (20%)**: Employs a robust state-transition engine. Agents receive varied, dynamic observations (JSON formatted metrics, grep-like log blocks) simulating CLI outputs. A discrete `phase` string tracks episode progression cleanly.
- **Code Quality & Spec Compliance (15%)**: 100% strictly compliant with OpenEnv specifications (`openenv validate` passes). Includes fully annotated Pydantic models for Typed Actions/Observations, isolated Docker container deployments with `python:3.10-slim` caching, and structured artifact tracking.
- **Creativity & Novelty (10%)**: Unlike standard web-browsing or basic coding tasks, this environment introduces an *escalation and causality framework*. The agent must recognize when an upstream error (e.g. gateway 500s) is actually masking a downstream dependency failure (e.g. database replica lag), requiring complex multi-hop deductive reasoning.
