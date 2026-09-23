import os
import socket
import subprocess
import sys
import time

import httpx


def test_uvicorn_starts_as_separate_process(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path / "server-data"),
        "DEMO_MODE": "false",
        "CALCULATION_MODULE": "backend.calculations.missing",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(timeout=1, trust_env=False) as client:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                assert process.poll() is None, process.stderr.read().decode(errors="replace")
                try:
                    response = client.get(f"http://127.0.0.1:{port}/api/health")
                    assert response.status_code == 200
                    assert response.json()["status"] == "ok"
                    assert response.json()["calculations"]["available"] is False
                    assert response.json()["ai"]["configured"] is False
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    time.sleep(0.05)
            else:
                raise AssertionError("Uvicorn did not start within 15 seconds")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stderr.close()
