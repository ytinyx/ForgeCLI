"""Run shell commands without leaving their children behind on cancellation."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if os.name == "nt":
        if proc.returncode is not None:
            return
        # Killing cmd.exe alone leaves its child holding the output pipe open.
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/PID", str(proc.pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(killer.wait(), timeout=5)
            except asyncio.TimeoutError:
                killer.kill()
                await killer.wait()
        except OSError:
            pass
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
    else:
        # Each command starts a new session, so this group belongs to us.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)


async def run_shell_command(
    command: str, *, timeout: float, cwd: str | None = None,
) -> tuple[bytes, int]:
    """Capture merged output, cleaning up descendants before timeout/cancel escapes."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
        start_new_session=os.name != "nt",
    )
    communication = asyncio.create_task(proc.communicate())
    try:
        # Keep draining the pipe during cleanup instead of cancelling its reader.
        stdout, _ = await asyncio.wait_for(
            asyncio.shield(communication), timeout=timeout,
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        await _kill_process_tree(proc)
        await communication
        raise
    return stdout or b"", proc.returncode or 0
