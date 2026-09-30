# AI Engineering Company Project — Student Template

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Base template for transversal projects in the AI Engineering Career Program — 4Geeks Academy._

> _Instrucciones disponibles en español en [README.es.md](./README.es.md)._

---

## Purpose

This repository is the **starter template** for transversal projects. You will work on real company scenarios (Brasaland, TrackFlow, Nexova), building deliverables that map to course milestones (Web, Programming, Backend, Telemetry, RAG, Agents, Workflows, Real-time).

- Create a template from this repository.
- Replace the placeholder `CONTEXT.md` with your assigned company context.
- Use `skills/` and the directory-level `README.md` files as working guidance.

---

## Current status of the template

The repository currently provides a **base folder structure and documentation skeleton**. It does not include runnable apps or global scripts yet.

- `CONTEXT.md` is a placeholder and must be replaced with your assigned company context.
- There is no root `AGENTS.md` yet.
- Shared package metadata exists in `packages/shared/package.json` (`@repo/shared-types`), but no workspace runner is configured at root.

---

## Repository structure

```text
ai-engineering-company-project-template/
├── README.md
├── README.es.md
├── CONTEXT.md                # Placeholder to be replaced with assigned context
├── agents/                   # Agent patterns/templates and tools docs
├── apps/                     # Product apps (web, APIs, dashboards)
├── data/                     # raw, process, pipelines, eval
├── docs/                     # Project and architecture documentation
├── packages/
│   └── shared/               # Shared package (@repo/shared-types)
├── scripts/                  # Script conventions/documentation
├── shared/                   # Shared assets/conventions at repo level
├── skills/                   # Reusable agent skills
└── workflows/                # Automation/orchestration documentation
```

---

## How to start

1. **Use this repository as a template** and create your own project repo.
2. **Clone** your repository (or open it in Codespaces).
3. **Replace** `CONTEXT.md` with the full context for your assigned company.
4. **Review** each top-level folder `README.md` to understand intended responsibilities (`apps/`, `data/`, `skills/`, etc.).
5. **Start implementing** milestone deliverables in `apps/`, reusing `packages/shared/` and `data/` as needed.

---

## Milestones (reference)

| Milestone | Focus        | Typical deliverables                        |
| --------- | ------------ | ------------------------------------------- |
| 0         | Prework      | Environment setup, first prompts            |
| 1         | Web          | Corporate website, forms, SEO               |
| 2         | Programming  | Business logic, scoring, calculations       |
| 3         | AI-driven UI | AI-generated interfaces                     |
| 4         | Next.js      | Portals, loyalty app, operations UI         |
| 5         | Backend      | Central API (locations, menus, sales, etc.) |
| 6         | Telemetry    | Data pipeline, dashboards                   |
| 7         | RAG & Memory | Semantic knowledge base, search             |
| 8         | Agents       | Support, onboarding, training agents        |
| 9         | Workflows    | n8n automations                             |
| 10        | Real-time    | Live dashboards, alerts, streaming          |

---

## Incident Analysis Worker

Incident CSV analysis is queued by FastAPI and executed by an independent Celery worker. The API stores each upload under `./data/incident_analysis` (mounted into both containers) and publishes only its generated file reference to Redis. Celery results are stored in Redis for 30 days; task ownership, an idempotency summary, and terminal failures are stored in the SQLModel database.

### Configuration

Copy `compose.env.example` to `.env`, replace `SECRET_KEY` with a random secret, and add non-default Flower credentials:

```dotenv
FLOWER_USER=your-operator-name
FLOWER_PASSWORD=use-a-long-random-password
```

Compose sets `REDIS_URL=redis://redis:6379/0` for the API, worker, and Flower. For processes started directly on the host, set `REDIS_URL=redis://localhost:6379/0` and `INCIDENT_UPLOAD_DIR=./data/incident_analysis`. API and worker must use the same `DATABASE_URL`; without it, Compose mounts their default SQLite database through `./data`.

### Start and Stop

Run the services independently:

```powershell
docker compose up -d redis
docker compose up -d backend
docker compose up -d worker
docker compose up -d flower
```

Stop one process without stopping the others:

```powershell
docker compose stop backend
docker compose stop worker
docker compose stop flower
docker compose stop redis
```

Redis uses AOF persistence and `maxmemory-policy noeviction`, so pending messages survive service restarts while Redis remains available. Flower is at `http://localhost:5555` and requires the configured username and password. Its worker event stream shows queued, active, completed, and failed tasks.

### Task and Failure Policy

`POST /api/incidents/analyze` returns `202` and a `task_id`; authenticated clients poll `GET /tasks/{task_id}` and export successful results with `GET /api/incidents/results/export?task_id=...`. Only the owner can read or export a task.

The worker retries transient storage `OSError` and SQLAlchemy `OperationalError`/`InterfaceError` failures with exponential delays of 2, 4, and 8 seconds. CSV validation errors and database errors while writing the DLQ are not retried. `max_retries=3` means one initial attempt plus three retries; a retry-exhausted failure is recorded as attempt 4 in `incident_analysis_dead_letters`, keyed by `task_id`, with the complete error message and UTC timestamp. A non-retryable terminal failure is recorded as attempt 1.

## Links

- [4Geeks Academy — AI Engineering](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [How to start a coding project](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contributors

This template was built as part of the 4Geeks Academy AI Engineering Career Program by [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) and [@alezanchezr](https://x.com/alesanchezr) and many other contributors. Find out more about our [AI Engineering Course](https://4geeksacademy.com/en/career-programs/ai-engineering), and [other courses](https://4geeksacademy.com/en/program-comparison).

You can find other templates and resources like this at the [4Geeks Academy GitHub page](https://github.com/4geeksacademy).

_This template is maintained by 4Geeks Academy for the AI Engineering track. For exclusive use in the programme._
