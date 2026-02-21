"""AI brain module that contains the necessary code to define tools and how to use them"""

from datetime import datetime, timedelta
import json
from string import Template

from ollama import chat
from crud import CalendarRepository
from helpers import (  # Translate names into English, for non English locales.
    DAYS_EN,
)


class AgentBrain:
    """Class that holds the necessary code to define tools and the agent behavior"""

    def __init__(self, model, repository: CalendarRepository) -> None:
        self.repository = repository
        self.model = model
        self._tool_map = {
            "create_event": self.repository.create_event,
            "delete_event": self.repository.delete_event,
            "get_events": self.repository.get_events,
        }

    def _get_system_prompt(self) -> str:
        now = datetime.now()

        tomorrow = now + timedelta(days=1)
        next_monday = now + timedelta(
            days=((7 - now.weekday()) if now.weekday() != 0 else 7)
        )

        current_time_str = (
            f"Today is: {DAYS_EN[now.weekday()]} {now.strftime('%Y-%m-%d %H:%M')}. "
            f"Tomorrow is {DAYS_EN[tomorrow.weekday()]} {tomorrow.strftime('%Y-%m-%d')}. "
            f"Next week starts on {DAYS_EN[0]} {next_monday.strftime('%Y-%m-%d')}."
        )
        return self._PROMPT_TEMPLATE.substitute({"current_datetime": current_time_str})

    def _get_tools_schema(self) -> list:
        return self._TOOLS

    def _execute_tool(self, tool_call):
        func_name = tool_call.function.name
        args = tool_call.function.arguments

        # Special case for vague dates.
        if func_name == "create_event" or func_name == "get_events":
            if not args.get("start_date") or args.get("start_date").strip() == "":
                return "Error: The date is too vague. Please ask the user for a specific day or date."

        # Special case for event_id (integer). If Agent returns "1" instead of 1, a preventive cast is needed.
        if "event_id" in args and isinstance(args["event_id"], str):
            try:
                args["event_id"] = int(args["event_id"])
            except ValueError:
                return f"Error: event_id must be a number, got '{args['event_id']}'"
        func = self._tool_map.get(func_name)

        if func:
            return func(**args)
        return f"Error: Tool {func_name} not found"

    def chat(self, user_input: str):
        # 1. Construct history
        history = [{"role": "system", "content": self._get_system_prompt()}]
        history.append({"role": "user", "content": user_input})

        response = chat(
            model=self.model,
            messages=history,
            tools=self._get_tools_schema(),
            options={
                "temperature": 0.0,
                "num_predict": 50,
                "num_ctx": 1024,
            },
        )

        # 2. Call tools management
        if response.message.tool_calls:
            for call in response.message.tool_calls:
                # Execute tool
                try:
                    tool_result = self._execute_tool(call)
                except Exception as exc:
                    tool_result = f"Error calling tool. Reason: {str(exc)}"

                # If there's a call to get events, add a small format reminder of the rules. this for small models.
                if call.function.name == "get_events" and not tool_result:
                    return "No events found for this period."
                return tool_result

        return "Sorry, Don't understand."

    _PROMPT_TEMPLATE = Template(
        """

        # SYSTEM: Calendar Agent.
        # TASK:  Call the required tool and exit.
        # CONTEXT:
        - $current_datetime.
        - Timezone is Europe/Madrid.

        """
    )

    _TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "create_event",
                "description": "Create a new calendar appointment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Event title",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Target date. Use ISO YYYY-MM-DD HH:MM if possible. If relative (e.g. 'monday', 'tomorrow'), return the literal text.",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date. Use ISO YYYY-MM-DD HH:MM if possible. If relative, return literal text. Return empty string if not specified.",
                        },
                        "category_name": {
                            "type": "string",
                            "description": "Category (work, medical, personal, etc). Default to 'personal'.",
                        },
                    },
                    "required": ["title", "start_date", "category_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_events",
                "description": "List appointments from the calendar. Use it for 'what do I have', 'check my schedule' or 'plans'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "Target date. Use ISO YYYY-MM-DD HH:MM if possible. Default time, 00:00 If relative (e.g. 'monday', 'tomorrow'), return the literal text.",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date. Use ISO YYYY-MM-DD HH:MM if possible. If not specified or unknown, return an empty string. Never invent an end date.",
                        },
                    },
                    "required": ["start_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_event",
                "description": """Delete an appointments from the calendar. Use it when the user asks 'Delete event with id 1'.
                Only use this tool if the user provides a numeric ID. """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "integer",
                            "description": "Event Id to delete",
                        }
                    },
                    "required": ["event_id"],
                },
            },
        },
    ]
