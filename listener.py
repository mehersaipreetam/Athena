import subprocess
import platform
import sys
import os
import threading
from pynput import keyboard

HOTKEY = "<alt>+a"
MAIN_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../main.py"))


def launch_agent():
    system = platform.system()

    if system == "Linux":
        subprocess.Popen(["gnome-terminal", "--", "python3", MAIN_SCRIPT_PATH])
    elif system == "Darwin":  # macOS
        subprocess.Popen([
            "osascript",
            "-e",
            f'tell app "Terminal" to do script "python3 {MAIN_SCRIPT_PATH}"'
        ])
    elif system == "Windows":
        subprocess.Popen(["start", "cmd", "/k", f"python {MAIN_SCRIPT_PATH}"], shell=True)
    else:
        print(f"Unsupported OS: {system}")


def on_activate():
    print("Hotkey detected! Spinning up Athena...")
    launch_agent()


def start_listener():
    hotkey = keyboard.HotKey(
        keyboard.HotKey.parse(HOTKEY),
        on_activate
    )

    def for_canonical(f):
        return lambda k: f(l.canonical(k))

    from pynput.keyboard import Listener
    with Listener(
        on_press=lambda k: hotkey.press(k),
        on_release=lambda k: hotkey.release(k)
    ) as l:
        l.join()

# Detach process 
# Linux/macOS: fork and exit parent
# Windows: relaunch as detached process
def detach_process():
    system = platform.system()

    if system in ["Linux", "Darwin"]:
        # Fork and exit parent
        if os.fork() > 0:
            sys.exit(0)
    elif system == "Windows":
        # TODO: Test this on Windows
        # Relaunch as detached process
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            [sys.executable] + sys.argv,
            creationflags=DETACHED_PROCESS,
            close_fds=True
        )
        sys.exit(0)


if __name__ == "__main__":
    detach_process() 

    listener_thread = threading.Thread(target=start_listener, daemon=True)
    listener_thread.start()

    print(f"Headless hotkey listener running! Press {HOTKEY} to launch Athena.")

    # Keep main thread alive
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("Listener terminated gracefully.")
