from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
import importlib.util
from pathlib import Path


APP_NAME = "Mythos"
ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"
NATIVE_APP_FILE = ROOT / "mythos_native.py"
RUNTIME_DIR = ROOT / ".mythos_runtime"
PID_FILE = RUNTIME_DIR / "streamlit.pid"
LOG_FILE = RUNTIME_DIR / "streamlit.log"
ENV_FILE = ROOT / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def mythos_host() -> str:
    return os.getenv("MYTHOS_HOST", "localhost").strip() or "localhost"


def mythos_port() -> int:
    raw_port = os.getenv("MYTHOS_PORT", "8501").strip()
    try:
        return int(raw_port)
    except ValueError:
        return 8501


def mythos_url() -> str:
    return f"http://{mythos_host()}:{mythos_port()}"


def is_url_available(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_process_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def streamlit_running() -> bool:
    return is_url_available(mythos_url()) or is_process_running(read_pid())


def start_streamlit() -> bool:
    RUNTIME_DIR.mkdir(exist_ok=True)
    if is_url_available(mythos_url()):
        print(f"{APP_NAME} is already available at {mythos_url()}")
        return False

    if is_process_running(read_pid()):
        print(f"{APP_NAME} process is already running. Opening {mythos_url()}")
        return False

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_FILE),
        "--server.address",
        mythos_host(),
        "--server.port",
        str(mythos_port()),
        "--server.headless",
        "true",
    ]

    log_handle = LOG_FILE.open("a", encoding="utf-8")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    print(f"Starting {APP_NAME} on {mythos_url()}...")

    for _ in range(30):
        if is_url_available(mythos_url()):
            print(f"{APP_NAME} is online.")
            return True
        if process.poll() is not None:
            print(f"{APP_NAME} stopped during startup. Check {LOG_FILE}")
            return False
        time.sleep(1)

    print(f"{APP_NAME} is still starting. Check {LOG_FILE} if it does not open.")
    return True


def open_mythos(use_window: bool = False) -> None:
    url = mythos_url()
    if use_window:
        try:
            import webview  # type: ignore

            webview.create_window(APP_NAME, url, width=1280, height=860)
            webview.start()
            return
        except Exception as exc:
            print(f"Desktop window unavailable, opening browser instead. Details: {exc}")
    webbrowser.open(url)


def open_native_shell() -> bool:
    if importlib.util.find_spec("PyQt6") is None:
        print("Native Mythos shell requires PyQt6. Install it with: pip install PyQt6")
        return False
    try:
        subprocess.Popen([sys.executable, str(NATIVE_APP_FILE)], cwd=str(ROOT))
        return True
    except Exception as exc:
        print(f"Native Mythos shell unavailable. Details: {exc}")
        return False


def stop_streamlit() -> bool:
    pid = read_pid()
    if not pid or not is_process_running(pid):
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        print(f"No tracked {APP_NAME} process is running.")
        return False

    print(f"Stopping {APP_NAME} process {pid}...")
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=10)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as exc:
        print(f"Could not stop {APP_NAME} cleanly: {exc}")
        return False
    PID_FILE.unlink(missing_ok=True)
    print(f"{APP_NAME} stopped.")
    return True


def restart_streamlit(open_after: bool = True, use_window: bool = False) -> None:
    stop_streamlit()
    time.sleep(1)
    start_streamlit()
    if open_after:
        open_mythos(use_window=use_window)


def run_tray() -> None:
    try:
        import pystray  # type: ignore
        from PIL import Image, ImageDraw  # type: ignore
    except Exception as exc:
        print(f"System tray is unavailable. Install pystray and pillow to enable it. Details: {exc}")
        open_mythos()
        return

    def make_icon() -> Image.Image:
        image = Image.new("RGB", (64, 64), "#101827")
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill="#2dd4bf")
        draw.text((23, 20), "M", fill="#101827")
        return image

    def on_open(icon, item):
        open_mythos()

    def on_restart(icon, item):
        restart_streamlit(open_after=False)

    def on_stop(icon, item):
        stop_streamlit()

    def on_exit(icon, item):
        stop_streamlit()
        icon.stop()

    start_streamlit()
    icon = pystray.Icon(
        APP_NAME,
        make_icon(),
        APP_NAME,
        pystray.Menu(
            pystray.MenuItem("Open Mythos", on_open),
            pystray.MenuItem("Restart Mythos", on_restart),
            pystray.MenuItem("Stop Mythos", on_stop),
            pystray.MenuItem("Exit", on_exit),
        ),
    )
    icon.run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Desktop launcher for Project Mythos.")
    parser.add_argument("--start", action="store_true", help="Start Mythos.")
    parser.add_argument("--stop", action="store_true", help="Stop Mythos.")
    parser.add_argument("--restart", action="store_true", help="Restart Mythos.")
    parser.add_argument("--open", action="store_true", help="Open Mythos without starting a new process.")
    parser.add_argument("--tray", action="store_true", help="Run Mythos with a system tray menu if pystray is installed.")
    parser.add_argument("--window", action="store_true", help="Open Mythos in a pywebview desktop window if installed.")
    parser.add_argument("--native", action="store_true", help="Open the futuristic PyQt6 Mythos native shell if installed.")
    parser.add_argument("--no-open", action="store_true", help="Start without opening the app.")
    return parser.parse_args()


def main() -> None:
    load_env_file()
    args = parse_args()

    if args.stop:
        stop_streamlit()
        return
    if args.restart:
        restart_streamlit(open_after=not args.no_open, use_window=args.window)
        return
    if args.tray:
        run_tray()
        return
    if args.open:
        open_mythos(use_window=args.window)
        return

    start_streamlit()
    if not args.no_open:
        if args.native:
            if not open_native_shell():
                open_mythos(use_window=args.window)
        else:
            open_mythos(use_window=args.window)


if __name__ == "__main__":
    main()
