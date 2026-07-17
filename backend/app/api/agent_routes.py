from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.agent_service import execute_agent


router = APIRouter(
    prefix="/agent",
    tags=["OpsSage AI Agent"],
)


class AgentRunRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=12000,
    )
    mode: Literal["auto", "devops", "bugbounty"] = "auto"


@router.get("/modes")
def list_agent_modes():
    return {
        "modes": {
            "auto": "Orchestrator automatically selects a specialist",
            "devops": "Ubuntu, Docker, Git and infrastructure specialist",
            "bugbounty": "Authorized bug-bounty analysis specialist",
        }
    }


@router.post("/run")
async def run_agent(request: AgentRunRequest):
    try:
        return await execute_agent(
            prompt=request.prompt,
            mode=request.mode,
        )
    except Exception as exc:
        print(f"Agent execution failed: {type(exc).__name__}: {exc}")

        raise HTTPException(
            status_code=500,
            detail=(
                "Agent execute nahi ho saka. Backend terminal logs check karo. "
                "API key, model name aur internet connection verify karo."
            ),
        ) from exc
