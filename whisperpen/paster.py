from __future__ import annotations

import platform
import time

try:
    import pyautogui
except ImportError as exc:  # pragma: no cover - runtime dependency
    pyautogui = None
    PYAUTOGUI_IMPORT_ERROR = exc
else:
    PYAUTOGUI_IMPORT_ERROR = None

try:
    import pyperclip
except ImportError as exc:  # pragma: no cover - runtime dependency
    pyperclip = None
    PYPERCLIP_IMPORT_ERROR = exc
else:
    PYPERCLIP_IMPORT_ERROR = None


DEFAULT_PASTE_KEYS = ["shift", "insert"]


def copy_text(text: str) -> None:
    if pyperclip is None:
        raise RuntimeError(
            "pyperclip is required for clipboard copy. Install requirements.txt first."
        ) from PYPERCLIP_IMPORT_ERROR

    pyperclip.copy(text)


def paste_text(text: str, auto_paste: bool = True, paste_keys: list[str] | None = None) -> None:
    copy_text(text)

    if not auto_paste:
        return

    if pyautogui is None:
        raise RuntimeError(
            "pyautogui is required for auto-paste. Install requirements.txt first."
        ) from PYAUTOGUI_IMPORT_ERROR

    time.sleep(0.15)

    if paste_keys:
        pyautogui.hotkey(*paste_keys)
        return

    if platform.system() == "Darwin":
        pyautogui.hotkey("command", "v")
        return

    pyautogui.hotkey(*DEFAULT_PASTE_KEYS)
