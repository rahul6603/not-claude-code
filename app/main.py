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
from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog
from textual import work
from rich.markdown import Markdown

from .lsp.server import LanguageServerManager
from .tools.bash import execute_bash_tool
from .tools.definitions import TOOL_DEFINITIONS
from .tools.read import execute_read_tool
from .tools.write import execute_write_tool
from .config import API_KEY, BASE_URL

logger = logging.getLogger(__name__)


class ChatApp(App[None]):
    CSS = """
    Input {
        dock: bottom;
    }
    RichLog {
        height: 1fr;
        border: solid green;
    }
    """

    def __init__(self):
        super().__init__()
        self.client: OpenAI | None = None
        self.language_server_manager: LanguageServerManager = LanguageServerManager()
        self.conversation_history: list[ChatCompletionMessageParam] = []

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, wrap=True)
        yield Input(placeholder="How can I help you today?")

    def on_mount(self) -> None:
        if not API_KEY:
            self.query_one(RichLog).write(
                "[bold red]Error:[/bold red] OpenRouter API key is not set"
            )
            self.query_one(Input).disabled = True
            return
        self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.query_one(Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return

        self.query_one(Input).value = ""
        self.query_one(Input).disabled = True

        log = self.query_one(RichLog)
        log.write(f"[bold green]User[/bold green]\n{user_input}")

        self.conversation_history.append(
            ChatCompletionUserMessageParam(role="user", content=user_input)
        )

        self.process_response()

    def enable_input(self) -> None:
        input_widget = self.query_one(Input)
        input_widget.disabled = False
        input_widget.focus()

    @work(thread=True)
    def process_response(self) -> None:
        if not self.client:
            return
        while True:
            try:
                chat = self.client.chat.completions.create(
                    model="openrouter/free",
                    messages=self.conversation_history,
                    tools=TOOL_DEFINITIONS,
                )
            except Exception:
                self.call_from_thread(
                    self.query_one(RichLog).write,
                    "[bold red]Error: Could not call the OpenRouter API, try again[/bold red]",
                )
                self.call_from_thread(self.enable_input)
                return

            if not chat.choices:
                self.call_from_thread(
                    self.query_one(RichLog).write,
                    "[bold red]Error:[/bold red] No choices in response",
                )
                self.call_from_thread(self.enable_input)
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
                    log = self.query_one(RichLog)
                    self.call_from_thread(log.write, "[bold blue]Assistant[/bold blue]")
                    self.call_from_thread(log.write, Markdown(content))
                    self.conversation_history.append(assistant_message)
                self.call_from_thread(self.enable_input)
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
                        tool_response = execute_read_tool(
                            self.language_server_manager, arguments
                        )
                    elif function_name == "Write":
                        tool_response = execute_write_tool(
                            self.language_server_manager, arguments
                        )
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

            self.conversation_history.append(assistant_message)
            self.conversation_history.extend(tool_messages)


def main():
    app = ChatApp()
    app.run()


if __name__ == "__main__":
    main()
