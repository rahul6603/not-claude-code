import json
import logging
import subprocess

logger = logging.getLogger(__name__)


def execute_bash_tool(arguments: str) -> str:
    try:
        arguments = json.loads(arguments)
    except Exception as e:
        logger.error(error := f"Failed to parse arguments: {e}")
        return error
    if not isinstance(arguments, dict):
        logger.error(error := "Arguments in response not in dict format")
        return error
    command = arguments.get("command")
    if not command:
        logger.error(error := "command argument missing in response")
        return error
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    except PermissionError:
        logger.error(error := "Permission denied to execute command")
    except subprocess.TimeoutExpired:
        logger.error(error := "Command took too long")
    except Exception as e:
        logger.error(error := f"Unexpected error while executing the command: {e}")
    return error
