import argparse
import os
import json
import logging
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
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

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")
SAFE_DIR = Path(".").resolve()

logging.basicConfig(level=logging.WARN, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", required=True)
    args = p.parse_args()

    if not API_KEY:
        logger.error("OPENROUTER_API_KEY is not set")
        return

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    initial_user_message = ChatCompletionUserMessageParam(role="user", content=args.p)
    conversation_history: list[ChatCompletionMessageParam] = [initial_user_message]
    while True:
        chat = client.chat.completions.create(
            model="anthropic/claude-haiku-4.5",
            # model="openrouter/free",
            messages=conversation_history,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "Read",
                        "description": "Read and return the contents of a file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "The path to the file to read",
                                }
                            },
                            "required": ["file_path"],
                        },
                    },
                }
            ],
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
                    tool_response = execute_read_tool(arguments)
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


def execute_read_tool(arguments: str) -> str:
    try:
        arguments = json.loads(arguments)
    except json.JSONDecodeError:
        logger.error(error := "Invalid JSON in arguments")
        return error
    if not isinstance(arguments, dict):
        logger.error(error := "Arguments in response not in dict format")
        return error
    file_path = arguments.get("file_path")
    if not file_path:
        logger.error(error := f"Argument missing in response: {file_path}")
        return error
    if not file_path or not isinstance(file_path, str):
        logger.error(error := "Missing or invalid file_path")
        return error
    try:
        requested_path = (SAFE_DIR / file_path).resolve()
        requested_path.relative_to(SAFE_DIR)
        if not requested_path.is_file():
            logger.error(error := f"Not a file: {file_path}")
            return error

        content = requested_path.read_text(encoding="utf-8")
        return content

    except ValueError:
        logger.error(error := f"Path outside allowed directory: {file_path}")
        return error
    except PermissionError:
        logger.error(error := f"Permission denied: {file_path}")
        return error
    except Exception as e:
        logger.error(error := f"Error reading file: {e}")
        return error


if __name__ == "__main__":
    main()
