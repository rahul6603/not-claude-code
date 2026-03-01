# agentic-code-assistant

A simple code assistant built to learn about AI agents.

## Features

- A minimal TUI
- Response streaming
- Tool usage: read/write file and command execution
- Python LSP integration
- Managing conversation history

## To be implemented

- Additional tools
- More language servers
- Code diff visualization
- etc.

## Requirements

- Python 3.14 or higher
- OpenRouter API key
- pyright-langserver (for Python diagnostics)

## How to use

Install dependencies using uv:
```bash
uv sync
```

Create a `.env` file in the project root:
```bash
cp .env.example .env
```

Add OpenRouter API key to `.env`:
```
OPENROUTER_API_KEY=your_api_key_here
```

Run the application:
```bash
uv run -m app.main
```
