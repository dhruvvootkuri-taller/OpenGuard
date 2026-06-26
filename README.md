# 🛡️ Open Guard

**Open Guard** is an AI-powered physical security monitoring and alerting
platform. It watches camera feeds with **OpenCV**, assesses threats, generates
human-readable incident summaries with **Claude Haiku**, and escalates serious
events to an on-call operator via **ElevenLabs** voice synthesis over a
**Twilio** phone call. Live events stream to a **React** dashboard, with
**Redis** providing fast persistence and real-time pub/sub.

---

## Tech Stack

| Concern              | Technology        |
| -------------------- | ----------------- |
| Backend language     | Python 3.11 (FastAPI) |
| Frontend             | React + TypeScript (Vite) |
| Vision / detection   | OpenCV            |
| LLM reasoning        | Claude Haiku (Anthropic) |
| Voice synthesis      | ElevenLabs        |
| Telephony (calls/SMS)| Twilio            |
| Persistence + pub/sub| Redis             |

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
| **Infrastructure** | `src/infrastructure/` | Concrete implementations: Redis, Claude Haiku, ElevenLabs, Twilio, OpenCV, config. | `domain`, `application` |
| **Interfaces** | `src/interfaces/` | Entry points: FastAPI controllers, CLI, the monitoring agent. Thin adapters. | `application` |

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
├── main.py                              # Composition root (wires all layers)
├── domain/
│   ├── entities/security_event.py       # Entity w/ invariants + lifecycle
│   ├── value_objects/threat_level.py    # Immutable value object
│   ├── value_objects/detection_box.py
│   ├── services/threat_assessment_service.py  # Pure business logic
│   └── repositories/security_event_repository.py  # Interface (the "what")
├── application/
│   ├── use_cases/process_detection_use_case.py    # execute(dto)
│   ├── use_cases/acknowledge_event_use_case.py
│   ├── ports/llm_port.py                # Abstraction for Claude Haiku
│   ├── ports/notification_port.py       # Abstractions for ElevenLabs + Twilio
│   └── dtos/detection_dtos.py
├── infrastructure/
│   ├── persistence/redis_security_event_repository.py  # implements domain interface
│   ├── llm/claude_haiku_client.py
│   ├── voice/elevenlabs_voice_client.py
│   ├── telephony/twilio_telephony_client.py
│   ├── vision/opencv_detector.py
│   └── container.py                     # DI container
└── interfaces/
    ├── http/app.py + controllers/       # FastAPI controllers (call use cases)
    ├── agent/guard_agent.py             # Live monitoring loop
    └── cli/run_agent.py                 # CLI entry point
```

The **composition root** (`src/main.py`) is the single place permitted to know
about every layer — it builds the infrastructure `Container` and injects use
cases into the interface controllers.

---

## Getting Started

### Prerequisites

- Python 3.11+
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

### 3. Frontend

```bash
cd frontend
npm install
npm run dev           # -> http://localhost:5173 (proxies /api to :8000)
```

### 4. Run the live monitoring agent (optional)

```bash
make agent
# or:
python -m src.interfaces.cli.run_agent --camera-id front-door --source 0
```

### Run with Docker

```bash
docker compose up --build
```

---

## API

| Method | Path                              | Description                       |
| ------ | --------------------------------- | --------------------------------- |
| GET    | `/health`                         | Service health check              |
| POST   | `/api/events`                     | Process a detection → event       |
| GET    | `/api/events`                     | List recent events                |
| POST   | `/api/events/{id}/acknowledge`    | Acknowledge an event              |

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

A high/critical threat will be persisted to Redis, summarized by Claude Haiku,
synthesized to voice by ElevenLabs, and escalated via a Twilio call.

---

## Development

```bash
make test     # pytest (domain + application unit tests, no external services)
make lint     # ruff
make format   # black + ruff --fix
```

Domain and application layers are tested in isolation using in-memory fakes for
all ports — no Redis/Twilio/Anthropic credentials required to run the suite.

---

## License

MIT
