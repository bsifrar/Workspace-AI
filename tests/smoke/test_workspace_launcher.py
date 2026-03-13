from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_workspace_command(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["./workspace.sh", *args],
        cwd=REPO_ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_workspace_help_mentions_local_default():
    result = run_workspace_command("help")
    assert result.returncode == 0
    assert "start/status/smoke run in local null mode" in result.stdout


def test_workspace_status_defaults_to_null_mode(monkeypatch):
    env = {
        "WORKSPACE_ADAPTER_MODE": "",
        "WORKSPACE_EXTERNAL_BASE_URL": "",
    }
    result = run_workspace_command("status", env=env)
    assert result.returncode == 0
    assert "Adapter mode:  null" in result.stdout


def test_workspace_status_external_mode_is_explicit(monkeypatch):
    env = {"WORKSPACE_ADAPTER_MODE": "external", "WORKSPACE_EXTERNAL_BASE_URL": "http://127.0.0.1:65535"}
    result = run_workspace_command("status", env=env)
    assert result.returncode == 0
    assert "Adapter mode:  external" in result.stdout
    assert "EXTERNAL MODE ACTIVE" in result.stdout
