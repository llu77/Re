"""
Base Agent — foundation class for all specialized rehabilitation agents.
"""

import json
import anthropic
from rehab_consultant import TOOLS, execute_tool, extract_text_response
from utils.security import validate_medical_output


class BaseAgent:
    """Base class for specialized rehabilitation agents."""

    def __init__(self, name: str, specialty: str, system_instructions: str, tool_names: list = None):
        self.name = name
        self.specialty = specialty
        self.system_instructions = system_instructions
        self.tool_names = tool_names  # subset of TOOLS by name, or None for all

    def get_tools(self) -> list:
        """Return agent-specific tools (subset of global TOOLS)."""
        if self.tool_names is None:
            return TOOLS
        return [t for t in TOOLS if t["name"] in self.tool_names]

    def build_system_prompt(self, base_prompt: str, patient_context: str = "") -> str:
        """Build agent-specific system prompt."""
        return (
            f"{base_prompt}\n\n"
            f"<agent_role>\n{self.system_instructions}\n</agent_role>\n"
            f"{patient_context}"
        )

    def process(self, client: anthropic.Anthropic, messages: list, system: str,
                thinking_budget: int = 8000, use_thinking: bool = True) -> dict:
        """Run agent reasoning loop with tool use (synchronous)."""
        api_params = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 16384,
            "system": system,
            "tools": self.get_tools(),
            "messages": messages,
        }
        if use_thinking:
            api_params["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

        tool_calls_log = []
        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = client.messages.create(**api_params)

            if response.stop_reason == "end_turn":
                result_text = extract_text_response(response)
                return {
                    "text": validate_medical_output(result_text),
                    "tool_calls": tool_calls_log,
                    "thinking_used": use_thinking,
                }

            if response.stop_reason == "tool_use":
                api_params["messages"].append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        result = execute_tool(block.name, block.input)
                        log_entry = {"name": block.name, "input_preview": str(block.input)[:120]}
                        if block.name == "generate_visual_exercise" and isinstance(result, dict) and "svg" in result:
                            log_entry["svg_data"] = result["svg"]
                            log_entry["svg_title"] = result.get("title", "")
                            log_entry["svg_instructions"] = result.get("instructions", "")
                            log_entry["svg_duration"] = result.get("duration_minutes", 10)
                            log_entry["svg_reps"] = result.get("repetitions", 3)
                            log_entry["svg_evidence"] = result.get("evidence_level", "B")
                        tool_calls_log.append(log_entry)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                api_params["messages"].append({"role": "user", "content": tool_results})
            else:
                result_text = extract_text_response(response)
                return {
                    "text": validate_medical_output(result_text),
                    "tool_calls": tool_calls_log,
                    "thinking_used": False,
                }

        return {
            "text": "تم الوصول للحد الأقصى من التكرارات.",
            "tool_calls": tool_calls_log,
            "thinking_used": False,
        }

    def process_stream(self, client: anthropic.Anthropic, messages: list, system: str,
                       placeholder=None, thinking_budget: int = 8000, use_thinking: bool = True) -> dict:
        """Run agent reasoning loop with streaming output."""
        api_params = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 16384,
            "system": system,
            "tools": self.get_tools(),
            "messages": messages,
        }
        if use_thinking:
            api_params["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

        tool_calls_log = []
        accumulated_text = ""
        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            with client.messages.stream(**api_params) as stream:
                current_text = ""
                for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            current_text += event.delta.text
                            accumulated_text += event.delta.text
                            if placeholder:
                                placeholder.markdown(accumulated_text + " |")

                response = stream.get_final_message()

            if response.stop_reason == "end_turn":
                if placeholder:
                    placeholder.markdown(validate_medical_output(accumulated_text))
                return {
                    "text": validate_medical_output(accumulated_text),
                    "tool_calls": tool_calls_log,
                    "thinking_used": use_thinking,
                }

            if response.stop_reason == "tool_use":
                api_params["messages"].append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        if placeholder:
                            placeholder.markdown(accumulated_text + f"\n\n---\n*جارٍ استخدام أداة: {block.name}...*")
                        result = execute_tool(block.name, block.input)
                        log_entry = {"name": block.name, "input_preview": str(block.input)[:120]}
                        if block.name == "generate_visual_exercise" and isinstance(result, dict) and "svg" in result:
                            log_entry["svg_data"] = result["svg"]
                            log_entry["svg_title"] = result.get("title", "")
                            log_entry["svg_instructions"] = result.get("instructions", "")
                            log_entry["svg_duration"] = result.get("duration_minutes", 10)
                            log_entry["svg_reps"] = result.get("repetitions", 3)
                            log_entry["svg_evidence"] = result.get("evidence_level", "B")
                        tool_calls_log.append(log_entry)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                api_params["messages"].append({"role": "user", "content": tool_results})
            else:
                if placeholder:
                    placeholder.markdown(validate_medical_output(accumulated_text))
                return {
                    "text": validate_medical_output(accumulated_text),
                    "tool_calls": tool_calls_log,
                    "thinking_used": False,
                }

        return {
            "text": accumulated_text or "تم الوصول للحد الأقصى من التكرارات.",
            "tool_calls": tool_calls_log,
            "thinking_used": False,
        }
