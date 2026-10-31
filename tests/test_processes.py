"""Shell timeout and cancellation must stop descendants and close their pipes."""

import asyncio
import os
import shlex
import subprocess
import sys
import time

import pytest

from forgecli.processes import run_shell_command


def _command(*args):
    values = [str(arg) for arg in args]
    return subprocess.list2cmdline(values) if os.name == "nt" else shlex.join(values)


def _heartbeat_command(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    child = tmp_path / "child.py"
    child.write_text(
        "import pathlib, time\n"
        f"path = pathlib.Path({str(heartbeat)!r})\n"
        "for i in range(100):\n"
        "    path.write_text(str(i))\n"
        "    time.sleep(0.03)\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess, sys\n"
        f"subprocess.run([sys.executable, {str(child)!r}], check=True)\n",
        encoding="utf-8",
    )
    return _command(sys.executable, parent), heartbeat


@pytest.mark.asyncio
async def test_shell_output_status_and_working_directory(tmp_path):
    command = _command(
        sys.executable, "-c",
        "import os, sys; print(os.getcwd()); print('stderr', file=sys.stderr); sys.exit(7)",
    )
    output, returncode = await run_shell_command(command, timeout=5, cwd=str(tmp_path))
    assert str(tmp_path).encode() in output
    assert b"stderr" in output
    assert returncode == 7


@pytest.mark.asyncio
async def test_timeout_stops_child_and_closes_output_pipe(tmp_path):
    command, heartbeat = _heartbeat_command(tmp_path)
    started = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        await run_shell_command(command, timeout=0.5)
    assert time.monotonic() - started < 2
    assert heartbeat.exists(), "Child did not start before timeout"
    last_value = heartbeat.read_text()
    await asyncio.sleep(0.15)
    assert heartbeat.read_text() == last_value


@pytest.mark.asyncio
async def test_cancellation_stops_child_and_closes_output_pipe(tmp_path):
    command, heartbeat = _heartbeat_command(tmp_path)
    task = asyncio.create_task(run_shell_command(command, timeout=5))
    try:
        async with asyncio.timeout(3):
            while not heartbeat.exists():
                await asyncio.sleep(0.01)
    finally:
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert time.monotonic() - started < 2
    last_value = heartbeat.read_text()
    await asyncio.sleep(0.15)
    assert heartbeat.read_text() == last_value
