# Backend (Django + DRF)

Apps:

- `config/` — settings, root URLconf
- `core/` — auth, chat agent, conversations, observability, skills, MCP bootstrap helpers
- `issues/` — customers, issues, timeline notes, next actions
- `evals/` — evaluation narrative (`RESULTS.md`); raw harness output is gitignored
- `mcp_server/` — FastMCP process exposing the same domain tools

## Layout rules

- Business logic lives in `*/services/`
- Role helpers: `core/permissions.py` (shared) and `issues/permissions.py` (issue RBAC)
- JWT authentication: `core/authentication.py`
- Views stay thin: validate → service → response

## Commands

```bash
# from backend/ with venv + Postgres available
python manage.py migrate
python manage.py seed_data
python manage.py test
python manage.py eval_agent --provider anthropic
python manage.py run_agent_smoke
```

Docker: `docker compose up --build` from the repo root (see root README).

## API surface (`/api/`)

| Method | Path | Who | Notes |
|--------|------|-----|-------|
| GET | `/health/` | public | Process + Keycloak + Redis |
| GET | `/me/` | authenticated | JWT identity + roles |
| POST | `/chat/` | assistant roles | Agent turn; optional `conversation_id` / eval `session_id` |
| GET/POST | `/conversations/` | assistant roles | List / create |
| GET/DELETE | `/conversations/:id/` | owner | Detail / delete |
| GET/POST | `/issues/` | assistant; **POST admin** | List visible / create |
| GET/PATCH/DELETE | `/issues/:id/` | GET any visible; PATCH support+admin; DELETE admin | |
| POST | `/issues/:id/updates/` | support+admin | Timeline note |
| GET/POST | `/customers/` | assistant; **POST admin** | List / create |
| GET/PATCH/DELETE | `/customers/:id/` | GET assistant; mutations admin | Cannot delete if issues remain |
| GET | `/agent/tools/` | assistant roles | Debug/eval tool specs |
| POST | `/agent/tools/call/` | assistant roles | Debug/eval single tool invoke |
| GET | `/admin/runs/` | admin | Observability list |
| GET | `/admin/runs/:id/` | admin | Observability detail |

## Auth notes

- Identities/roles come from Keycloak JWTs (no local `users` table).
- Access-token `aud` is often the account client; we verify signature + issuer, then enforce client via `azp`/`aud`.
- MCP tools run as a synthetic admin user for local demos — not a production multi-tenant pattern.
