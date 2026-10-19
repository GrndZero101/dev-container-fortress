"""Run and judge the EC2 test fleet's verification checks in parallel.

Each fleet host gets the check its OS supports: Ubuntu runs the one-liner on
the box twice, and every other OS runs ``ft host validate`` from the operator's
machine. This module plans those steps, runs one thread per host, writes one
log per step, and judges each step from its exit code and Ansible recap. The
CLI layer builds the SSH and ``ft`` commands and renders progress.
"""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ft.recap import parse_play_recaps

# The check each OS gets. The one-liner's host mode supports Ubuntu only.
ONE_LINER_OSES = frozenset({"ubuntu"})

QUEUED = "queued"
RUNNING = "running"
PASSED = "passed"
FAILED = "failed"


@dataclass(frozen=True)
class CheckStep:
    """One command in a host's check.

    Attributes:
        label: Short name shown in progress output, such as ``pass 1``.
        command: The argv to run.
        log_path: Where the step's combined output is written.
        expect_converged: Whether the step's last recap must report
            ``changed=0``, as a re-run on a converged host should.
    """

    label: str
    command: list[str]
    log_path: Path
    expect_converged: bool = False


@dataclass
class HostCheck:
    """A fleet host's planned check and its live state.

    Attributes:
        host: The fleet host target name.
        os: The host's OS, from the fleet outputs.
        architecture: ``amd64`` or ``arm64``.
        check: ``one-liner`` or ``validate``.
        steps: The steps, run in order until one fails.
        status: One of queued, running, passed, or failed.
        phase: The label of the step running now, or the last one run.
        started: Monotonic start time, when started.
        finished: Monotonic finish time, when finished.
        results: One short result per finished step, such as ``changed=26``.
        detail: Why the check failed, when it did.
    """

    host: str
    os: str
    architecture: str
    check: str
    steps: list[CheckStep]
    status: str = QUEUED
    phase: str = ""
    started: float | None = None
    finished: float | None = None
    results: list[str] = field(default_factory=list)
    detail: str = ""

    def elapsed(self, now: float | None = None) -> float:
        """Return the seconds spent so far, or in total once finished.

        Args:
            now: Monotonic time to measure against; defaults to the clock.

        Returns:
            Elapsed seconds, or ``0.0`` before the check starts.
        """
        if self.started is None:
            return 0.0
        end = self.finished if self.finished is not None else (now or time.monotonic())
        return end - self.started


def check_kind(os_name: str) -> str:
    """Return the check a fleet host's OS gets.

    Args:
        os_name: The host's OS, such as ``ubuntu`` or ``alpine``.

    Returns:
        ``one-liner`` for OSes the installer supports, else ``validate``.
    """
    return "one-liner" if os_name in ONE_LINER_OSES else "validate"


def judge_step(step: CheckStep, returncode: int, log_text: str) -> tuple[bool, str]:
    """Decide whether one step passed, and summarize it.

    Args:
        step: The step that ran.
        returncode: Its exit code.
        log_text: Its captured output.

    Returns:
        ``(passed, summary)``. The summary lists the ``changed`` count of every
        recap in the log, or explains the failure.
    """
    recaps = [counters for _, counters in parse_play_recaps(log_text)]
    changed = ", ".join(f"changed={counters['changed']}" for counters in recaps)
    if returncode != 0:
        return False, f"exit {returncode}" + (f" ({changed})" if changed else "")
    if not recaps:
        return False, "no Ansible recap in the log"
    last = recaps[-1]
    if last["failed"] or last["unreachable"]:
        return False, changed + f", failed={last['failed']}"
    if step.expect_converged and last["changed"]:
        return False, f"{changed}: expected changed=0"
    return True, changed


def run_host_check(
    check: HostCheck,
    *,
    timeout_seconds: float,
    on_update: Callable[[HostCheck], None],
) -> None:
    """Run one host's steps in order, stopping at the first failure.

    Args:
        check: The host check to run; its state is updated in place.
        timeout_seconds: The limit for each step.
        on_update: Called after every state change.

    Side effects:
        Runs the step commands with stdin detached, because concurrent Ansible
        runs refuse a shared non-blocking stdin, and writes each step's log.
    """
    check.status, check.started = RUNNING, time.monotonic()
    on_update(check)
    for step in check.steps:
        check.phase = step.label
        on_update(check)
        step.log_path.parent.mkdir(parents=True, exist_ok=True)
        with step.log_path.open("w", encoding="utf-8") as log:
            try:
                returncode = subprocess.run(
                    step.command,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=timeout_seconds,
                    check=False,
                ).returncode
            except subprocess.TimeoutExpired:
                returncode = None
        if returncode is None:
            passed, summary = False, f"timed out after {timeout_seconds / 60:.0f} min"
        else:
            log_text = step.log_path.read_text(encoding="utf-8", errors="replace")
            passed, summary = judge_step(step, returncode, log_text)
        check.results.append(f"{step.label}: {summary}")
        if not passed:
            check.status, check.detail = FAILED, f"{step.label}: {summary}"
            break
    else:
        check.status = PASSED
    check.finished = time.monotonic()
    on_update(check)


def run_fleet_checks(
    checks: Sequence[HostCheck],
    *,
    timeout_seconds: float,
    on_update: Callable[[HostCheck], None],
) -> None:
    """Run every host's check at once and wait for all of them.

    Args:
        checks: The planned host checks.
        timeout_seconds: The limit for each step.
        on_update: Called after every state change, from worker threads; it
            must be thread-safe.
    """
    threads = [
        threading.Thread(
            target=run_host_check,
            args=(check,),
            kwargs={"timeout_seconds": timeout_seconds, "on_update": on_update},
            name=f"fleet-check-{check.host}",
            daemon=True,
        )
        for check in checks
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def format_duration(seconds: float) -> str:
    """Render seconds as ``Xm YYs``.

    Args:
        seconds: A duration in seconds.

    Returns:
        The duration, such as ``5m 24s``.
    """
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes}m {rest:02d}s"


def markdown_summary(checks: Sequence[HostCheck]) -> str:
    """Render the results as a markdown table for milestone notes.

    Args:
        checks: Finished host checks.

    Returns:
        A markdown table with one row per host.
    """
    lines = [
        "| Host | Check | Result | Time |",
        "| --- | --- | --- | --- |",
    ]
    for check in checks:
        mark = "✅" if check.status == PASSED else "❌"
        lines.append(
            f"| {check.host} ({check.architecture}) | {check.check} | "
            f"{mark} {'; '.join(check.results) or check.status} | "
            f"{format_duration(check.elapsed())} |"
        )
    return "\n".join(lines)
