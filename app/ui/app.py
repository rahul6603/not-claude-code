from openai import AsyncOpenAI
from textual.app import App, ComposeResult
from textual.widgets import Static, TextArea
from textual.containers import VerticalScroll
from rich.markdown import Markdown
from textual.binding import Binding
from textual.message import Message
from textual import work

from app.core.agent import Agent
from app.config import API_KEY, BASE_URL


class ChatArea(TextArea):
    BINDINGS = [
        Binding("enter", "submit", "Submit", show=False, priority=True),
        Binding("ctrl+j", "insert_newline", "Newline", show=False),
    ]

    class Submitted(Message):
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    def action_submit(self):
        self.post_message(self.Submitted(self.text))
        self.clear()

    def action_insert_newline(self):
        self.insert("\n")


class ChatApp(App[None]):
    CSS = """
    ChatArea {
        dock: bottom;
        height: 5;
        border: tall $border !important;
    }
    VerticalScroll {
        height: 1fr;
    }
    .user-message {
        border: solid $border;
        margin-bottom: 1;
        padding: 0 1;
    }
    .streaming-text {
        margin-bottom: 1;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.agent: Agent | None = None
        self._streaming_widget: Static | None = None
        self._streaming_content: str = ""
        self._first_message: bool = True

    def compose(self) -> ComposeResult:
        yield VerticalScroll()
        yield ChatArea(placeholder="How can I help you today?")

    def on_mount(self) -> None:
        if not API_KEY:
            scroll = self.query_one(VerticalScroll)
            scroll.mount(
                Static("[bold red]Error:[/bold red] OpenRouter API key is not set")
            )
            self.query_one(ChatArea).disabled = True
            return
        client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)
        self.agent = Agent(
            client,
            self.handle_error,
            self.stream_token,
            self.finish_message,
        )
        self.query_one(ChatArea).focus()

    def on_chat_area_submitted(self, event: ChatArea.Submitted) -> None:
        if not self.agent:
            self.handle_error("Could not initialize the OpenRouter client, try again")
            return

        user_input = event.value.strip()
        if not user_input:
            return

        chat_area = self.query_one(ChatArea)
        chat_area.text = ""
        chat_area.disabled = True

        if self._first_message:
            chat_area.placeholder = ""
            self._first_message = False

        scroll = self.query_one(VerticalScroll)
        scroll.mount(Static(user_input, classes="user-message"))

        self.agent.add_user_message(user_input)
        self.process_response()

    def _start_streaming(self) -> None:
        self._streaming_content = ""
        self._streaming_widget = Static("", classes="streaming-text")
        scroll = self.query_one(VerticalScroll)
        scroll.mount(self._streaming_widget)
        scroll.scroll_end(animate=False)

    def stream_token(self, token: str) -> None:
        if self._streaming_widget is None:
            self._start_streaming()
        self._streaming_content += token
        if self._streaming_widget is not None:
            self._streaming_widget.update(self._streaming_content)
            scroll = self.query_one(VerticalScroll)
            scroll.scroll_end(animate=False)

    def finish_message(self, full_content: str) -> None:
        if self._streaming_widget is not None:
            self._streaming_widget.update(Markdown(full_content))
            scroll = self.query_one(VerticalScroll)
            scroll.scroll_end(animate=False)
        self._streaming_widget = None
        self._streaming_content = ""

    def handle_error(self, error_msg: str) -> None:
        scroll = self.query_one(VerticalScroll)
        scroll.mount(Static(f"[bold red]Error:[/bold red] {error_msg}"))
        scroll.scroll_end(animate=False)

    def enable_input(self) -> None:
        input_widget = self.query_one(ChatArea)
        input_widget.disabled = False
        input_widget.focus()

    @work
    async def process_response(self) -> None:
        if not self.agent:
            return
        should_continue = True
        while should_continue:
            should_continue = await self.agent.process_turn()
        self.enable_input()
