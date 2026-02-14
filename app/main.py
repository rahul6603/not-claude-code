import argparse
import logging
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionToolMessageParam,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_message_function_tool_call_param import (
    ChatCompletionMessageFunctionToolCallParam,
    Function,
)

from .lsp.server import LanguageServer
from .tools.bash import execute_bash_tool
from .tools.definitions import TOOL_DEFINITIONS
from .tools.read import execute_read_tool
from .tools.write import execute_write_tool
from .config import API_KEY, BASE_URL

logger = logging.getLogger(__name__)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", required=True)
    args = p.parse_args()

    if not API_KEY:
        logger.error("OPENROUTER_API_KEY is not set")
        return

    language_server = LanguageServer()
    language_server.initialize()
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    initial_user_message = ChatCompletionUserMessageParam(role="user", content=args.p)
    conversation_history: list[ChatCompletionMessageParam] = [initial_user_message]
    while True:
        chat = client.chat.completions.create(
            model="openrouter/free",
            messages=conversation_history,
            tools=TOOL_DEFINITIONS,
        )

        if not chat.choices:
            logger.error("no choices in response")
            return

        message = chat.choices[0].message
        tool_calls = message.tool_calls
        content = message.content
        assistant_message = ChatCompletionAssistantMessageParam(
            role="assistant",
            content=content,
        )
        if not tool_calls:
            if content:
                print(content)
            return
        assistant_message["tool_calls"] = []
        tool_messages = []
        for tool_call in tool_calls:
            if tool_call.type == "function":
                tool_call_id = tool_call.id
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
                assistant_message["tool_calls"].append(
                    ChatCompletionMessageFunctionToolCallParam(
                        id=tool_call.id,
                        type=tool_call.type,
                        function=Function(name=function_name, arguments=arguments),
                    )
                )
                if function_name == "Read":
                    tool_response = execute_read_tool(language_server, arguments)
                elif function_name == "Write":
                    tool_response = execute_write_tool(language_server, arguments)
                elif function_name == "Bash":
                    tool_response = execute_bash_tool(arguments)
                else:
                    tool_response = f"Unknown tool: {function_name}"
                tool_messages.append(
                    ChatCompletionToolMessageParam(
                        role="tool",
                        tool_call_id=tool_call_id,
                        content=tool_response,
                    )
                )
        conversation_history.append(assistant_message)
        conversation_history.extend(tool_messages)


if __name__ == "__main__":
    main()
