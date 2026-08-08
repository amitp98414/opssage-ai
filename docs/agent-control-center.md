# OpsSage AI Agent Control Center

## Phase 1

This phase adds the first Control Center layer without changing the existing agent contract.

### Components

- `app/services/control_center.py` — in-memory lifecycle event store.
- `app/api/control_center_routes.py` — non-sensitive status and event endpoints.
- `app/services/agent_service.py` — emits started, completed and failed task events.
- `app/static/control-center.html` — futuristic command-center UI.
- `app/static/control-center.css` — responsive visual system.
- `app/static/control-center.js` — live polling and agent execution client.

### Endpoints

- `GET /control-center` — Control Center UI.
- `GET /control/status` — non-sensitive control-plane status.
- `GET /control/events` — recent lifecycle events.
- `POST /agent/run` — existing protected AI execution endpoint.

### Security note

The browser stores the execution API key only in `sessionStorage` for the current browser session. This is acceptable for the local development control center, but it is not the final enterprise authentication design. The production version will use the existing authenticated workspace/RBAC model and server-side authorization.

### Next phase

Add a durable task model, WebSocket/SSE event streaming, explicit tool registry, tool approval gates and real DevOps diagnostic tools.
