"""
desktop-notifier — macOS terminal-notifier for Hermes agent events.

Hooks:
  post_llm_call  → notification when a turn completes with a response
  pre_tool_call  → record start time for slow-tool detection
  post_tool_call → detect tool errors, notify on slow tools (>30s)
  on_clarify     → notification when agent asks a clarify question
"""

import json
import subprocess
import time
from collections import defaultdict

_start_times: dict[str, float] = {}

# Threshold in seconds — tools taking longer than this trigger a notification
SLOW_TOOL_THRESHOLD = 30.0


def _notify(title: str, message: str, sound: str = "default") -> None:
    """Fire-and-forget macOS desktop notification via terminal-notifier."""
    try:
        subprocess.Popen(
            ["terminal-notifier", "-title", title, "-message", message, "-sound", sound],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError) as e:
        print(f"[desktop-notifier] terminal-notifier failed: {e}")


def _on_pre_tool_call(tool_name: str, args: dict, task_id: str, **kwargs) -> None:
    """Record start time so we can detect slow tools in post_tool_call."""
    _start_times[f"{task_id}:{tool_name}"] = time.time()


def _on_post_tool_call(tool_name: str, args: dict, result: str, task_id: str, **kwargs) -> None:
    """Detect tool errors and slow tool executions."""
    key = f"{task_id}:{tool_name}"
    start = _start_times.pop(key, None)

    # Slow tool notification
    if start is not None:
        elapsed = time.time() - start
        if elapsed > SLOW_TOOL_THRESHOLD:
            _notify(
                f"\u23f1 \u6162\u5de5\u5177 {tool_name}",
                f"\u8017\u65f6 {elapsed:.0f}s",
                "Hero",
            )

    # Error notification
    try:
        parsed = json.loads(result)
        err = parsed.get("error")
        if err:
            _notify("\u274c \u5de5\u5177\u9519\u8bef", f"{tool_name}: {str(err)[:80]}", "Basso")
    except (json.JSONDecodeError, TypeError):
        pass


def _on_clarify(question: str, choices, session_id: str, **kwargs) -> None:
    """Notify when the agent needs user input via clarify."""
    is_open = not choices
    if is_open:
        detail = "\u9700\u8981\u4f60\u56de\u7b54"
    else:
        labels = [str(c) for c in choices[:3]]
        detail = f"\u8bf7\u9009\u62e9: {', '.join(labels)}"
    _notify("\u2753 Hermes \u9700\u8981\u4f60", f"{question[:80]}\u2026 {detail}", "Ping")


def _on_post_llm_call(
    session_id: str,
    user_message: str,
    assistant_response: str,
    model: str,
    platform: str,
    **kwargs,
) -> None:
    """Notify when the agent finishes a turn with a response."""
    if assistant_response:
        preview = assistant_response[:80] + ("\u2026" if len(assistant_response) > 80 else "")
        _notify("\u2705 Hermes \u5b8c\u6210", preview, "Hero")


def register(ctx) -> None:
    """Register all hooks."""
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_clarify", _on_clarify)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
