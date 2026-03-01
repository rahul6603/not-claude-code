import asyncio
from typing import Callable
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call_param import Function

from app.lsp.server import LanguageServerManager
from app.tools.definitions import TOOL_DEFINITIONS
from app.tools.bash import execute_bash_tool
from app.tools.read import execute_read_tool
from app.tools.write import execute_write_tool


class Agent:
    def __init__(
        self,
        client: AsyncOpenAI,
        on_error: Callable[[str], None],
        on_token: Callable[[str], None],
        on_message_done: Callable[[str], None],
    ):
        self.client: AsyncOpenAI = client
        self.language_server_manager: LanguageServerManager = LanguageServerManager()
        self.conversation_history: list[ChatCompletionMessageParam] = []
        self.on_error: Callable[[str], None] = on_error
        self.on_token: Callable[[str], None] = on_token
        self.on_message_done: Callable[[str], None] = on_message_done

    async def process_turn(self) -> bool:
        try:
            stream = await self.client.chat.completions.create(
                model="openrouter/free",
                messages=self.conversation_history,
                tools=TOOL_DEFINITIONS,
                stream=True,
            )
        except Exception:
            self.on_error("Could not call the OpenRouter API, try again")
            return False

        content_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, str]] = {}

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                self.on_token(delta.content)

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {
                            "id": "",
                            "type": "function",
                            "function_name": "",
                            "arguments": "",
                        }
                    entry = tool_calls_by_index[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.type:
                        entry["type"] = tc_delta.type
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["function_name"] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

        full_content = "".join(content_parts) or None

        assistant_message = ChatCompletionAssistantMessageParam(
            role="assistant",
            content=full_content,
        )

        if not tool_calls_by_index:
            if full_content:
                self.on_message_done(full_content)
                self.conversation_history.append(assistant_message)
            return False

        assistant_message["tool_calls"] = []
        tool_messages: list[ChatCompletionToolMessageParam] = []

        for idx in sorted(tool_calls_by_index.keys()):
            tc = tool_calls_by_index[idx]
            tool_call_id = tc["id"]
            function_name = tc["function_name"]
            arguments = tc["arguments"]

            assistant_message["tool_calls"].append(
                ChatCompletionMessageFunctionToolCallParam(
                    id=tool_call_id,
                    type="function",
                    function=Function(name=function_name, arguments=arguments),
                )
            )

            if function_name == "Read":
                tool_response = await asyncio.to_thread(
                    execute_read_tool, self.language_server_manager, arguments
                )
            elif function_name == "Write":
                tool_response = await asyncio.to_thread(
                    execute_write_tool, self.language_server_manager, arguments
                )
            elif function_name == "Bash":
                tool_response = await asyncio.to_thread(execute_bash_tool, arguments)
            else:
                tool_response = f"Unknown tool: {function_name}"

            tool_messages.append(
                ChatCompletionToolMessageParam(
                    role="tool",
                    tool_call_id=tool_call_id,
                    content=tool_response,
                )
            )

        self.conversation_history.append(assistant_message)
        self.conversation_history.extend(tool_messages)
        return True

    def add_user_message(self, content: str) -> None:
        self.conversation_history.append(
            ChatCompletionUserMessageParam(role="user", content=content)
        )
