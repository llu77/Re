# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Medical Rehabilitation AI Consultant — a Streamlit web application powered by Claude API (claude-sonnet-4-6) with Extended Thinking and Tool Use. Supports comprehensive medical rehabilitation across orthopedic, neurological, cardiac, pulmonary, vision, pediatric, geriatric, pain, and psychosocial specialties.

## Architecture

- **`app.py`** — Streamlit frontend (patient registry, chat UI, assessments, CDSS, interventions, documents). All UI text is Arabic (RTL).
- **`rehab_consultant.py`** — Core AI engine: SYSTEM_PROMPT, TOOLS array (22 tools), execute_tool(), tool use loop, record_treatment_plan.
- **`orchestrator.py`** — Multi-Agent Orchestrator: routes requests to specialized agents (assessment, treatment, general) based on keyword matching.
- **`agents/`** — Specialized agents: `base_agent.py` (BaseAgent with sync + streaming), `assessment_agent.py`, `treatment_agent.py`.
- **`tools/`** — 15+ clinical tools (PubMed, calculator, visual exercises, etc.)
- **`cdss/`** — Clinical Decision Support System with YAML rule engine, guardrails, explainability.
- **`assessments/`** — Digital biomarkers (fixation BCEA, reading MNREAD, visual search, contrast).
- **`interventions/`** — Active treatments (scanning trainer, perceptual learning, visual augmentation, device routing).
- **`chains/`** — Prompt chaining for multi-phase assessment (case_assessment.py).
- **`utils/security.py`** — Input sanitization and medical output validation.
- **`data/patients/`** — Patient JSON files with sequential file numbers.

## Key Patterns

- **Tool Use Loop**: `client.messages.create()` → check `stop_reason` → if `tool_use`, execute tools, append results, loop → if `end_turn`, return text.
- **Streaming**: `client.messages.stream()` via `BaseAgent.process_stream()` — tokens displayed word-by-word in `st.empty()` placeholder.
- **Patient Context**: `build_patient_system_context()` appends patient data to SYSTEM_PROMPT for each chat turn.
- **No Emojis**: The frontend uses text labels and CSS-styled badges instead of emoji characters.

## Commands

```bash
# Run the app
streamlit run app.py

# Quick syntax check
python3 -c "compile(open('app.py').read(), 'app.py', 'exec'); print('OK')"

# Verify imports
python3 -c "from rehab_consultant import SYSTEM_PROMPT, TOOLS; print(len(TOOLS), 'tools')"
python3 -c "from orchestrator import RehabOrchestrator; print('orchestrator OK')"
python3 -c "from agents import BaseAgent, AssessmentAgent, TreatmentAgent; print('agents OK')"
```

## Environment Variables

- `ANTHROPIC_API_KEY` — Required for Claude API access.
