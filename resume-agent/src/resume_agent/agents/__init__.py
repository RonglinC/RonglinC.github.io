from __future__ import annotations

from resume_agent.agents.base import BaseApplyAgent
from resume_agent.agents.greenhouse import GreenhouseAgent
from resume_agent.agents.lever import LeverAgent
from resume_agent.agents.manual import ManualAgent
from resume_agent.config import AgentConfig
from resume_agent.models.job import Job


def get_agents(config: AgentConfig) -> list[BaseApplyAgent]:
    return [
        GreenhouseAgent(config),
        LeverAgent(config),
        ManualAgent(config),
    ]


async def select_agent(agents: list[BaseApplyAgent], job: Job) -> BaseApplyAgent:
    for agent in agents:
        if agent.name == "manual":
            continue
        if await agent.can_apply(job):
            return agent
    return agents[-1]
