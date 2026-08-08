from __future__ import annotations

from typing import Literal
from uuid import uuid4

from agents import Runner

from app.agents.bugbounty_agent import bugbounty_agent
from app.agents.devops_agent import devops_agent
from app.agents.orchestrator import orchestrator_agent
from app.services.control_center import add_event


AgentMode = Literal["auto", "devops", "bugbounty"]


AGENTS = {
    "auto": orchestrator_agent,
    "devops": devops_agent,
    "bugbounty": bugbounty_agent,
}


async def execute_agent(
    prompt: str,
    mode: AgentMode = "auto",
) -> dict[str, str]:
    starting_agent = AGENTS[mode]
    task_id = str(uuid4())

    add_event(
        event_type="task.started",
        status="running",
        message="Agent task accepted by the Control Center.",
        agent=starting_agent.name,
        task_id=task_id,
    )

    try:
        result = await Runner.run(
            starting_agent,
            prompt,
            max_turns=8,
        )
    except Exception as exc:
        add_event(
            event_type="task.failed",
            status="failed",
            message=f"Agent task failed: {type(exc).__name__}",
            agent=starting_agent.name,
            task_id=task_id,
        )
        raise

    final_agent = result.last_agent.name
    add_event(
        event_type="task.completed",
        status="success",
        message="Agent task completed successfully.",
        agent=final_agent,
        task_id=task_id,
    )

    return {
        "task_id": task_id,
        "mode": mode,
        "agent": final_agent,
        "answer": str(result.final_output),
    }
