import logging
import json

from app.config import SAFE_DIR
from app.lsp.server import LanguageServer

logger = logging.getLogger(__name__)


def execute_read_tool(
    language_server: LanguageServer,
    arguments: str,
) -> str:
    try:
        arguments = json.loads(arguments)
    except Exception as e:
        logger.error(error := f"Failed to parse arguments: {e}")
        return error
    if not isinstance(arguments, dict):
        logger.error(error := "Arguments in response not in dict format")
        return error
    file_path = arguments.get("file_path")
    if not file_path or not isinstance(file_path, str):
        logger.error(error := "Missing or invalid file_path argument")
        return error
    try:
        requested_path = (SAFE_DIR / file_path).resolve()
        requested_path.relative_to(SAFE_DIR)
        if not requested_path.is_file():
            logger.error(error := f"Not a file: {file_path}")
            return error

        content = requested_path.read_text(encoding="utf-8")
        language_server.send_did_read_notification(requested_path, content)

        return content

    except ValueError:
        logger.error(error := f"Path outside allowed directory: {file_path}")
    except PermissionError:
        logger.error(error := f"Permission denied: {file_path}")
    except Exception as e:
        logger.error(error := f"Unexpected error while reading file: {e}")
    return error
