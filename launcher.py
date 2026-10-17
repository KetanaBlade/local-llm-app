"""
Single-Instance Desktop Launcher for Local AI Studio.

Features:
- Zero Duplicate Instances: If the studio is already running, it simply focuses/opens
  the browser app window without spawning duplicate background processes.
- Silent Launch: Runs cleanly in background without lingering command prompt windows.
- Native App Window: Launches Microsoft Edge or Google Chrome in standalone '--app' mode
  (frameless, dedicated taskbar icon, no address bar clutter), falling back to the default browser.
- Auto-Spawns Ollama & FastAPI: Verifies that Ollama and Uvicorn are up; starts them if offline.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SERVER_URL = "http://localhost:8000"
STATUS_ENDPOINT = "http://127.0.0.1:8000/api/system/status"
OLLAMA_STATUS = "http://127.0.0.1:11434/api/tags"

DETACHED_FLAGS = 0
if platform.system() == "Windows":
    # CREATE_NO_WINDOW (0x08000000) | DETACHED_PROCESS (0x00000008)
    DETACHED_FLAGS = 0x08000000 | 0x00000008


def is_service_alive(url: str, timeout: float = 0.8) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LocalAIStudioLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def find_ollama_binary() -> Optional[Path]:
    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(local_app) / "Programs" / "Ollama" / "ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def open_browser_app(url: str) -> None:
    """
    Open url in a frameless application window (Edge/Chrome '--app' mode)
    or standard browser window as fallback.
    """
    edge_candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    chrome_candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]

    for p in edge_candidates:
        if p.exists():
            try:
                subprocess.Popen([str(p), f"--app={url}"], creationflags=DETACHED_FLAGS, close_fds=True)
                return
            except Exception:
                pass

    for p in chrome_candidates:
        if p.exists():
            try:
                subprocess.Popen([str(p), f"--app={url}"], creationflags=DETACHED_FLAGS, close_fds=True)
                return
            except Exception:
                pass

    webbrowser.open(url)


def main() -> None:
    # 1. Single-Instance Check: If server is already running, just open the browser and exit!
    if is_service_alive(STATUS_ENDPOINT, timeout=0.8):
        open_browser_app(SERVER_URL)
        sys.exit(0)

    # 2. Ensure Ollama daemon is active
    if not is_service_alive(OLLAMA_STATUS, timeout=0.5):
        ollama_bin = find_ollama_binary()
        if ollama_bin:
            try:
                subprocess.Popen(
                    [str(ollama_bin), "serve"],
                    cwd=str(ROOT_DIR),
                    creationflags=DETACHED_FLAGS,
                    close_fds=True,
                )
            except Exception as exc:
                print(f"[Warning] Failed to start Ollama daemon: {exc}")

    # 3. Launch Uvicorn FastAPI server
    python_exe = sys.executable
    # On Windows, prefer 'python.exe' over 'pythonw.exe' for child processes
    if python_exe.lower().endswith("pythonw.exe"):
        py_normal = Path(python_exe).parent / "python.exe"
        if py_normal.exists():
            python_exe = str(py_normal)

    subprocess.Popen(
        [
            python_exe,
            "-u",
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        cwd=str(ROOT_DIR),
        creationflags=DETACHED_FLAGS,
        close_fds=True,
    )

    # 4. Wait for server to become responsive (up to 12 seconds)
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < 12.0:
        if is_service_alive(STATUS_ENDPOINT, timeout=0.5):
            server_ready = True
            break
        time.sleep(0.25)

    # 5. Open browser app window
    open_browser_app(SERVER_URL)


if __name__ == "__main__":
    main()
