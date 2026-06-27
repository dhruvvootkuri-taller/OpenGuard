# 🛡️ Open Guard

**Open Guard** is an AI-powered physical security monitoring and alerting
platform. It watches camera feeds with **OpenCV**, assesses threats, generates
human-readable incident summaries with **Claude Haiku**, and escalates serious
events to an on-call operator via **ElevenLabs** voice synthesis over a
**Twilio** phone call. The slow escalation pipeline runs out-of-band on
**Celery** workers so the request path stays fast. Live events stream to a
**React** dashboard, with **Redis** providing fast persistence, pub/sub, and
the Celery broker/result backend.

---

## Tech Stack

| Concern                  | Technology                    |
| ------------------------ | ----------------------------- |
| Backend language         | Python 3.11 (FastAPI)         |
| Frontend                 | React + TypeScript (Vite)     |
| Vision / detection       | OpenCV                        |
| LLM reasoning            | Claude Haiku (Anthropic)      |
| Voice synthesis          | ElevenLabs                    |
| Telephony (calls/SMS)    | Twilio                        |
| Background task queue    | Celery                        |
| Persistence + pub/sub + broker | Redis                   |

---

## Architecture — Clean Architecture

This project follows **Clean Architecture**. Dependencies only ever point
**inward**. Business rules sit at the center and know nothing about frameworks,
databases, or external APIs.

```
interfaces  ──►  application  ──►  domain
infrastructure ─►  application  ──►  domain
```

### The four layers

| Layer | Path | Responsibility | May import |
| ----- | ---- | -------------- | ---------- |
| **Domain** | `src/domain/` | Entities, value objects, domain services, repository **interfaces**. Pure business rules. | Nothing outside itself |
| **Application** | `src/application/` | Use cases (`execute(dto)`), DTOs, mappers, and **port** interfaces for infrastructure. Orchestration only. | `domain` |
| **Infrastructure** | `src/infrastructure/` | Concrete implementations: Redis, Celery, Claude Haiku, ElevenLabs, Twilio, OpenCV, config. | `domain`, `application` |
| **Interfaces** | `src/interfaces/` | Entry points: FastAPI controllers, CLI, the monitoring agent, the Celery worker. Thin adapters. | `application` |

The **dependency rule is absolute**:

- `domain/` imports **nothing** from outside itself.
- `application/` imports **only** from `domain/`.
- `infrastructure/` implements interfaces declared in `domain/`/`application/`.
- `interfaces/` orchestrates use cases and contains **no business logic**.

> Each layer has its own `CLAUDE.md` describing exactly what belongs there.
> See `CLAUDE.md` (root) and `architecture.json` for the machine-readable rules.

### Where things live (concrete examples)

```
src/
├── main.py                              # Composition root for the API (wires all layers)
├── worker.py                            # Composition root for the Celery worker
├── domain/
│   ├── entities/security_event.py       # Entity w/ invariants + lifecycle
│   ├── value_objects/threat_level.py    # Immutable value object
│   ├── value_objects/detection_box.py
│   ├── services/threat_assessment_service.py  # Pure business logic
│   └── repositories/security_event_repository.py  # Interface (the "what")
├── application/
│   ├── use_cases/process_detection_use_case.py    # execute(dto) — fast path
│   ├── use_cases/escalate_event_use_case.py       # slow path (runs on worker)
│   ├── use_cases/acknowledge_event_use_case.py
│   ├── ports/llm_port.py                # Abstraction for Claude Haiku
│   ├── ports/notification_port.py       # Abstractions for ElevenLabs + Twilio
│   ├── ports/task_queue_port.py         # Abstraction for Celery
│   └── dtos/detection_dtos.py
├── infrastructure/
│   ├── persistence/redis_security_event_repository.py  # implements domain interface
│   ├── llm/claude_haiku_client.py
│   ├── voice/elevenlabs_voice_client.py
│   ├── telephony/twilio_telephony_client.py
│   ├── vision/opencv_detector.py
│   ├── tasks/celery_app.py              # Celery app (Redis broker/backend)
│   ├── tasks/celery_task_queue.py       # implements TaskQueuePort
│   ├── tasks/escalation_tasks.py        # Celery tasks → run use cases
│   └── container.py                     # DI container
└── interfaces/
    ├── http/app.py + controllers/       # FastAPI controllers (call use cases)
    ├── agent/guard_agent.py             # Live monitoring loop
    ├── worker/celery_worker.py          # Celery worker interface adapter
    └── cli/run_agent.py                 # CLI entry point
```

The **composition roots** (`src/main.py` for the API, `src/worker.py` for the
Celery worker) are the only modules permitted to know about every layer — they
build the infrastructure `Container` and wire concrete adapters into use cases.

### Request flow

1. A detection arrives (`POST /api/events` or the live OpenCV agent).
2. `ProcessDetectionUseCase` assesses the threat (domain), **persists** the
   event to Redis, and **publishes** it — fast, synchronous path.
3. If the domain says the threat requires human escalation, the use case
   **enqueues** an escalation job via the `TaskQueuePort` (Celery).
4. A **Celery worker** picks up the job and runs `EscalateEventUseCase`:
   Claude Haiku writes a summary → ElevenLabs synthesizes voice → Twilio places
   the call. The event is re-persisted and re-published.

Because the heavy I/O runs on the worker, the API/agent never blocks on the
LLM, TTS, or telephony providers.

---

## Getting Started

### Prerequisites

- Python 3.9+ (3.11 recommended)
- Node.js 18+
- Redis (local or via Docker)
- API keys for Anthropic, ElevenLabs, and Twilio

### 1. Configure environment

```bash
cp .env.example .env
# then fill in your API keys and phone numbers
```

### 2. Backend

```bash
# create a virtualenv, then:
make install          # pip install -r requirements-dev.txt
make run              # uvicorn src.main:app --reload  -> http://localhost:8000
```

API docs are available at `http://localhost:8000/docs`.

### 3. Celery worker (required for escalation)

In a separate terminal (with Redis running):

```bash
make worker
# or:
celery -A src.worker:celery_app worker --loglevel=info
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev           # -> http://localhost:5173 (proxies /api to :8000)
```

### 5. Run the live monitoring agent (optional)

```bash
make agent
# or:
python -m src.interfaces.cli.run_agent --camera-id front-door --source 0
```

### Run with Docker

```bash
docker compose up --build
```

This brings up Redis, the API, and the Celery worker together.

---

## API

| Method | Path                              | Description                       |
| ------ | --------------------------------- | --------------------------------- |
| GET    | `/health`                         | Service health check              |
| POST   | `/api/events`                     | Process a detection → event       |
| GET    | `/api/events`                     | List recent events                |
| POST   | `/api/events/{id}/acknowledge`    | Acknowledge an event              |
| POST   | `/api/feeds/{camera_id}/frame`    | Assess one MP4 frame with Claude vision → event |

Example:

```bash
curl -X POST http://localhost:8000/api/events \
  -H 'Content-Type: application/json' \
  -d '{
        "camera_id": "front-door",
        "is_armed_zone": true,
        "detections": [
          {"label": "knife", "confidence": 0.95,
           "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}
        ]
      }'
```

A high/critical threat is persisted to Redis immediately, then a Celery worker
summarizes it with Claude Haiku, synthesizes voice via ElevenLabs, and
escalates via a Twilio call.

---

## MP4 camera-feed end-to-end test (browser)

Each `VideoMonitor` tile on the dashboard captures a frame from a playing MP4
(via a `<canvas>`) every ~5s and POSTs it to
`POST /api/feeds/{camera_id}/frame`. Claude **vision** assesses the frame; when
it returns `is_emergency: true` the backend creates a `SecurityEvent` that
appears in the Emergency Log. A calm frame returns `is_emergency: false` and
nothing is persisted — playback is never interrupted.

### Required env vars

| Variable                 | Purpose                                              |
| ------------------------ | ---------------------------------------------------- |
| `ANTHROPIC_API_KEY`      | Anthropic key used for both Haiku and vision         |
| `ANTHROPIC_VISION_MODEL` | Vision model for frame analysis. **Defaults to `claude-3-5-sonnet-latest`** — must be a *current* model (the old `claude-3-5-sonnet-20241022` was retired 2025-10-28 and 404s every frame) |
| `REDIS_URL`              | Redis connection (persistence + pub/sub)             |

> A bad API key or retired model is **logged and surfaced as HTTP 502** by the
> frame endpoint — it is never silently treated as "all clear".

### Run it

```bash
# 1. Redis (Docker or local)
docker run -p 6379:6379 redis:7        # or: redis-server

# 2. Backend (Python 3.9+ supported)
cp .env.example .env                   # fill in ANTHROPIC_API_KEY
uvicorn src.main:app --reload          # -> http://localhost:8000  (/health = 200)

# 3. Frontend
cd frontend && npm install && npm run dev   # -> http://localhost:5173 (proxies /api → :8000)
```

Then open `http://localhost:5173`, drop an MP4 into a monitor tile, and press
play. Watch the browser **Network** tab for `POST /api/feeds/CAM-01/frame`
calls and the backend logs for the vision assessments. An emergency clip raises
a new event in the Emergency Log within one poll cycle (~5s) with a severity
and bounding box; a calm clip leaves the log untouched.

> **Python 3.9 note:** the API boots on Python 3.9+. Response schemas use
> `Optional[...]` (never a quoted PEP-604 union + `model_rebuild()`, which
> raises `TypeError` on 3.9). This is covered by `tests/interfaces/test_app_boot.py`.

---

## Development

```bash
make test     # pytest (domain + application unit tests, no external services)
make lint     # ruff
make format   # black + ruff --fix
```

Domain and application layers are tested in isolation using in-memory fakes for
all ports — including the Celery task queue — so no Redis/Twilio/Anthropic
credentials are required to run the suite.

---

## License

MIT
