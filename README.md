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

Backend layout, commands, and API table: [`backend/README.md`](backend/README.md).

Demo users (Keycloak):

| User | Password | Role |
|------|----------|------|
| `sales` | `sales123` | sales_user (read) |
| `support` | `support123` | support_user (read + update issues + next actions) |
| `admin` | `admin123` | admin (all issues + updates + next actions) |


## Architecture diagram

```mermaid
flowchart TB
  subgraph clients [Clients]
    UI[React UI :5173]
    Ext[External MCP hosts]
  end

  subgraph compose [Docker Compose]
    KC[Keycloak :8080]
    API[Django/DRF API :8000]
    MCP[MCP server :8001]
    PG[(PostgreSQL)]
    Redis[(Redis)]
    KCPG[(Keycloak Postgres)]
  end

  subgraph agent [Agent runtime]
    LG[LangGraph ReAct]
    Tools[AgentToolService]
    Skill[Customer Escalation Summary Skill]
    LLM[Anthropic / OpenAI]
  end

  UI -->|OIDC login| KC
  UI -->|Bearer JWT| API
  API --> LG
  LG --> Tools
  LG --> Skill
  LG --> LLM
  Skill --> Tools
  Tools --> PG
  API --> PG
  API --> Redis
  LG --> Redis
  API -.->|validate JWT| KC
  KC --> KCPG
  Ext -->|SSE tools| MCP
  MCP --> Tools
  MCP --> Skill
```

ASCII summary of the same flow:

```
Browser (React + Keycloak login)
    │  JWT
    ▼
Django/DRF API ──► LangGraph ReAct agent
    │                    │
    │                    ├─ AgentToolService (domain tools)
    │                    ├─ CustomerEscalationSummarySkill
    │                    └─ LLM (Anthropic / OpenAI-compatible)
    │
    ├── PostgreSQL (customers, issues, chat, agent runs)
    ├── Redis (warm session / caches)
    ├── Keycloak (+ dedicated Postgres)
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

## Trade-offs

Strategic choices for a reviewable prototype — what we accepted, and why.

| Choice | What we gained | What we accepted |
|--------|----------------|------------------|
| **Django + DRF over FastAPI** | Built-in ORM, migrations, admin, and a mature request/response stack — less glue for CRUD-heavy domain data (customers, issues, chat, traces) | Heavier than a thin API-only framework; FastAPI is often faster for pure async I/O APIs, but ships no ORM — you’d add SQLAlchemy/SQLModel and wire migrations yourself |
| **LangGraph + LangChain** | A real ReAct agent loop, tool tracing, LangSmith, and Anthropic/OpenAI behind one switch | A heavier dependency than a tiny custom loop — worth it because the same stack supports evals, tracing, and future multi-step workflows |
| **In-app chat vs MCP** | Chat uses the signed-in user’s roles; MCP exposes the same tools to external hosts (Cursor, etc.) | MCP runs as a demo **admin** identity so callers don’t need to pass end-user tokens. Real RBAC is on the API/chat path; MCP auth is not production-ready |
| **Keycloak-only users** | Login and roles live in Keycloak; the API reads them from the JWT | No app `users` / `user_roles` tables in Postgres — Keycloak already owns that job, so we don’t keep a second copy to sync |
| **Postgres + Redis** | Postgres holds durable truth (including issue summaries); Redis warms sessions, customer lookups, and recent open-issue tool results | Redis down → chat/summaries still work from Postgres; tool caches are best-effort speedups |
| **One Compose stack** | Reviewers can `docker compose up` and see Keycloak, API, UI, MCP, and data together | Local all-in-one demo — not how you’d host or scale this in production |
| **Skills vs tools** | Tools = one capability; Skills = multi-step playbooks (e.g. escalation brief) | Extra concept to learn, but clearer than stuffing workflows into one mega-prompt |
| **Smoke CLI / eval harness** | Fast agent checks without logging in through the UI | They use a synthetic role (default admin) — for wiring checks, not for proving end-user auth |

### Redis vs Postgres (detail)

| Store | Holds |
|-------|--------|
| **Postgres** | Durable customers, issues, updates, next actions, **issue history summaries** (LLM output, fingerprint-invalidated), chat conversations/messages, agent-run traces |
| **Redis** | Warm session turns, **cached customer lookups** (`REDIS_CACHE_TTL_SECONDS`), **recent open-issue tool results** (`REDIS_TOOL_TTL_SECONDS`, keyed by customer + viewer for RBAC), short-TTL debug traces |

**Why summaries in Postgres:** expensive LLM output that should survive Redis restarts and stay correct when the timeline changes (fingerprint includes issue fields, updates, and next actions).

**Why tool/customer lookups in Redis:** short-lived speedups for repeated reads in one session; TTL keeps them fresh enough for a demo without complex invalidation. Mutating tools (`create_next_action`) are never cached.

Chat context uses a **sliding window** of the last `AGENT_HISTORY_MAX_TURNS` (default 8) messages from **Postgres**, each turn capped at `AGENT_HISTORY_MAX_CHARS_PER_TURN` (default 1200). Redis is rehydrated when empty.

### RBAC (demonstrated)

| Role | Issues / customers | Status / timeline note | Issue & customer CRUD | Create next action (agent tool) | Observability |
|------|--------------------|------------------------|----------------------|----------------------------------|---------------|
| `sales_user` | Read assigned issues + customer directory | No | No | No (tool returns RBAC error) | No |
| `support_user` | Read assigned issues + customer directory | Yes | No | Yes | No |
| `admin` | All issues + customers | Yes | Yes | Yes | Yes |

Frontend gates use `<PermissionCheck roles={[…]}>` (menu + page actions). Backend enforces the same rules in services/views.

## Agent tools

1. `get_customer_profile`
2. `get_open_issues_for_customer` (exact / partial / keyword)
3. `summarise_issue_history` (LLM)
4. `create_next_action` (LLM recommend + persist; support/admin)
5. `customer_escalation_summary` (Skill)

## Evaluation & observability

**Latest live harness result: 15/15** (Anthropic `claude-sonnet-4-5-20250929`).

Full eval narrative (case map, earlier failures/fixes, limits, brief mapping):  
**[`backend/evals/RESULTS.md`](backend/evals/RESULTS.md)** — sits beside raw `evals/results/latest.md` (gitignored machine output).

```bash
cd backend
python manage.py eval_agent --provider anthropic
# Raw output (gitignored): backend/evals/results/latest.json + latest.md

# Optional DeepEval judge on stored AgentRun replies
python manage.py eval_deepeval
```

Coverage snapshot: tool selection, grounding, RBAC, next-action + skill, Redis memory/cache. Earlier fixes included model id, partial customer names, and Client X keyword match.

Observability on each `/api/chat/` request:

- `tool_trace`, `trace_id`, `latency_ms`, token totals
- Durable Postgres: `AgentRun`, `LlmCall`, `ToolCall`
- Admin UI at `/observability` (admin only)
- Structured logs (`acme.llm`, `acme.observability`)
- **LangSmith** (optional): LangGraph/LangChain run traces when enabled via env

### LangSmith

Agent runs (`create_react_agent`) are traced to [LangSmith](https://smith.langchain.com) when these are set in `backend/.env`:

```bash
LANGCHAIN_TRACING_V2=true
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_…
LANGSMITH_PROJECT=acme-operations
# optional
# LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

No code changes required — LangChain reads these from the environment. Restart the backend after editing `.env`. Keep the API key out of git.

Chat UX: conversation list/resume, Markdown replies, expandable Markdown/JSON on Observability.

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

## Deliverables map

| Pack item | Where |
|-----------|--------|
| Code + Compose | this repo |
| README / architecture diagram | this file (mermaid above) |
| Eval results + commentary | [`backend/evals/RESULTS.md`](backend/evals/RESULTS.md) + local `evals/results/` |
| AI usage notes | section below |

## AI tool usage notes (assessment)

### How AI was used

Cursor (AI coding assistants) was used throughout this case study as a **pair-programming accelerator**, not as an unsupervised code generator. The working loop was:

1. **Design first** — stack, folder layout, libs, and patterns were decided up front (often sketched or iterated in chat).
2. **Implement with AI** — scaffolding and boilerplate were generated against that design.
3. **Review and reshape by hand** — every meaningful chunk was read, tested, and changed where the design or product rules needed to win.

### What stayed human-owned

- **Backend shape**: Python / Django + DRF, app split (`core` vs `issues`), service-based OOP (thin views → services → models), RBAC helpers living **per app** (`core/permissions.py`, `issues/permissions.py`) rather than one dumping ground.
- **Agent design**: LangGraph ReAct orchestrator, tool contracts, prompts, Skills vs tools, Redis memory + Postgres as source of truth, MCP as an adapter over the same domain services.
- **Frontend shape**: React + TypeScript, feature folders, React Hook Form for forms, TanStack Query for server state, shared widgets (`CustomModal`, `TextField`), create/edit forms keyed by optional `id`.
- **Product / security choices**: Keycloak-only identities (no local `users` table), admin vs support vs sales gates, delete confirmations, “don’t delete customers with open issues”, eval harness and honesty about MCP’s synthetic admin user.

### What AI sped up

Scaffolding services, serializers/views, MCP wiring, UI pages/modals, unit/API tests, Docker/env glue, and first-pass wording for docs. AI was also useful for exploring options (e.g. permission layout, history windowing, observability models) before committing to one approach.

### Guardrails

LLM outputs inside the product (summarise / next-action / escalation) are treated as **assistive** and grounded only on tool-fetched context. Secrets never belong in git; API keys stay in local `.env`. Eval failures (model IDs, partial customer names, keyword search) were chased down and fixed with human judgment, not accepted as “the model said so.”
