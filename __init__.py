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

# --- Configuration ---
SLOW_TOOL_THRESHOLD = 30.0  # seconds
NOTIFICATION_COOLDOWN = 10.0  # seconds between same-type notifications
_MAX_START_TIMES = 2000  # prevent memory leak if post_tool_call is skipped

# --- State ---
_start_times: dict[str, float] = {}
_last_notified: dict[str, float] = {}  # key → last timestamp


def _should_notify(key: str) -> bool:
    """Return True if the notification is not within the cooldown window."""
    now = time.time()
    last = _last_notified.get(key, 0)
    if now - last < NOTIFICATION_COOLDOWN:
        return False
    _last_notified[key] = now
    # Also prune old entries periodically
    if len(_last_notified) > _MAX_START_TIMES:
        cutoff = now - 60
        for stale_key in [k for k, v in _last_notified.items() if v <= cutoff]:
            del _last_notified[stale_key]
    return True


def _notify(title: str, message: str, sound: str = "default", key: str = "") -> None:
    """Fire-and-forget macOS desktop notification via terminal-notifier."""
    if key and not _should_notify(key):
        return
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
    key = f"{task_id}:{tool_name}"
    _start_times[key] = time.time()
    # Prune if dict grows too large
    if len(_start_times) > _MAX_START_TIMES:
        cutoff = time.time() - 60
        for stale_key in [k for k, v in _start_times.items() if v <= cutoff]:
            del _start_times[stale_key]


def _on_post_tool_call(tool_name: str, args: dict, result: str, task_id: str, **kwargs) -> None:
    """Detect tool errors and slow tool executions."""
    key = f"{task_id}:{tool_name}"
    start = _start_times.pop(key, None)

    # Slow tool notification
    if start is not None:
        elapsed = time.time() - start
        if elapsed > SLOW_TOOL_THRESHOLD:
            _notify(
                f"\u23f1 Slow tool: {tool_name}",
                f"Took {elapsed:.0f}s",
                "Hero",
                key=f"slow:{tool_name}",
            )

    # Error notification
    try:
        parsed = json.loads(result)
        err = parsed.get("error")
        if err:
            _notify("\u274c Tool error", f"{tool_name}: {str(err)[:80]}", "Basso",
                    key=f"error:{tool_name}")
    except (json.JSONDecodeError, TypeError):
        pass


def _on_clarify(question: str, choices, session_id: str, **kwargs) -> None:
    """Notify when the agent needs user input via clarify."""
    is_open = not choices
    if is_open:
        detail = "needs your answer"
    else:
        labels = [str(c) for c in choices[:3]]
        detail = f"Choose: {', '.join(labels)}"
    _notify("\u2753 Hermes needs you", f"{question[:80]}\u2026 {detail}", "Ping",
            key=f"clarify:{session_id}")


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
        _notify("\u2705 Hermes done", preview, "Hero", key=f"done:{session_id}")


def register(ctx) -> None:
    """Register all hooks."""
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_clarify", _on_clarify)
    ctx.register_hook("post_llm_call", _on_post_llm_call)

