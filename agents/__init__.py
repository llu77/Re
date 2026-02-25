"""
Rehabilitation Multi-Agent System
=================================
Specialized agents for medical rehabilitation tasks.
"""

from agents.base_agent import BaseAgent
from agents.assessment_agent import AssessmentAgent
from agents.treatment_agent import TreatmentAgent

__all__ = ["BaseAgent", "AssessmentAgent", "TreatmentAgent"]
