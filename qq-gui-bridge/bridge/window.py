import io
import time

import mss
import numpy as np
import pyautogui
import pyperclip
import win32clipboard
import win32con
import win32gui
from PIL import Image
from pywinauto import Application


def find_qq_windows():
    items = []

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        if title != "QQ" or class_name != "Chrome_WidgetWin_1":
            return True
        rect = win32gui.GetWindowRect(hwnd)
        area = max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])
        items.append({
            "hwnd": hwnd,
            "title": title,
            "class_name": class_name,
            "rect": rect,
            "area": area,
        })
        return True

    win32gui.EnumWindows(callback, None)
    items.sort(key=lambda item: item["area"], reverse=True)
    return items


def get_window_rect(hwnd):
    return list(win32gui.GetWindowRect(hwnd))


def move_window(hwnd, rect) -> None:
    left, top, right, bottom = rect
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOP,
        left,
        top,
        right - left,
        bottom - top,
        win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
    )


def focus_window(hwnd) -> bool:
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    try:
        win32gui.BringWindowToTop(hwnd)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.3)
    if win32gui.GetForegroundWindow() != hwnd:
        try:
            app = Application(backend="uia").connect(handle=hwnd)
            app.window(handle=hwnd).set_focus()
        except Exception:
            pass
    time.sleep(0.3)
    return win32gui.GetForegroundWindow() == hwnd


def absolute_rect(window_rect, relative_rect):
    left, top, right, bottom = window_rect
    rel_left, rel_top, rel_right, rel_bottom = relative_rect
    return {
        "left": left + rel_left,
        "top": top + rel_top,
        "width": rel_right - rel_left,
        "height": rel_bottom - rel_top,
    }


def absolute_point(window_rect, relative_point):
    return window_rect[0] + relative_point[0], window_rect[1] + relative_point[1]


def capture(window_rect, relative_rect):
    with mss.mss() as sct:
        shot = sct.grab(absolute_rect(window_rect, relative_rect))
        return np.array(shot)[:, :, :3].copy()


def send_text(hwnd, point, text, restore=True) -> bool:
    previous = win32gui.GetForegroundWindow()
    if not focus_window(hwnd):
        return False
    pyautogui.click(point[0], point[1])
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.8)
    if restore and previous and previous != hwnd:
        try:
            win32gui.SetForegroundWindow(previous)
        except Exception:
            pass
    return True


def set_clipboard_image(image_path) -> None:
    with Image.open(image_path) as image:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "BMP")
        data = buffer.getvalue()[14:]
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()


def send_image(hwnd, point, image_path, caption="", restore=True) -> bool:
    previous = win32gui.GetForegroundWindow()
    if not focus_window(hwnd):
        return False
    pyautogui.click(point[0], point[1])
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "a")
    if caption:
        pyperclip.copy(caption)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
    set_clipboard_image(image_path)
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.8)
    pyautogui.press("enter")
    time.sleep(1.0)
    if restore and previous and previous != hwnd:
        try:
            win32gui.SetForegroundWindow(previous)
        except Exception:
            pass
    return True


def click_point(hwnd, point, restore=False) -> bool:
    previous = win32gui.GetForegroundWindow()
    if not focus_window(hwnd):
        return False
    pyautogui.click(point[0], point[1])
    time.sleep(0.5)
    if restore and previous and previous != hwnd:
        try:
            win32gui.SetForegroundWindow(previous)
        except Exception:
            pass
    return True
