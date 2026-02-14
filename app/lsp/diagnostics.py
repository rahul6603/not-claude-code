from typing import Any
import json
import subprocess
import select
import time
import logging
from venv import logger

logger = logging.getLogger(__name__)


def read_lsp_message(process: subprocess.Popen[bytes]) -> dict[str, Any] | None:
    if not process.stdout:
        return None

    rlist, _, _ = select.select([process.stdout], [], [], 0.1)
    if not rlist:
        return None

    try:
        headers = {}
        while True:
            line = process.stdout.readline()
            if not line:
                return None
            line = line.decode("utf-8")
            if line == "\r\n":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()

        if "Content-Length" not in headers:
            return None

        content_length = int(headers["Content-Length"])
        content = process.stdout.read(content_length)
        if not content:
            return None

        return json.loads(content.decode("utf-8"))
    except Exception as e:
        logger.error(f"Error reading LSP message: {e}")
        return None


def collect_diagnostics(
    process: subprocess.Popen[bytes], file_uri: str, timeout: float = 10.0
) -> list[str]:
    diagnostics = []
    start_time = time.time()

    while time.time() - start_time < timeout:
        message = read_lsp_message(process)
        if message and message.get("method") == "textDocument/publishDiagnostics":
            params = message.get("params", {})
            if params.get("uri") == file_uri:
                for diag in params.get("diagnostics", []):
                    severity = diag.get("severity", 1)
                    message_text = diag.get("message", "")
                    line = diag.get("range", {}).get("start", {}).get("line", 0) + 1
                    severity_map = {1: "Error", 2: "Warning", 3: "Info", 4: "Hint"}
                    diagnostics.append(
                        f"{severity_map.get(severity, 'Unknown')}: {message_text} (Line {line})"
                    )
                return diagnostics
        time.sleep(0.1)

    return diagnostics
