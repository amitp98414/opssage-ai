# OpsSage AI — Product Roadmap

## Vision

Build a production-grade AI automation platform that can run with cloud or local models, deploy on a developer workstation, VPS, or major cloud provider, and automate measurable business workflows.

## North-star business objective

Reach product-market fit first; then scale recurring revenue. A long-term target is ₹1 crore+ annual revenue, but no revenue outcome is assumed or guaranteed.

## Target customers

- Small and medium businesses with repetitive support and back-office workflows
- Agencies and service businesses handling high email/document volume
- DevOps teams that need operational diagnostics and automation

## Initial wedge

1. AI inbox triage and reply drafting
2. Document/invoice extraction
3. Human-approved workflow automation

## Product architecture

```text
Client / SaaS UI
      |
      v
API Gateway / FastAPI
      |
      v
Authentication + Tenant isolation
      |
      v
Workflow / Job Router
      |
      +------------------+
      |                  |
      v                  v
Cloud AI            Local AI
Provider            Ollama
      |                  |
      +---------+--------+
                |
                v
          Worker Runtime
                |
       +--------+--------+
       |        |        |
    Support  Documents  DevOps
       |        |        |
       +--------+--------+
                |
                v
       Audit + Usage Metering
                |
                v
       PostgreSQL / Redis
                |
                v
     Prometheus + Grafana
```

## Deployment strategy

The application should remain provider- and platform-portable:

- Docker Compose for local development
- Local Ollama for private inference
- VPS deployment
- AWS deployment
- Azure deployment
- GCP deployment
- Dedicated GPU worker deployment
- Cloud AI provider fallback

## Phases

### Phase 1 — Foundation

- [x] AI provider abstraction
- [x] OpenAI provider retained
- [x] Ollama provider added
- [x] Local AI Docker Compose stack
- [ ] Automated integration tests for both providers
- [ ] Production configuration validation

### Phase 2 — Workflow engine

- [ ] Redis-backed job queue
- [ ] Worker registration
- [ ] Retry and dead-letter handling
- [ ] Job status API
- [ ] Idempotency keys
- [ ] Audit trail

### Phase 3 — First sellable workflow

- [ ] Inbox ingestion
- [ ] Email classification
- [ ] Reply drafting
- [ ] Confidence scoring
- [ ] Human approval
- [ ] Provider-independent execution

### Phase 4 — Documents

- [ ] File upload pipeline
- [ ] OCR integration
- [ ] Invoice extraction
- [ ] Structured validation
- [ ] Export/integration APIs

### Phase 5 — SaaS

- [ ] Multi-tenancy hardening
- [ ] Usage metering
- [ ] Subscription plans
- [ ] Billing integration
- [ ] Customer admin dashboard
- [ ] API keys and quotas

### Phase 6 — Production scale

- [ ] PostgreSQL production configuration
- [ ] Redis production configuration
- [ ] Object storage
- [ ] Horizontal workers
- [ ] GPU worker pool
- [ ] Observability and alerting
- [ ] Backup and disaster recovery

### Phase 7 — Distribution

- [ ] Public landing page
- [ ] Product demo
- [ ] Customer onboarding
- [ ] Case studies
- [ ] Sales pipeline
- [ ] Referral/partner channel

## Business model

Start with outcome-based service pricing while validating workflows. Move successful workflows into standardized SaaS plans.

Example validation tiers:

- Starter: low-volume automation
- Business: multi-workflow automation
- Enterprise: private deployment, custom integrations, stronger controls

Pricing must be validated against customer ROI, inference cost, infrastructure cost, support time, and retention rather than assumed from competitor pricing.

## Engineering standards

- Secrets never committed to Git
- Tenant data isolation
- Least-privilege credentials
- Human approval for consequential outbound actions
- Structured logging without sensitive payload leakage
- Automated tests before production deployment
- CI/CD for every release
- Dependency and container scanning
- Rate limiting and abuse controls
- Backups and recovery testing

## Success metrics

### Product

- Workflow completion rate
- Human approval rate
- AI correction rate
- Median and p95 execution latency
- Job failure rate

### Business

- Activated customers
- Paying customers
- Monthly recurring revenue
- Gross margin
- Churn
- Customer acquisition cost
- Customer lifetime value

## First milestone

Get one complete local AI workflow working end-to-end, measure its reliability and cost, then deploy the same codebase to a VPS without changing application logic.
