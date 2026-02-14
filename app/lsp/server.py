from pathlib import Path
import subprocess
import json
import shutil
import logging
import os
import time

from app.lsp.diagnostics import collect_diagnostics, read_lsp_message

logger = logging.getLogger(__name__)


class LanguageServer:
    def __init__(self):
        self.open_file_uris: set[str] = set()
        self.process: subprocess.Popen[bytes] | None = None

    def initialize(self):
        if not shutil.which("pyright"):
            logger.error("pyright not installed")
            return

        try:
            self.process = subprocess.Popen(
                ["pyright-langserver", "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )

            initialize_params = {
                "processId": os.getpid(),
                "rootUri": Path.cwd().as_uri(),
                "capabilities": {},
                "trace": "verbose",
            }

            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": initialize_params,
            }

            json_content = json.dumps(initialize_request).encode("utf-8")
            content_length = len(json_content)
            header = f"Content-Length: {content_length}\r\n\r\n".encode("utf-8")

            if self.process.stdin:
                self.process.stdin.write(header + json_content)
                self.process.stdin.flush()

                time.sleep(0.5)

                response = read_lsp_message(self.process)
                if not response:
                    logger.error("No response from language server initialization")
                    self.process.terminate()
                    return

                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "initialized",
                    "params": {},
                }

                json_content = json.dumps(initialized_notification).encode("utf-8")
                header = f"Content-Length: {len(json_content)}\r\n\r\n".encode("utf-8")
                self.process.stdin.write(header + json_content)
                self.process.stdin.flush()

                logger.info("Language server initialized")

        except Exception as e:
            logger.error(f"Failed to start language server: {e}")

    def send_did_read_notification(
        self,
        requested_path: Path,
        content: str,
    ):
        if not self.process or not self.process.stdin:
            return
        uri = requested_path.as_uri()
        if uri in self.open_file_uris:
            return
        did_open_notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": uri,
                    "languageId": "python",
                    "version": 1,
                    "text": content,
                }
            },
        }
        try:
            json_content = json.dumps(did_open_notification).encode("utf-8")
            content_length = len(json_content)
            header = f"Content-Length: {content_length}\r\n\r\n".encode("utf-8")
            self.process.stdin.write(header + json_content)
            self.process.stdin.flush()
            self.open_file_uris.add(uri)
            return
        except Exception as e:
            logger.error(f"Failed to send didOpen notification: {e}")

    def send_did_change_notification(self, requested_path: Path, content: str) -> str:
        if not self.process or not self.process.stdin:
            return ""
        self.send_did_read_notification(requested_path, content)
        uri = requested_path.as_uri()
        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/didChange",
            "params": {
                "textDocument": {
                    "uri": uri,
                    "version": 2,
                },
                "contentChanges": [{"text": content}],
            },
        }

        try:
            json_content = json.dumps(notification).encode("utf-8")
            header = f"Content-Length: {len(json_content)}\r\n\r\n".encode("utf-8")
            self.process.stdin.write(header + json_content)
            self.process.stdin.flush()

            diags = collect_diagnostics(self.process, uri)
            if diags:
                diagnostics_output = "\nDiagnostics:\n" + "\n".join(diags)
            else:
                diagnostics_output = "\nNo diagnostics returned."
            return diagnostics_output
        except Exception as e:
            logger.error(f"LSP Error: {e}")
        return ""
