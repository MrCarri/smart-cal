"""AI brain module that contains the necessary code to define tools and how to use them"""

from datetime import datetime
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
        day_name = DAYS_EN[now.weekday()]
        current_time_str = f"{day_name}, {now.strftime('%Y-%m-%d %H:%M')}"

        return self._PROMPT_TEMPLATE.substitute({"current_datetime": current_time_str})

    def _get_tools_schema(self) -> list:
        return self._TOOLS

    def _execute_tool(self, tool_call):
        func_name = tool_call.function.name
        args = tool_call.function.arguments
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
                    content_for_ai = "No results found for this period."
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

            final_response = chat(model=self.model, messages=history)
            return final_response.message.content

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
        # SYSTEM: Calendar Agent. Today is $current_datetime. Timezone is Europe/Madrid.

        # TASK: Administer appointments. Stick to manage calendar events. Decline answering non related questions, jokes or advice.

        # Tool Rules:
        - Call the appropriate tool if asked to create, list or delete events.
        - If request doesn't require tools, respond normally.
        - COUNTING RULE: If a tool returns 4 items, output must be exactly 4 items. Never merge duplicates.
        - DO NOT summarize or skip events.
        - List in chronological order.
        - If no events found, return "Not event founds for this period"

        # Behavior Rules
        - Be concise.
        - If request doesn't request anything specific, explain what you can do.
        - If request unclear or not sure, don't do anything.
        - If error message, explain the error in simple terms.
        - Don't say day names. Use day number instead.

        # Format Rules:
        - Never answer with JSON.
        - ALWAYS use date format YYYY-MM-DD HH:MM.
        """
    )

    _TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "create_event",
                "description": """Create an event for the calendar. Always Use it when the user wants to add, shedule or create a new appointment for the calendar. You must at least extract title, category_name, and start_date of the appointment.
                If the date is relative you must calculate the correct day taking into account today's date.
                Good Example: Add a work meeting at 13:00 tomorrow. -> title= 'Work meeting', category_name='work', start_date='2026-05-20 13:00'
                Good Example: Next Wednesday -> if today is Sunday, 2026-01-11 then -> start_date='2026-01-14'
                Bad Example: Dinner tomorrow -> start_date='tomorrow at 8pm' (ERROR: Should be YYYY-MM-DD HH:MM)
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Little summary of the appointment",
                        },
                        "start_date": {
                            "type": "string",
                            "description": """When the event starts. Always use ISO Format assuming timezone Europe/Madrid YYYY-MM-DD HH:MM
                                Good Example: Doctor appointment today at 14 -> '2026-05-19 14:00'

                            """,
                        },
                        "end_date": {
                            "type": "string",
                            "description": "When the event ends. If unknown, return empty string. Never invent end time. Always use ISO Format assuming timezone Europe/Madrid YYYY-MM-DD HH:MM",
                        },
                        "category_name": {
                            "type": "string",
                            "description": "Category name of the appointment. Use relevant terms such as work, medical, personal, groceries... Never invent the category name. If not sure, use 'personal'. ",
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
                "description": "List appointments from the calendar. ONLY use this tool if the user explicitly asks about their schedule, appointments, or dates. Use it when the user asks 'what do I have today', 'see my week' or 'check my schedule'.DO NOT use this tool for greetings, identity questions, or general talk.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_date": {
                            "type": "string",
                            "description": """When the event starts. Always use ISO Format assuming timezone Europe/Madrid YYYY-MM-DD HH:MM
                                If the user does not provide an hour, assume 00:00.
                                Good Example: 'What I have to do today? -> '2026-05-19 00:00'
                            """,
                        },
                        "end_date": {
                            "type": "string",
                            "description": "When the event ends. If unknown, return empty string. Never invent end time. Always use ISO Format assuming timezone Europe/Madrid YYYY-MM-DD HH:MM If the user does not provide an hour, assume 23:59.",
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
