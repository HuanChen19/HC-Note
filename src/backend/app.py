# -*- coding: utf-8 -*-
"""HC-Note 主入口。

组装数据层、调度层、通知层与托盘层，并通过 pywebview 暴露 API 给前端。
前端以本地文件方式载入 src/ui/index.html。
"""

import ctypes
import os
import sys
import threading
import time

from datetime import datetime
from urllib.parse import quote

import storage

from notifier import Notifier
from scheduler import Scheduler, format_remaining
from storage import Store
from tray import TrayManager


# ----------------------------------------------------------------------
# 路径解析：同时兼容源码运行与 PyInstaller 打包后的运行环境
#
# 源码布局为 <root>/src/backend/app.py，因此从本文件回退三级得到项目根；
# 打包后静态资源被释放到 sys._MEIPASS，可写数据放在 exe 同级目录。
# ----------------------------------------------------------------------

def resource_root():
    """返回静态资源根目录（含 assets 与 src/ui）。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    # __file__ = <root>/src/backend/app.py -> 上溯三级到 <root>
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def data_root():
    """返回可写数据目录。打包后放到 exe 同级的 data 目录。"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = resource_root()
    return os.path.join(base, "data")


ROOT = resource_root()
UI_INDEX = os.path.join(ROOT, "src", "ui", "index.html")
ICON_ICO = os.path.join(ROOT, "assets", "icons", "app.ico")
ICON_TRAY = os.path.join(ROOT, "assets", "icons", "tray.png")


# ----------------------------------------------------------------------
# 高 DPI 适配
# ----------------------------------------------------------------------

def enable_dpi_awareness():
    """启用进程级 DPI 感知，避免高分屏下窗口内容模糊。"""
    if not sys.platform.startswith("win"):
        return
    try:
        # PROCESS_SYSTEM_DPI_AWARE = 1，在 125%/150% 缩放下保持清晰
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class Api(object):
    """暴露给前端的 JS 桥接接口。"""

    def __init__(self, controller):
        self._c = controller

    # --- 数据读取 ---

    def bootstrap(self):
        return self._c.bootstrap()

    def list_tasks(self):
        return self._c.list_tasks()

    def get_settings(self):
        return self._c.store.get_settings()

    def stats(self):
        return self._c.store.stats()

    # --- 任务写操作 ---

    def create_task(self, payload):
        return self._c.create_task(payload)

    def update_task(self, task_id, patch):
        return self._c.update_task(task_id, patch)

    def set_status(self, task_id, status):
        return self._c.set_status(task_id, status)

    def toggle_complete(self, task_id):
        return self._c.toggle_complete(task_id)

    def delete_task(self, task_id):
        return self._c.delete_task(task_id)

    def clear_completed(self):
        return self._c.clear_completed()

    def snooze_task(self, task_id, minutes):
        return self._c.snooze_task(task_id, minutes)

    # --- 设置 ---

    def update_settings(self, patch):
        return self._c.update_settings(patch)

    def set_theme(self, theme):
        return self._c.update_settings({"theme": theme})

    # --- 窗口 ---

    def hide_to_tray(self):
        return self._c.hide_window()

    def show_window(self):
        return self._c.show_window()

    def quit_app(self):
        return self._c.quit()

    def get_system_theme(self):
        return self._c.system_theme()


class Controller(object):
    """应用控制器：持有各子系统并对外提供业务方法。"""

    def __init__(self, window=None):
        self.window = window
        self.store = Store(data_root())
        settings = self.store.get_settings()
        self.notifier = Notifier(sound_enabled=settings.get("sound_enabled", True))
        self.scheduler = Scheduler(
            self.store,
            self.notifier,
            on_change=self._on_state_change,
            on_wake=self._on_system_wake,
        )
        self.tray = TrayManager(
            ICON_TRAY,
            on_show=self.show_window,
            on_quick_done=self._tray_quick_done,
            on_quit=self.quit,
            summary_provider=self._due_summary,
        )
        self.notifier.set_tray_icon(self.tray)
        self.notifier.set_action_handler(self._handle_notification_action)
        self._quitting = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start_services(self):
        self.scheduler.start()
        self.tray.start()

    def quit(self):
        if self._quitting:
            return
        self._quitting = True
        try:
            self.scheduler.stop()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.store.save(reason="quit")
        except Exception:
            pass
        window = self.window
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass
        # pywebview 的 GUI 循环在主线程，退出后进程自然结束
        os._exit(0)

    # ------------------------------------------------------------------
    # 窗口控制
    # ------------------------------------------------------------------

    def hide_window(self):
        window = self.window
        if window is None:
            return False
        try:
            window.hide()
            return True
        except Exception:
            return False

    def show_window(self):
        window = self.window
        if window is None:
            return False
        try:
            window.show()
            window.restore()
            return True
        except Exception:
            try:
                window.show()
                return True
            except Exception:
                return False

    # ------------------------------------------------------------------
    # 业务接口
    # ------------------------------------------------------------------

    def bootstrap(self):
        """一次性返回界面初始化所需的全部数据。"""
        return {
            "ok": True,
            "settings": self.store.get_settings(),
            "tasks": self._decorate_tasks(self.store.list_tasks()),
            "stats": self.store.stats(),
            "system_theme": self.system_theme(),
            "capabilities": {
                "toast": self.notifier.is_toast_available(),
                "tray": self.tray.is_available(),
            },
        }

    def list_tasks(self):
        tasks = self._decorate_tasks(self.store.list_tasks())
        return {"ok": True, "tasks": tasks, "stats": self.store.stats()}

    def create_task(self, payload):
        try:
            task = self.store.create_task(payload)
        except storage.StorageError as exc:
            return {"ok": False, "error": str(exc)}
        self.scheduler.trigger_check()
        self._refresh_ui()
        return {"ok": True, "task": self._decorate(task), "stats": self.store.stats()}

    def update_task(self, task_id, patch):
        try:
            task = self.store.update_task(task_id, patch)
        except storage.StorageError as exc:
            return {"ok": False, "error": str(exc)}
        if task is None:
            return {"ok": False, "error": "任务不存在"}
        self.scheduler.trigger_check()
        self._refresh_ui()
        return {"ok": True, "task": self._decorate(task), "stats": self.store.stats()}

    def set_status(self, task_id, status):
        task = self.store.set_status(task_id, status)
        if task is None:
            return {"ok": False, "error": "任务不存在"}
        self._refresh_ui()
        return {"ok": True, "task": self._decorate(task), "stats": self.store.stats()}

    def toggle_complete(self, task_id):
        task = self.store.get_task(task_id)
        if task is None:
            return {"ok": False, "error": "任务不存在"}
        if task.get("status") == storage.STATUS_COMPLETED:
            target = storage.STATUS_PENDING
            # 撤销完成时依据时间重新推断状态
            start = storage.parse_time(task.get("start_time"))
            end = storage.parse_time(task.get("end_time"))
            now = datetime.now()
            if start is not None and now >= start:
                target = storage.STATUS_EXPIRED if (end is not None and now > end) else storage.STATUS_IN_PROGRESS
        else:
            target = storage.STATUS_COMPLETED
        result = self.set_status(task_id, target)
        if result.get("ok"):
            self.notifier.play_sound("info")
        return result

    def delete_task(self, task_id):
        ok = self.store.delete_task(task_id)
        self._refresh_ui()
        return {"ok": ok, "stats": self.store.stats()}

    def clear_completed(self):
        removed = self.store.clear_completed()
        self._refresh_ui()
        return {"ok": True, "removed": removed, "stats": self.store.stats()}

    def snooze_task(self, task_id, minutes):
        task = self.store.snooze_task(task_id, minutes)
        if task is None:
            return {"ok": False, "error": "任务不存在"}
        self._refresh_ui()
        return {"ok": True, "task": self._decorate(task)}

    def update_settings(self, patch):
        settings = self.store.update_settings(patch)
        if "sound_enabled" in patch:
            self.notifier.set_sound_enabled(settings.get("sound_enabled", True))
        self._refresh_ui()
        return {"ok": True, "settings": settings}

    # ------------------------------------------------------------------
    # 状态装饰：补充派生的展示字段
    # ------------------------------------------------------------------

    def _decorate_tasks(self, tasks):
        return [self._decorate(t) for t in tasks]

    def _decorate(self, task):
        item = dict(task)
        now = datetime.now()
        start = storage.parse_time(item.get("start_time"))
        end = storage.parse_time(item.get("end_time"))

        remaining = None
        if end is not None and item.get("status") != storage.STATUS_COMPLETED:
            remaining = (end - now).total_seconds()

        item["remaining_seconds"] = remaining
        item["remaining_text"] = format_remaining(remaining) if remaining is not None else ""
        item["overdue"] = bool(remaining is not None and remaining < 0)
        item["progress"] = self._compute_progress(now, start, end, item.get("status"))
        return item

    def _compute_progress(self, now, start, end, status):
        """计算区间进度百分比，用于列表中的进度条展示。"""
        if status == storage.STATUS_COMPLETED:
            return 100
        if start is None or end is None:
            return 0
        total = (end - start).total_seconds()
        if total <= 0:
            return 100
        passed = (now - start).total_seconds()
        ratio = passed / total * 100.0
        if ratio < 0:
            return 0
        if ratio > 100:
            return 100
        return int(ratio)

    # ------------------------------------------------------------------
    # 系统主题
    # ------------------------------------------------------------------

    def system_theme(self):
        """读取 Windows 系统深浅色设置，返回 "dark" 或 "light"。"""
        if not sys.platform.startswith("win"):
            return "light"
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            handle = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
            try:
                value, _ = winreg.QueryValueEx(handle, "AppsUseLightTheme")
            finally:
                winreg.CloseKey(handle)
            return "light" if int(value) != 0 else "dark"
        except Exception:
            return "light"

    # ------------------------------------------------------------------
    # 回调
    # ------------------------------------------------------------------

    def _on_state_change(self, reason):
        """调度线程触发状态变化后，通知前端刷新。"""
        self._refresh_ui()
        if reason in ("status", "reminder"):
            self.tray.refresh_menu()

    def _on_system_wake(self):
        """系统休眠唤醒后的补偿动作。"""
        self._refresh_ui()
        self.tray.refresh_menu()

    def _refresh_ui(self):
        window = self.window
        if window is None:
            return
        try:
            window.evaluate_js("window.HCNoteRefresh && window.HCNoteRefresh();")
        except Exception:
            pass

    def _due_summary(self):
        return self.scheduler.next_due_summary(limit=6)

    def _tray_quick_done(self, task_id):
        if not task_id:
            return
        self.set_status(task_id, storage.STATUS_COMPLETED)
        self.tray.refresh_menu()

    def _handle_notification_action(self, action, task_id):
        """处理 Toast 按钮点击。"""
        if action == "mark_done":
            self.toggle_complete(task_id)
        elif action == "snooze_10":
            self.snooze_task(task_id, 10)
        elif action == "open":
            self.show_window()


# ----------------------------------------------------------------------
# 启动流程
# ----------------------------------------------------------------------

def single_instance_guard():
    """基于命名互斥体防止重复启动，返回 (handle, already_running)。"""
    if not sys.platform.startswith("win"):
        return None, False
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, "HC-Note-SingleInstance")
        already = ctypes.windll.kernel32.GetLastError() == 183
        return handle, already
    except Exception:
        return None, False


def main():
    enable_dpi_awareness()

    handle, already = single_instance_guard()
    if already:
        return 1

    if not os.path.isfile(UI_INDEX):
        sys.stderr.write("找不到界面文件: %s\n" % UI_INDEX)
        return 2

    import webview

    controller = Controller()
    api = Api(controller)

    url = _path_to_uri(UI_INDEX)
    window = webview.create_window(
        "HC-Note 待办事项",
        url=url,
        js_api=api,
        width=1180,
        height=780,
        min_size=(900, 600),
        background_color="#1E1E22",
    )
    controller.window = window

    # 关闭窗口时最小化到托盘而非退出
    def _on_closing():
        settings = controller.store.get_settings()
        if settings.get("minimize_to_tray", True):
            controller.hide_window()
            controller.tray.notify("HC-Note 已最小化到托盘，定时提醒仍在后台运行。")
            return False
        return True

    window.events.closing += _on_closing

    def _on_loaded():
        controller.start_services()

    window.events.loaded += _on_loaded

    try:
        webview.start(debug=False, private_mode=False)
    except TypeError:
        # 兼容不支持 private_mode 参数的旧版本
        webview.start(debug=False)
    finally:
        controller.quit()

    return 0


def _path_to_uri(path):
    """把本地路径转换为 file:// URI，注意 Windows 反斜杠与中文路径。"""
    normalized = os.path.abspath(path).replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return "file://" + quote(normalized, safe="/:")


if __name__ == "__main__":
    sys.exit(main())
