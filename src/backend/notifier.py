# -*- coding: utf-8 -*-
"""Windows 原生 Toast 通知与提示音。

优先使用 windows-toasts 库推送带操作按钮的 Toast；若该库不可用或调用失败，
自动降级为 pystray 气泡提示，最终降级为控制台输出，保证提醒能力不丢失。
"""

import os
import sys
import threading


SOUND_ALIASES = {
    "start": "SystemAsterisk",
    "pre_end": "SystemExclamation",
    "end": "SystemHand",
    "info": "SystemAsterisk",
}


def _is_windows():
    return sys.platform.startswith("win")


class Notifier(object):
    """通知分发器。

    通过 set_action_handler 注册回调后，Toast 上的按钮点击会回传到业务层。
    """

    APP_ID = "幻尘.HC-Note"

    def __init__(self, sound_enabled=True):
        self._sound_enabled = bool(sound_enabled)
        self._action_handler = None
        self._toast_available = False
        self._tray_icon = None
        self._toast_module = None
        self._lock = threading.Lock()
        self._probe_toast()

    # ------------------------------------------------------------------
    # 初始化与降级探测
    # ------------------------------------------------------------------

    def _probe_toast(self):
        if not _is_windows():
            return
        try:
            import windows_toasts

            self._toast_module = windows_toasts
            self._toast_available = True
        except Exception:
            self._toast_available = False

    def set_tray_icon(self, icon):
        """注入托盘图标，用于 Toast 不可用时的气泡降级通道。"""
        self._tray_icon = icon

    def set_action_handler(self, handler):
        """注册动作回调，handler(action, task_id) -> None。"""
        self._action_handler = handler

    def set_sound_enabled(self, enabled):
        with self._lock:
            self._sound_enabled = bool(enabled)

    def is_toast_available(self):
        return self._toast_available

    # ------------------------------------------------------------------
    # 声音
    # ------------------------------------------------------------------

    def play_sound(self, kind="info"):
        """播放系统提示音。"""
        with self._lock:
            enabled = self._sound_enabled
        if not enabled:
            return
        if not _is_windows():
            return
        try:
            import winsound

            alias = SOUND_ALIASES.get(kind, "SystemAsterisk")
            winsound.PlaySound(alias, winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Toast 推送
    # ------------------------------------------------------------------

    def _build_text(self, kind, task):
        """根据提醒类型生成标题与正文。"""
        title = task.get("title") or "未命名任务"
        if kind == "start":
            head = "任务开始"
            body = title
        elif kind == "pre_end":
            head = "即将到期"
            body = "%s（即将到达结束时间）" % title
        elif kind == "end":
            head = "任务已超时"
            body = "%s（已超过结束时间）" % title
        else:
            head = "HC-Note"
            body = title
        return head, body

    def notify(self, kind, task):
        """推送一条任务提醒。返回是否成功送达。"""
        head, body = self._build_text(kind, task)
        task_id = task.get("id")

        sent = False
        if self._toast_available:
            sent = self._send_toast(head, body, task_id)
        if not sent:
            sent = self._send_balloon(head, body)
        if not sent:
            try:
                sys.stdout.write("[HC-Note] %s - %s\n" % (head, body))
            except Exception:
                pass

        self.play_sound(kind)
        return sent

    def _send_toast(self, head, body, task_id):
        try:
            toaster = self._toast_module.Toaster()
            if hasattr(self._toast_module, "ToastTextToAddTo"):
                toast = self._toast_module.ToastTextToAddTo()
                toast.text_fields = [head, body]
            else:
                toast = self._toast_module.Toast([head, body])

            buttons = self._build_buttons(task_id)
            if buttons:
                toast.AddAction(buttons)

            toaster.show_toast(toast)
            return True
        except Exception:
            return False

    def _build_buttons(self, task_id):
        """构造 Toast 上的操作按钮。"""
        if self._action_handler is None or not task_id:
            return None
        try:
            module = self._toast_module
            specs = (
                ("mark_done", "标记完成"),
                ("snooze_10", "推迟 10 分钟"),
                ("open", "查看"),
            )
            actions = []
            for action, label in specs:
                if action == "open":
                    btn = module.ToastButton(label, launch="")
                else:
                    btn = module.ToastButton(label)
                # 绑定回调，闭包捕获 action 与 task_id
                btn.on_activated = self._make_callback(action, task_id)
                actions.append(btn)
            return actions
        except Exception:
            return None

    def _make_callback(self, action, task_id):
        def _callback(*_args, **_kwargs):
            handler = self._action_handler
            if handler is None:
                return
            try:
                handler(action, task_id)
            except Exception:
                pass

        return _callback

    def _send_balloon(self, head, body):
        """降级通道：使用托盘气泡提示。"""
        icon = self._tray_icon
        if icon is None:
            return False
        try:
            icon.notify(body, head)
            return True
        except Exception:
            return False
