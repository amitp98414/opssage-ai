#!/usr/bin/env bash
set -euo pipefail

echo "Creating OpsSage Agent MVP..."

mkdir -p backend/app/{api,agents,tools}
touch backend/app/api/__init__.py
touch backend/app/agents/__init__.py
touch backend/app/tools/__init__.py

# OpenAI Agents SDK dependency
if ! grep -qE '^openai-agents([<>=].*)?$' backend/requirements.txt; then
    echo "openai-agents" >> backend/requirements.txt
fi

# ---------------- SAFE UBUNTU TOOL ----------------
cat > backend/app/tools/safe_system.py <<'PY'
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from agents import function_tool


CheckName = Literal[
    "os",
    "uptime",
    "disk",
    "memory",
    "git_status",
    "docker_ps",
    "compose_ps",
]


COMMANDS: dict[str, list[str]] = {
    "os": ["uname", "-a"],
    "uptime": ["uptime"],
    "disk": ["df", "-h"],
    "memory": ["free", "-m"],
    "git_status": ["git", "status", "--short", "--branch"],
    "docker_ps": [
        "docker",
        "ps",
        "--format",
        "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}",
    ],
    "compose_ps": ["docker", "compose", "ps"],
}


def _find_project_directory() -> Path:
    current_file = Path(__file__).resolve()

    for parent in current_file.parents:
        if (parent / ".git").exists():
            return parent

    return Path.cwd()


@function_tool
def ubuntu_readonly_check(check: CheckName) -> str:
    """
    Run one approved read-only Ubuntu or DevOps diagnostic check.

    Available checks:
    os, uptime, disk, memory, git_status, docker_ps and compose_ps.
    This tool cannot accept or execute arbitrary shell commands.
    """
    command = COMMANDS[check]

    try:
        result = subprocess.run(
            command,
            cwd=_find_project_directory(),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return (
            f"Tool unavailable: '{command[0]}' command installed nahi hai "
            "ya PATH me available nahi hai."
        )
    except subprocess.TimeoutExpired:
        return "Command 20 seconds ke timeout ke baad stop kar diya gaya."
    except Exception as exc:
        return f"Safe diagnostic tool error: {type(exc).__name__}"

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    output_parts = [
        f"$ {' '.join(command)}",
        f"exit_code={result.returncode}",
    ]

    if stdout:
        output_parts.append(stdout)

    if stderr:
        output_parts.append(f"stderr:\n{stderr}")

    if not stdout and not stderr:
        output_parts.append("(no output)")

    return "\n".join(output_parts)[:12000]
PY

# ---------------- BUG BOUNTY SCOPE TOOL ----------------
cat > backend/app/tools/scope_tools.py <<'PY'
from __future__ import annotations

import re
from urllib.parse import urlparse

from agents import function_tool


def _extract_hostname(target: str) -> str:
    value = target.strip().lower()

    if "://" not in value:
        value = f"//{value}"

    parsed = urlparse(value)
    return (parsed.hostname or "").rstrip(".")


def _matches_scope(hostname: str, pattern: str) -> bool:
    normalized_pattern = pattern.strip().lower().rstrip(".")

    if not normalized_pattern:
        return False

    if normalized_pattern.startswith("*."):
        base_domain = normalized_pattern[2:]

        # Preliminary wildcard interpretation.
        return hostname.endswith(f".{base_domain}")

    return hostname == normalized_pattern


@function_tool
def check_bug_bounty_scope(
    target: str,
    allowed_scope: str,
) -> str:
    """
    Perform a preliminary target scope check.

    target:
        A hostname or URL such as api.example.com.

    allowed_scope:
        Comma or newline-separated scope entries, such as:
        example.com, *.example.com
    """
    hostname = _extract_hostname(target)

    if not hostname:
        return "Invalid target: hostname identify nahi ho saka."

    patterns = [
        value.strip()
        for value in re.split(r"[,\n]+", allowed_scope)
        if value.strip()
    ]

    if not patterns:
        return "Scope list empty hai. Program scope provide karo."

    matched_patterns = [
        pattern
        for pattern in patterns
        if _matches_scope(hostname, pattern)
    ]

    if matched_patterns:
        return (
            f"PRELIMINARY IN-SCOPE\n"
            f"Target: {hostname}\n"
            f"Matched entry: {matched_patterns[0]}\n\n"
            "Important: HackerOne/Bugcrowd program policy, exclusions, "
            "testing restrictions aur asset-specific rules manually verify karo."
        )

    return (
        f"NOT MATCHED\n"
        f"Target: {hostname}\n"
        f"Provided scope entries: {', '.join(patterns)}\n\n"
        "Is target par testing start mat karo jab tak program rules se "
        "written authorization confirm na ho."
    )
PY

# ---------------- DEVOPS AGENT ----------------
cat > backend/app/agents/devops_agent.py <<'PY'
from agents import Agent

from app.core.config import settings
from app.tools.safe_system import ubuntu_readonly_check


devops_agent = Agent(
    name="DevOps Specialist",
    handoff_description=(
        "Ubuntu, Linux, Docker, Git, CI/CD, deployment, server health "
        "aur infrastructure troubleshooting specialist."
    ),
    model=settings.OPENAI_MODEL,
    instructions="""
You are a careful senior DevOps diagnostic specialist.

Your environment is the user's authorized Ubuntu system.

Rules:
1. Reply in simple Hinglish with clear practical steps.
2. Use ubuntu_readonly_check whenever the user asks for current system facts.
3. Never invent terminal output.
4. Clearly distinguish:
   - what you actually checked using a tool;
   - what you are recommending.
5. The available tool only runs fixed read-only diagnostic commands.
6. Never claim that a service was restarted, package installed, file deleted,
   deployment changed or command executed unless a suitable tool actually did it.
7. For destructive or system-changing operations, explain the proposed command,
   risk and rollback first. User approval will be required in a future stage.
8. Never expose environment variables, API keys, tokens or credentials.
9. When diagnosing an error, explain:
   observation, likely cause, verification step and safe fix.
""",
    tools=[ubuntu_readonly_check],
)
PY

# ---------------- BUG BOUNTY AGENT ----------------
cat > backend/app/agents/bugbounty_agent.py <<'PY'
from agents import Agent

from app.core.config import settings
from app.tools.scope_tools import check_bug_bounty_scope


bugbounty_agent = Agent(
    name="Bug Bounty Specialist",
    handoff_description=(
        "Authorized bug-bounty scope review, HTTP analysis, testing checklist "
        "aur vulnerability report writing specialist."
    ),
    model=settings.OPENAI_MODEL,
    instructions="""
You are an authorized bug-bounty assistant.

Rules:
1. Reply in simple Hinglish with practical and understandable steps.
2. Work only on targets that the user is authorized to test.
3. Before target-specific testing advice, confirm:
   program name, target and scope.
4. Use check_bug_bounty_scope when the target and allowed scope are provided.
5. A scope-tool match is preliminary only. Program rules and exclusions remain
   the final source of truth.
6. Focus on safe work:
   scope parsing, passive analysis, HTTP request/response review,
   authentication-flow reasoning, secure test-case design,
   evidence organization and professional report writing.
7. Do not assist with destructive testing, denial of service, persistence,
   credential attacks, malware, data exfiltration or unauthorized access.
8. Never fabricate a vulnerability or impact.
9. Clearly label findings as:
   confirmed, likely, needs verification or false positive.
10. Do not submit any report automatically.
""",
    tools=[check_bug_bounty_scope],
)
PY

# ---------------- ORCHESTRATOR ----------------
cat > backend/app/agents/orchestrator.py <<'PY'
from agents import Agent

from app.agents.bugbounty_agent import bugbounty_agent
from app.agents.devops_agent import devops_agent
from app.core.config import settings


orchestrator_agent = Agent(
    name="BugOps Orchestrator",
    model=settings.OPENAI_MODEL,
    instructions="""
You are the main routing and planning agent for BugOps AI.

Your responsibility:
- Send Linux, Ubuntu, Docker, Git, CI/CD, Kubernetes, Terraform,
  cloud and infrastructure tasks to the DevOps Specialist.
- Send authorized bug-bounty, security scope, HTTP analysis and
  vulnerability reporting tasks to the Bug Bounty Specialist.
- When a request contains both areas, choose the specialist responsible
  for the immediate task.
- When required information is missing, ask one concise clarification.
- Never pretend that a tool or command was executed.
""",
    handoffs=[
        devops_agent,
        bugbounty_agent,
    ],
)
PY

# ---------------- AGENT SERVICE ----------------
cat > backend/app/services/agent_service.py <<'PY'
from __future__ import annotations

from typing import Literal

from agents import Runner

from app.agents.bugbounty_agent import bugbounty_agent
from app.agents.devops_agent import devops_agent
from app.agents.orchestrator import orchestrator_agent


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

    result = await Runner.run(
        starting_agent,
        prompt,
        max_turns=8,
    )

    return {
        "mode": mode,
        "agent": result.last_agent.name,
        "answer": str(result.final_output),
    }
PY

# ---------------- API ROUTE ----------------
cat > backend/app/api/agent_routes.py <<'PY'
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
PY

# ---------------- UPDATED FASTAPI APP ----------------
cat > backend/app/main.py <<'PY'
from fastapi import FastAPI
from pydantic import BaseModel

from app.api.agent_routes import router as agent_router
from app.core.config import settings
from app.services.openai_service import ask_ai


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "OpsSage AI Agent for DevOps diagnostics and "
        "authorized bug-bounty assistance."
    ),
)

app.include_router(agent_router)


class ChatRequest(BaseModel):
    prompt: str


@app.get("/")
def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "agent_endpoint": "/agent/run",
        "documentation": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.post("/chat")
def chat(request: ChatRequest):
    answer = ask_ai(request.prompt)

    return {
        "response": answer,
    }
PY

echo
echo "Agent MVP files created successfully."
echo
find backend/app/agents backend/app/tools backend/app/api \
    -maxdepth 2 -type f | sort
