# OpsSage AI — Portable AI Deployment

## Goal

OpsSage AI can run with either a hosted AI provider or a local Ollama model. The application image stays the same; deployment changes are driven by environment variables.

## Supported modes

| Mode | AI runtime | Best use |
|---|---|---|
| Local / on-prem | Ollama | Privacy, low recurring inference cost |
| VPS / dedicated server | Ollama | Production self-hosting |
| Cloud CPU | OpenAI or another supported hosted provider | Simple deployment |
| Cloud GPU | Ollama | Self-hosted inference at scale |
| Docker-compatible platforms | OpenAI or Ollama where resources permit | Portable application deployment |

The key design principle is **container portability**. We do not create a separate application for AWS, Azure, GCP, Render, Railway, or a local PC. We build one application image and provide platform-specific infrastructure configuration around it.

## Local AI quick start

Requirements:

- Docker Engine
- Docker Compose v2
- At least 8 GB RAM for the default small model; more RAM is recommended for larger models

From the repository root:

```bash
cp .env.example .env
```

Replace the two application secrets with long random values, then run:

```bash
docker compose -f docker-compose.local-ai.yml up --build
```

The stack contains:

- `backend` — FastAPI application
- `ollama` — local model runtime
- `ollama-model-init` — one-time model download

Check the API:

```bash
curl http://localhost:8000/health
```

Expected shape:

```json
{
  "status": "healthy",
  "application": "OpsSage AI",
  "version": "2.0.0",
  "ai_provider": "ollama"
}
```

Test inference:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Explain Docker health checks in two sentences."}'
```

## Switching to hosted AI

Keep the same backend image and set:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4.1-mini
```

For a hosted deployment, use the normal `docker-compose.yml` or the platform's Docker deployment configuration. Do not expose `OPENAI_API_KEY` in source control.

## Deployment strategy

### Phase 1 — local proof of concept

Validate one machine with Ollama and the 3B model.

### Phase 2 — multi-machine cluster

Run independent workers on separate machines and route jobs through a queue. Do not treat multiple old PCs as one GPU; distribute jobs between workers.

### Phase 3 — production

Add PostgreSQL, Redis, HTTPS, centralized logs, metrics, backups, secret management, authentication hardening, and automated CI/CD.

### Phase 4 — commercial service

Add tenant isolation, per-client usage accounting, approval workflows, audit logs, billing, quotas, and SLA monitoring.

## Important limitation

"Deploy on every platform" does not mean every platform can efficiently run local LLM inference. CPU-only PaaS services can run the FastAPI control plane, while GPU/local inference should run on a suitable host. The provider abstraction lets us keep the same product while changing the inference location.
