# OpsSage AI — Production Architecture

## Design principle

One application, multiple inference backends and multiple deployment targets.

```text
                         Internet / Client
                                |
                              HTTPS
                                |
                         Reverse Proxy
                                |
                         OpsSage FastAPI
                                |
                  +-------------+-------------+
                  |                           |
            Auth / Tenant               Workflow API
                  |                           |
                  +-------------+-------------+
                                |
                         Job Router / Queue
                                |
              +-----------------+-----------------+
              |                 |                 |
          Support Worker   Document Worker   DevOps Worker
              |                 |                 |
              +-----------------+-----------------+
                                |
                    +-----------+-----------+
                    |                       |
                Cloud AI                Local AI
                 Provider                Ollama
                    |                       |
                    +-----------+-----------+
                                |
                         Result / Approval
                                |
                     Audit + Usage Metering
                                |
                    PostgreSQL + Redis
                                |
                    Prometheus + Grafana
```

## Deployment targets

The application container is the portable unit. Configuration selects infrastructure and AI provider.

```text
Docker Compose -> VPS -> AWS/Azure/GCP -> dedicated GPU workers
```

No application code should contain provider-specific business logic. Provider integrations belong behind the AI service interface.

## Local AI

`docker-compose.local-ai.yml` runs the FastAPI backend with Ollama and a configurable model. The default model is intentionally small for development and low-resource machines.

## Cloud AI

The existing OpenAI integration remains available through `AI_PROVIDER=openai`. API keys must be supplied through the deployment secret manager or environment, never through Git.

## Security boundaries

- TLS terminates at the reverse proxy/load balancer.
- Authentication and tenant authorization are enforced by the API.
- AI workers receive only the minimum data required for a job.
- Consequential external actions require explicit workflow policy and, where appropriate, human approval.
- Logs must avoid passwords, tokens, API keys and unnecessary customer content.

## Reliability

The workflow engine will use durable jobs, retries with backoff, idempotency keys and dead-letter handling. A failed worker must not silently lose a customer job.

## Scalability

Scale the stateless API horizontally. Scale workers independently by workload. GPU workers can be added without changing the customer-facing API.
