from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.workspace_routes import router as workspace_router
from app.api.agent_routes import router as agent_router
from app.api.auth_routes import router as auth_router
from app.api.control_center_routes import router as control_center_router
from app.api.login_routes import router as login_router
from app.api.subscription_routes import router as subscription_router
from app.core.config import settings
from app.core.database import init_db
from app.core.security import enforce_rate_limit
from app.services.openai_service import ask_ai


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "OpsSage AI for DevOps diagnostics, observability and "
        "authorized security assistance."
    ),
    lifespan=lifespan,
)

# API routers are registered together to avoid accidental omission.
app.include_router(agent_router)
app.include_router(control_center_router)
app.include_router(auth_router)
app.include_router(login_router)
app.include_router(subscription_router)
app.include_router(workspace_router)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


class ChatRequest(BaseModel):
    prompt: str


@app.get("/")
def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "agent_endpoint": "/agent/run",
        "control_center": "/control-center",
        "control_status": "/control/status",
        "control_events": "/control/events",
        "signup_endpoint": "/auth/signup",
        "login_endpoint": "/auth/login",
        "subscription_endpoint": "/subscriptions",
        "documentation": "/docs",
    }


@app.get("/demo", include_in_schema=False)
def demo():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/control-center", include_in_schema=False)
def control_center():
    return FileResponse(STATIC_DIR / "control-center.html")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.post("/chat")
def chat(
    request: ChatRequest,
    _: str = Depends(enforce_rate_limit),
):
    return {"response": ask_ai(request.prompt)}


Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
)
