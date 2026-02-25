"""
Multi-Agent Orchestrator for Medical Rehabilitation
====================================================
Routes requests to specialized agents based on content analysis.
"""

import os
import re
import anthropic
from agents.assessment_agent import AssessmentAgent
from agents.treatment_agent import TreatmentAgent
from agents.base_agent import BaseAgent
from rehab_consultant import SYSTEM_PROMPT, TOOLS, execute_tool


class RehabOrchestrator:
    """Multi-Agent Orchestrator for Medical Rehabilitation."""

    def __init__(self):
        self.agents = {
            "assessment": AssessmentAgent(),
            "treatment": TreatmentAgent(),
            "general": BaseAgent(
                name="general",
                specialty="استشارات عامة",
                system_instructions="أنت المستشار العام. تعامل مع الاستفسارات العامة والمحادثات.",
                tool_names=None,  # all tools
            ),
        }

        # Keyword-based routing patterns
        self._assessment_keywords = [
            "تقييم", "فحص", "قياس", "اختبار", "assessment", "evaluate", "test",
            "ROM", "MMT", "Berg", "FIM", "Barthel", "VAS", "TUG", "6MWT",
            "BCEA", "MNREAD", "PHQ", "GAD", "MMSE", "Ashworth",
            "حدة", "توازن", "قوة", "ألم", "مدى الحركة",
        ]
        self._treatment_keywords = [
            "خطة", "علاج", "تمرين", "تأهيل", "تدخل", "جلسة", "برنامج",
            "treatment", "plan", "exercise", "intervention", "rehab",
            "تمارين", "منزلي", "هدف", "أهداف", "SMART",
            "record_treatment", "خطة علاجية",
        ]

    def route(self, message: str, patient: dict = None) -> str:
        """Determine which agent should handle the request."""
        msg_lower = message.lower()

        # Count keyword matches for each agent
        assessment_score = sum(1 for kw in self._assessment_keywords if kw.lower() in msg_lower)
        treatment_score = sum(1 for kw in self._treatment_keywords if kw.lower() in msg_lower)

        if assessment_score > treatment_score and assessment_score >= 2:
            return "assessment"
        elif treatment_score > assessment_score and treatment_score >= 2:
            return "treatment"

        # Default to general for everything else
        return "general"

    def get_agent(self, agent_name: str) -> BaseAgent:
        """Get agent by name."""
        return self.agents.get(agent_name, self.agents["general"])

    def execute(self, message: str, patient: dict = None, messages: list = None,
                system: str = None, images: list = None, stream: bool = False,
                placeholder=None, thinking_budget: int = 8000,
                use_thinking: bool = True) -> dict:
        """Execute request through the appropriate agent."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {
                "text": "[تنبيه] مفتاح API غير موجود!",
                "tool_calls": [],
                "thinking_used": False,
            }

        client = anthropic.Anthropic(api_key=api_key)

        # Route to appropriate agent
        agent_name = self.route(message, patient)
        agent = self.get_agent(agent_name)

        # Build system prompt with agent-specific instructions
        base_system = system or SYSTEM_PROMPT
        full_system = agent.build_system_prompt(base_system)

        if stream and placeholder:
            return agent.process_stream(
                client=client,
                messages=messages or [],
                system=full_system,
                placeholder=placeholder,
                thinking_budget=thinking_budget,
                use_thinking=use_thinking,
            )
        else:
            return agent.process(
                client=client,
                messages=messages or [],
                system=full_system,
                thinking_budget=thinking_budget,
                use_thinking=use_thinking,
            )
