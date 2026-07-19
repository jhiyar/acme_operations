# Evaluation results — commentary

This document is the human commentary for the Acme Operations eval harness. It is the pack “eval results + commentary” deliverable.

Raw machine output from the latest local run lives next to this file under `backend/evals/results/` (`latest.md` / `latest.json`, gitignored). Re-run with:

```bash
cd backend
python manage.py eval_agent --provider anthropic
```

Optional LLM-as-judge on stored `AgentRun` replies:

```bash
python manage.py eval_deepeval
```

## Latest headline result

| Field | Value |
|-------|--------|
| Score | **15 / 15** |
| Provider | Anthropic |
| Model | `claude-sonnet-4-5-20250929` |
| Generated | `2026-07-19T08:24:48Z` (UTC) |
| Harness | `python manage.py eval_agent` |

Cases cover the brief’s eval criteria: correct tool selection, grounding in DB-backed tool results, RBAC, reasonable next actions, plus skill and Redis memory checks.

## What we measure

| Check | How |
|-------|-----|
| Tool selection | Expected / forbidden / any-of tool names from agent `tool_trace` |
| Grounding | Reply must contain domain keywords (customer names, “alert”, “Northwind”, etc.) pulled from seeded data |
| RBAC | Sales user invoking `create_next_action` must not successfully persist; support/admin may |
| Next actions | Support path must call `create_next_action` and produce a non-empty recommendation |
| Skill | Contoso escalation must call `customer_escalation_summary` and mention a risk level |
| Memory | Multi-turn Redis session recall + customer cache population after profile lookup |

## Case map (Q01–Q15)

| ID | Intent | Result |
|----|--------|--------|
| Q01 | Customer profile tool | PASS |
| Q02 | Open issues for Northwind | PASS |
| Q03 | Summarise Contoso critical issue | PASS |
| Q04 | Create next action (support) | PASS |
| Q05 | Create next action RBAC (sales blocked) | PASS |
| Q06 | Compound Contoso query (multi-tool) | PASS |
| Q07 | Unknown customer handling | PASS |
| Q08 | Fabrikam SSO summary | PASS |
| Q09 | Northwind profile + open issues | PASS |
| Q10 | Chitchat without forced writes | PASS |
| Q11 | Ambiguous “Client X” → Northwind | PASS |
| Q12 | Contoso open issues only | PASS |
| Q13 | Escalation skill | PASS |
| Q14 | Redis session memory across turns | PASS |
| Q15 | Redis customer cache after profile | PASS |

## Notable behaviours

- **Ambiguous Client X (Q11):** Agent uses `get_open_issues_for_customer` with keyword matching and resolves to Northwind’s warehouse tracking issue — no hardcoded router.
- **RBAC (Q05):** Tool is still *called*, but the service returns an error for `sales_user`; the reply explains the denial. That matches “RBAC respected” without pretending the model never attempts the tool.
- **Compound query (Q06):** Multiple tools in one turn (`profile` → `open issues` → `summarise` → `create_next_action`), which is the scenario in the client brief.
- **Memory (Q14–Q15):** Session turns and customer cache are validated against Redis, not only reply text.

## Failures we hit earlier (and fixes)

These showed up in earlier live runs before the 15/15 pass:

1. **Stale Anthropic model id** → 404; fixed default to `claude-sonnet-4-5-20250929`.
2. **Partial names** (“Contoso” vs “Contoso Ltd”) → added case-insensitive / candidate matching in customer lookup.
3. **Nickname queries** (“Client X warehouse”) → keyword open-issue search instead of requiring an exact customer row.
4. **Summarise / next-action as templates** → forced through LLM clients grounded on tool-fetched issue context.
5. **Env keys emptied by Compose `${VAR:-}`** → load secrets from `backend/.env` via `env_file` so keys are not overridden to empty.

## Limits and honesty

- Heuristic scoring (tools + keywords + regex) is intentional for a fast, CI-friendly harness; it does **not** fully judge answer quality the way DeepEval / human review would.
- `eval_deepeval` is optional and needs a judge model key; it scores stored `AgentRun` replies, not the golden Q-set directly.
- Latency varies (summarise / skill / compound cases often 20–40s) — acceptable for the prototype, not tuned for production SLOs.
- Observability stores run/tool/token metadata in Postgres; full prompt bodies are not persisted yet (privacy / size trade-off).

## How this maps to the brief (§4.8)

| Brief ask | Evidence |
|-----------|----------|
| 5–10 test questions | 15 cases in `eval_agent` |
| Correct tool(s) | Scored per case via `tool_trace` |
| Grounded in DB results | Keyword / entity checks against seed data |
| RBAC respected | Q05 sales path |
| Reasonable next actions | Q04 / Q06 tool + non-empty recommendation |
| Tool logs, traces, errors, latency | Chat API + `AgentRun` / Observability page + eval timings |
