import argparse
import os
import json
import logging
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from openai.types.chat import ChatCompletionMessageFunctionToolCall

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

    chat = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        # model="openrouter/free",
        messages=[{"role": "user", "content": args.p}],
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
    if content:
        print(content)
    if not tool_calls:
        return
    for tool_call in tool_calls:
        if tool_call.type == "function":
            function_name = tool_call.function.name
            if function_name == "Read":
                execute_read_tool(tool_call)


def execute_read_tool(tool_call: ChatCompletionMessageFunctionToolCall):
    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in arguments")
        return
    if not isinstance(arguments, dict):
        return
    file_path = arguments.get("file_path")
    if not file_path:
        return
    if not file_path or not isinstance(file_path, str):
        logger.error("Missing or invalid file_path")
        return
    try:
        requested_path = (SAFE_DIR / file_path).resolve()
        requested_path.relative_to(SAFE_DIR)
        if not requested_path.is_file():
            logger.error(f"Not a file: {file_path}")
            return

        content = requested_path.read_text(encoding="utf-8")
        print(content)

    except ValueError:
        logger.error(f"Path outside allowed directory: {file_path}")
    except PermissionError:
        logger.error(f"Permission denied: {file_path}")
    except Exception as e:
        logger.error(f"Error reading file: {e}")


if __name__ == "__main__":
    main()
