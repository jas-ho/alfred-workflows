"""Actual SIGTERM must reap a helper's native child before returning."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("helper", ["desktop.py", "open_app.py"])
def test_sigterm_reaps_native_subprocess(helper):
    module = Path(__file__).resolve().parents[1] / "workflows/new-workspace" / helper
    code = r"""
import importlib.util, os, signal, subprocess, sys, threading, time
spec = importlib.util.spec_from_file_location('helper', sys.argv[1])
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
signal.signal(signal.SIGTERM, helper.interrupted)
original = subprocess.Popen
children = []
def tracked(*args, **kwargs):
    child = original(*args, **kwargs)
    children.append(child)
    # Send the same signal hs.task:terminate sends, while run waits on its child.
    threading.Timer(.15, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    threading.Timer(.25, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    return child
subprocess.Popen = tracked
try:
    subprocess.run([sys.executable, '-c', 'import time; time.sleep(10)'], check=True)
except RuntimeError as error:
    assert 'interrupted' in str(error)
    assert children[0].poll() is not None, 'child still running after parent interruption'
    time.sleep(.3)  # A second stop must not interrupt recovery/cleanup.
else:
    raise AssertionError('interruption was swallowed')
finally:
    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(module)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
