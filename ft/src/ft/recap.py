"""Parse Ansible ``PLAY RECAP`` lines from captured run logs.

``ft host validate`` and the fleet checks both judge a run by its recap
counters, so the parsing lives here once. Logs may carry ANSI colour codes,
which are stripped before matching.
"""

from __future__ import annotations

import re

ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
ANSIBLE_PLAY_RECAP_PATTERN = re.compile(
    r"^(?:.*\|\s*)?(?P<target>[^\n:|]+?)\s*:\s*"
    r"ok=(?P<ok>\d+)\s+"
    r"changed=(?P<changed>\d+)\s+"
    r"unreachable=(?P<unreachable>\d+)\s+"
    r"failed=(?P<failed>\d+)\s+"
    r"skipped=(?P<skipped>\d+)\s+"
    r"rescued=(?P<rescued>\d+)\s+"
    r"ignored=(?P<ignored>\d+)\s*$",
    re.MULTILINE,
)
RECAP_COUNTERS = (
    "ok",
    "changed",
    "unreachable",
    "failed",
    "skipped",
    "rescued",
    "ignored",
)


def strip_ansi(text: str) -> str:
    """Remove ANSI colour and cursor escape sequences.

    Args:
        text: Captured terminal output.

    Returns:
        The text without escape sequences.
    """
    return ANSI_ESCAPE_PATTERN.sub("", text)


def parse_play_recaps(log_text: str) -> list[tuple[str, dict[str, int]]]:
    """Return every recap line in the order the log printed them.

    A log can hold several plays, such as the check, real, and second passes of
    ``ft host validate``, so each recap line is kept.

    Args:
        log_text: Full Ansible log text, with or without ANSI codes.

    Returns:
        ``(target, counters)`` pairs in log order.
    """
    return [
        (
            match.group("target").strip(),
            {name: int(match.group(name)) for name in RECAP_COUNTERS},
        )
        for match in ANSIBLE_PLAY_RECAP_PATTERN.finditer(strip_ansi(log_text))
    ]
