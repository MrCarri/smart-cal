"""AI brain module that contains the necessary code to define tools and how to use them"""

from datetime import datetime, timedelta
import json
from string import Template

from ollama import generate
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
        return ""  # TODO: FIXME
        # return self._PROMPT_TEMPLATE.substitute({"current_datetime": current_time_str})

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
        # history = [{"role": "system", "content": self._get_system_prompt()}]
        # history.append({"role": "user", "content": user_input})
        response = generate(
            model=self.model,
            prompt=self._PROMPT_TEMPLATE_INTENTION.substitute(
                {"user_input": user_input}
            ),
            format="json",
            stream=False,
            think=False,
            options={
                "temperature": 0.0,
                "num_predict": 50,
                "num_ctx": 512,
            },
        )
        return response.response
        # response = chat(
        #     model=self.model,
        #     messages=history,
        #     tools=self._get_tools_schema(),
        #     options={
        #         "temperature": 0.0,
        #         "num_predict": 50,
        #         "num_ctx": 1024,
        #     },
        # )

        # 2. Call tools management
        # if response.message.tool_calls:
        #     for call in response.message.tool_calls:
        #         # Execute tool
        #         try:
        #             tool_result = self._execute_tool(call)
        #         except Exception as exc:
        #             tool_result = f"Error calling tool. Reason: {str(exc)}"

        #         # If there's a call to get events, add a small format reminder of the rules. this for small models.
        #         if call.function.name == "get_events" and not tool_result:
        #             return "No events found for this period."
        #         return tool_result

        # return "Sorry, Don't understand."

    _PROMPT_TEMPLATE_INTENTION = Template(
        """
        # TASK: Analyze the user intention and ANSWER ONLY with a valid JSON.
        # RULES: "intention" value, must be one of this four: "create_event", "get_events", "delete_event","unknown". Do not invent new words.
        # EXAMPLES:

        User: "Add event to calendar for monday"
        JSON: {"intention": "create_event"}

        User: "What do I have scheduled for today"
        JSON: {"intention": "get_events"}

        User: "Delete the appointment with id 1"
        JSON: {"intention": "delete_event"}

        User: "$user_input"
        JSON:
        """
    )
    _PROMPT_TEMPLATE_CREATE_EVENT = Template(
        """
        # ROLE: Event extractor from user input.
        # CONTEXT:
        - today is: $today_weekday $today_date
        - tomorrow is: $tomorrow_weekday $tomorrow_date
        - Current year: $current_year
        - Timezone is Europe/Madrid
        # TASK: Extract event information, dates and category,and ANSWER ONLY with a valid JSON.
        # RULES: Extract the following values:
        - title: must be a concise summary of the appointment.
        - start_date: Target date. Use format YYYY-MM-DD HH:MM if possible. If relative, extract the relative fragment.
        - end_date: End date. Use format YYYY-MM-DD HH:MM if possible. If relative, extract the relative fragment. Return "" if not specified.
        - category_name: Category of the event. (work, medical, personal, etc.) Default to 'personal'.

        # EXAMPLES:

        USER: "Add doctor appointment for next monday"
        JSON: {"title": "Doctor appointment", "start_date":"next monday", "end_date":"","category_name":"medical"}

        USER: "Add buying groceries today at 9 "
        JSON: {"title": "Buy Groceries", "start_date":"$today_date 09:00", "end_date":"","category_name":"personal"}

        USER: "Create a work meeting tomorrow at 11 with a duration of 30 minutes."
        JSON: {"title": "Work meeting", "start_date":"$tomorrow_date 11:00", "end_date":"$tomorrow_date 11:30","category_name":"work"}

        USER: "Schedule a dinner with my wife on february 25th"
        JSON: {"title": "Dinner with my wife", "start_date":"$current_year-02-25 00:00", "end_date":"","category_name":"personal"}

        User: "$user_input"
        JSON:

        """
    )

    _PROMPT_TEMPLATE_LIST_EVENTS = Template(
        """
        # ROLE: Date extractor from user input
        # CONTEXT:
        - today is: $today_weekday $today_date
        - tomorrow is: $tomorrow_weekday $tomorrow_date
        - Current year: $current_year
        - Timezone is Europe/Madrid
        # TASK: Extract start_date and end_date from user input. ANSWER ONLY with a valid JSON.
        # RULES: Extract the following values:
        - start_date: Target date. Use format YYYY-MM-DD HH:MM if possible. Default time, 00:00. If relative, extract the relative fragment.
        - end_date: End date. Use format YYYY-MM-DD HH:MM if possible. If a single day is mentioned, default time is 23:59. If the input is a broad relative period (like week or month) and has no specific end, return "". If relative, extract the relative fragment. Return "" if not specified.

        # EXAMPLES:

        USER: "What do I have for tomorrow?"
        JSON: { "start_date":"$tomorrow_date 00:00", "end_date":"$tomorrow_date 23:59"}

        USER: "List appointments for today."
        JSON: { "start_date":"$today_date 00:00", "end_date":"$today_date 23:59"}

        USER: "What do I have for today and tomorrow?"
        JSON: { "start_date":"$today_date 00:00", "end_date":"$tomorrow_date 23:59"}

        USER: "What do I have scheduled next week?"
        JSON: { "start_date":"next week", "end_date":""}

        USER: "What I have to do next month?"
        JSON: { "start_date":"next month", "end_date":""}

        USER: "What appointments are on the 26th of february?"
        JSON: {"start_date":"$current_year-02-26 00:00", "end_date":"$current_year-02-26 23:59"}

        User: "$user_input"
        JSON:

        """
    )

    _PROMPT_TEMPLATE_DELETE_EVENT = Template(
        """
        # ROLE: Id extractor from user input
        # TASK: Extract the event id from user input
        # RULES: "event_id" value, must be numerical. If missing or unknown, return "unknown".

        User: "Delete doctor appointment with id 25"
        JSON: {"event_id": 25}

        User: "Delete the scheduled dinner at 3"
        JSON: {"event_id": "unknown"}

        User: "Clear tomorrow work meeting"
        JSON: {"event_id": "unknown"}

        User: "$user_input"
        JSON:
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
