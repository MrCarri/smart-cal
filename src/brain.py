"""AI brain module that contains the necessary code to define tools and how to use them"""

from datetime import datetime
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
                if call.function.name == "get_events":
                    reminder = (
                        "\nIMPORTANT: Remember to list EVERY event. Format: [YYYY-MM-DD] - "
                        "Event name (HH:MM - HH:MM). One line per event. NO summaries."
                    )
                    tool_result = reminder + str(tool_result)
                # Add tool result to history
                history.append(
                    {
                        "role": "tool",
                        "content": str(tool_result),
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
        # Role: Calendar Agent.
        # Task:
         Your task is to administer appointments. Your only responsability is to manage calendar events. You cannot anwser general knowledge questions, tell jokes or provide advice. If a request is outside calendar management, politely decline and explain that your specific role.
        # Context: today is $current_datetime. Timezone is Europe/Madrid
        # Guidelines:
        ## Tool usage Rules:
            - If you need to create, list or delete an event, call the appropriate tool.
            - If the user's request is a greeting or general talk that doesn't require calendar information, respond normally without calling any tool.
        ## Behavior Rules:
            - Be concise. If no tool is needed, answer briefly.
            - If the user doesn't request anything on specific, you can talk about what you are able to do.
            - If you are unsure about the name of the day of the appointment, just say the number.
            - If information is missing, ask it to the user to provide it.
            - If the request is unclear, ask for clarification instead of guessing.
            - If a tool returns is an error message, explain it in simple terms.
        ## Format Rules:
            - Use the date format YYYY-MM-DD HH:MM for any date arguments.
            - NEVER show the tool call JSON to the user.
        ## get_event tool Rules:
            - COUNTING RULE: If the tool returns 4 items, you must output exactly 4 formatted lines. Duplicates must never be merged into a single line or a text description.
            - DO NOT summarize or skip events. You MUST list EVERY event returned by the tool in chronological order.
            - Start each line with the format: [YYYY-MM-DD] - Title (HH:MM - HH:MM).
            - If the tool returns no events for a period, clearly state: "No events found for this period."
            - TRUNCATION IS FORBIDDEN: You must list every single item found in the tool output. - Do not summarize. Missing events will be considered a logic error.
            - One line per event.
            - If you add extra text while listing events, the system will fail.
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
                            "description": "When the event ends. If uknown, return empty string. Never invent end time. Always use ISO Format assuming timezone Europe/Madrid YYYY-MM-DD HH:MM",
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
                            "description": "When the event ends. If uknown, return empty string. Never invent end time. Always use ISO Format assuming timezone Europe/Madrid YYYY-MM-DD HH:MM If the user does not provide an hour, assume 23:59.",
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
