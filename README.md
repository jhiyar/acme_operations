# Acme Operations — Agentic Enterprise Assistant

Minimal working prototype for the Applied AI Engineer case study: a Keycloak-authenticated assistant that uses an LLM agent, PostgreSQL data, Redis memory, MCP tools, and a reusable Skill.

## Quick start

```bash
# 1. Add LLM keys
cp .env.example backend/.env   # or edit backend/.env
# ANTHROPIC_API_KEY=...
# OPENAI_API_KEY=...           # optional

# 2. Run everything
docker compose up --build

# 3. Open UI
open http://localhost:5173
```

Demo users (Keycloak):

| User | Password | Role |
|------|----------|------|
| `sales` | `sales123` | sales_user (read) |
| `support` | `support123` | support_user (read + next actions) |
| `admin` | `admin123` | admin |

## Architecture

```
Browser (React)
    │  JWT
    ▼
Django/DRF API ──► LangGraph ReAct agent
    │                    │
    │                    ├─ AgentToolService (domain tools)
    │                    ├─ CustomerEscalationSummarySkill
    │                    └─ LLM (Anthropic / OpenAI-compatible)
    │
    ├── PostgreSQL (customers, issues, updates, next_actions)
    ├── Redis (session memory, customer cache, traces)
    ├── Keycloak
    └── MCP server (same tools over Model Context Protocol)
```

### Why MCP

MCP separates **tool definitions/transport** from the **agent runtime**. The LangGraph agent calls in-process tools for low latency inside our API. The MCP server exposes the *same* Acme capabilities to external hosts (Cursor, Claude Desktop, other agents) without embedding SQL or RBAC rules in those hosts. Domain logic stays in `AgentToolService` / Skills; MCP is an adapter.

### Skills vs tools

| | Tools | Skill |
|---|---|---|
| Granularity | Single capability | Multi-step workflow |
| Example | `summarise_issue_history` | `customer_escalation_summary` |
| Behaviour | One DB/LLM call | Profile → open issues → issue summaries → structured brief |

The **Customer Escalation Summary** skill returns executive summary, risk level, recommended next action, and missing information.

### Redis vs Postgres

| Store | Holds |
|-------|--------|
| **Postgres** | Durable customers, issues, chat conversations/messages, agent-run traces (source of truth) |
| **Redis** | Warm session cache, customer/tool caches, short-TTL debug traces |

Chat agent context uses a **sliding window** of the last `AGENT_HISTORY_MAX_TURNS` (default 8) messages from Postgres, with each turn capped at `AGENT_HISTORY_MAX_CHARS_PER_TURN` (default 1200) so long replies don’t blow the prompt. Redis is rehydrated from Postgres when empty; if Redis is down, multi-turn chat still works via Postgres.

Trade-off: older turns outside the window are not sent to the model (unless you later add a rolling summary). Losing Redis does not lose operational or chat data.

## Agent tools

1. `get_customer_profile`
2. `get_open_issues_for_customer` (exact / partial / keyword)
3. `summarise_issue_history` (LLM)
4. `create_next_action` (LLM recommend + persist; support/admin)
5. `customer_escalation_summary` (Skill)

## Evaluation & observability

```bash
cd backend
python manage.py eval_agent --provider anthropic
# Results: backend/evals/results/latest.json + latest.md

# DeepEval (LLM-as-judge on stored AgentRun replies)
python manage.py eval_deepeval
```

Eval checks: tool selection, grounding keywords, RBAC, next-action / skill behaviour.

Observability on each `/api/chat/` request:

- `tool_trace` in the response
- `trace_id` + `latency_ms` + token totals
- Durable Postgres rows: `AgentRun`, `LlmCall`, `ToolCall`
- Admin UI at `/observability` (admin role)
- Structured logs (`acme.llm`, `acme.observability`)
- Trace JSON under `backend/evals/traces/` (and Redis when available)

Manual live smoke:

```bash
python manage.py run_agent_smoke --message "Summarise Contoso open issues"
```

## MCP server

Container listens on `http://localhost:8001` (SSE). Tools mirror the agent tools plus the escalation skill.

```bash
docker compose logs -f mcp
```

## Local tests (no live LLM)

```bash
cd backend
python manage.py test core.tests issues.tests
```

## AI tool usage notes (assessment)

AI coding assistants (Cursor) were used to scaffold services, MCP wiring, and tests. Human review focused on RBAC, tool contracts, seed realism, Docker env handling, and eval failures (model IDs, partial customer names, keyword search). LLM outputs for summarise / next-action / escalation are treated as assistive and grounded only via tool-fetched context.
