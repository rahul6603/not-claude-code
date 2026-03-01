import json
import logging

from app.config import SAFE_DIR
from app.lsp.server import LanguageServerManager

logger = logging.getLogger(__name__)


def execute_write_tool(
    language_server_manager: LanguageServerManager,
    arguments: str,
) -> str:
    try:
        arguments = json.loads(arguments)
    except Exception as e:
        logger.error(error := f"Failed to parse arguments: {e}")
        return format_error_response(error)
    if not isinstance(arguments, dict):
        logger.error(error := "Arguments in response not in dict format")
        return format_error_response(error)
    file_path = arguments.get("file_path")
    if not file_path or not isinstance(file_path, str):
        logger.error(error := "Missing or invalid file_path argument")
        return format_error_response(error)
    content = arguments.get("content")
    if not content:
        logger.error(error := "Content argument missing in response")
        return format_error_response(error)
    if not isinstance(content, str):
        logger.error(error := "Invalid content argument")
        return format_error_response(error)
    try:
        requested_path = (SAFE_DIR / file_path).resolve()
        requested_path.relative_to(SAFE_DIR)
        requested_path.write_text(content)
        diagnostics_output = language_server_manager.send_did_change_notification(
            requested_path, content
        )

        return json.dumps(
            {
                "success": True,
                "diagnostics": diagnostics_output,
            }
        )
    except ValueError:
        logger.error(error := f"Path outside allowed directory: {file_path}")
    except FileNotFoundError:
        logger.error(error := f"Path not found: {file_path}")
    except PermissionError:
        logger.error(error := f"Permission denied: {file_path}")
    except Exception as e:
        logger.error(error := f"Unexpected error while writing to file: {e}")
    return format_error_response(error)


def format_error_response(error: str) -> str:
    return json.dumps(
        {
            "success": False,
            "error": error,
        }
    )
