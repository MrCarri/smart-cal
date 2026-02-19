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
                "num_predict": 500,
            },
        )

        # Add response to history
        history.append(response.message)  # type: ignore (Ignore linter complaints, correct way to do it according to ollama docs.)

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
                    content_for_ai = "No events found for this period."
                else:
                    content_for_ai = json.dumps(tool_result)
                # Add tool result to history
                history.append(
                    {
                        "role": "tool",
                        "content": content_for_ai,
                        "tool_name": call.function.name,
                    }
                )

            # 3. Final call to ollama to present results

            final_response_stream = chat(
                model=self.model, messages=history, stream=True
            )
            full_content = ""
            print("Agent: ", end="", flush=True)

            for chunk in final_response_stream:
                token = chunk["message"]["content"]
                print(token, end="", flush=True)
                full_content += token

            print()
            return full_content

        # This will fire in the case only that the model allucinated and returned a json
        # Basically doesn't know what to say, so it returns a json that is valid for tools.
        elif response.message.content and response.message.content.strip().startswith(
            "{"
        ):
            return "Hi, I'm you calendar agent. What do you need?"

        # This return will be used when no tool is called, for example as a response for greeting.
        return response.message.content

    _PROMPT_TEMPLATE = Template(
        """
        # SYSTEM: Calendar Agent.

        # CONTEXT:
        - $current_datetime.
        - Timezone is Europe/Madrid.

        # TASK: Administer appointments only. Decline non-related questions, jokes or advice.

        # Tool Rules:
        - Use tools only for creating, listing or deleting events.
        - If no tool is needed, respond with plain text.
        - COUNTING RULE: If tool returns 4 items, you MUST output 4 lines. NEVER merge duplicates.
        - TRUNCATION IS FORBIDDEN: Do not summarize or skip events.
        - List in chronological order.
        - If no events found, return "No events found for this period."

        # Behavior Rules:
        - Be concise. Skip pleasantries.
        - If the request is unclear, briefly explain what you can do (e.g., "Tell me a date to check your schedule").
        - If error message, explain it in simple terms.
        - Use day numbers, never names (e.g. 2026-01-20, not Tuesday).

        # Format Rules:
        - NEVER output raw JSON. Always respond in plain text.
        - LIST FORMAT: ID: [event_id] - [YYYY-MM-DD] - Title (HH:MM - HH:MM)
        - For tool arguments, always use: YYYY-MM-DD HH:MM
        """
    )

    _TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "create_event",
                "description": "Add a new appointment. Use ONLY when the user wants to schedule something. Extract title, category, and date. If the date is vague or not 100 percent certain, return an empty string for start_date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Summary of the appointment",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "ISO YYYY-MM-DD HH:MM. If the day is vague (e.g. 'next week', 'soon', 'later') return EMPTY STRING. Never guess. Examples: 'next Wednesday' -> '', 'today at 5' -> '2026-01-20 17:00'",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "ISO YYYY-MM-DD HH:MM. Return empty string if not specified.",
                        },
                        "category_name": {
                            "type": "string",
                            "description": "Category (work, medical, personal, etc). Default to 'personal' if unsure.",
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
                "description": "List appointments from the calendar. Use it for 'what do I have', 'check my schedule' or 'plans'. You must calculate absolute dates. If the date is vague (e.g., 'soon', 'later', 'next week') and you cannot determine the exact start day, return an EMPTY STRING.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": "ISO YYYY-MM-DD HH:MM. Default time: 00:00. If the user is Vague, return an EMPTY STRING. Example: 'Today' -> '2026-01-20 00:00', 'Soon' -> '' ",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "ISO YYYY-MM-DD HH:MM. If not specified or unknown, return an empty string. Never invent an end date.",
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
