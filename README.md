# hermes-desktop-notifier

Hermes Agent plugin — sends macOS desktop notifications via `terminal-notifier`.

## Prerequisites

- macOS
- `terminal-notifier` — `brew install terminal-notifier`

## Installation

```bash
hermes plugins install pedh/hermes-desktop-notifier
```

Or manually:

```bash
mkdir -p ~/.hermes/plugins/desktop-notifier
cp plugin.yaml __init__.py ~/.hermes/plugins/desktop-notifier/
```

## Features

- **Turn complete** — notifies when the agent finishes a reply
- **Slow tool detection** — notifies when a tool takes longer than 30s
- **Tool errors** — notifies when a tool call fails
- **Clarify prompts** — notifies when the agent needs user input

