# -*- coding: utf-8 -*-
"""系统托盘驻留与后台常驻管理。

基于 pystray 实现托盘图标、右键菜单与最小化到托盘；
pystray 不可用时自动跳过托盘能力，程序仍可正常作为普通窗口运行。
"""

import os
import threading


class TrayManager(object):
    """托盘图标管理器。"""

    def __init__(self, icon_path, on_show=None, on_toggle=None,
                 on_quick_done=None, on_quit=None, summary_provider=None):
        self._icon_path = icon_path
        self._on_show = on_show
        self._on_toggle = on_toggle
        self._on_quick_done = on_quick_done
        self._on_quit = on_quit
        self._summary_provider = summary_provider

        self._icon = None
        self._thread = None
        self._available = False
        self._menu_cache = []
        self._lock = threading.Lock()

        self._probe()

    # ------------------------------------------------------------------
    # 可用性探测
    # ------------------------------------------------------------------

    def _probe(self):
        try:
            import pystray

            self._available = True
        except Exception:
            self._available = False

    def is_available(self):
        return self._available

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        """在独立线程中启动托盘图标。"""
        if not self._available:
            return False
        if self._thread is not None and self._thread.is_alive():
            return True

        self._thread = threading.Thread(target=self._run, name="hc-note-tray")
        self._thread.daemon = True
        self._thread.start()
        return True

    def _run(self):
        try:
            import pystray
            from PIL import Image

            image = self._load_image(Image)
            menu = pystray.Menu(
                pystray.MenuItem("打开 HC-Note", self._handle_show, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("即将到期", self._build_due_menu()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._handle_quit),
            )
            self._icon = pystray.Icon(
                "hc-note",
                icon=image,
                title="HC-Note 待办事项",
                menu=menu,
            )
            self._icon.run()
        except Exception:
            self._available = False

    def _load_image(self, image_module):
        """载入托盘图标，失败时生成一个纯色占位图标。"""
        if self._icon_path and os.path.isfile(self._icon_path):
            try:
                return image_module.open(self._icon_path).convert("RGBA")
            except Exception:
                pass
        # 占位图标：草方块绿，避免托盘完全不可见
        return image_module.new("RGBA", (64, 64), (91, 158, 62, 255))

    def stop(self):
        icon = self._icon
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
            self._icon = None

    # ------------------------------------------------------------------
    # 菜单构建
    # ------------------------------------------------------------------

    def _build_due_menu(self):
        """构建「即将到期」子菜单，pystray 支持可调用菜单项时动态展开。"""
        try:
            import pystray

            return pystray.Menu(lambda: self._collect_due_items(pystray))
        except Exception:
            return None

    def _collect_due_items(self, pystray_module):
        """收集即将到期的任务，生成菜单项列表。"""
        provider = self._summary_provider
        if provider is None:
            return []
        try:
            items = provider()
        except Exception:
            return []

        entries = []
        for end_time, task in items:
            label = "%s  (%s)" % (task.get("title") or "未命名", end_time.strftime("%m-%d %H:%M"))
            task_id = task.get("id")
            entries.append(
                pystray_module.MenuItem(
                    label,
                    self._make_done_handler(task_id),
                )
            )
        if not entries:
            entries.append(pystray_module.MenuItem("暂无即将到期任务", None, enabled=False))
        return entries

    def _make_done_handler(self, task_id):
        def _handler(icon=None, item=None):
            handler = self._on_quick_done
            if handler is None:
                return
            try:
                handler(task_id)
            except Exception:
                pass

        return _handler

    def refresh_menu(self):
        """请求托盘菜单重绘，使「即将到期」内容保持最新。"""
        icon = self._icon
        if icon is None:
            return
        try:
            icon.update_menu()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 气泡提示（供 Notifier 降级使用）
    # ------------------------------------------------------------------

    def notify(self, message, title=None):
        icon = self._icon
        if icon is None:
            raise RuntimeError("托盘图标未启动")
        icon.notify(message, title or "HC-Note")

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _handle_show(self, icon=None, item=None):
        if self._on_show is not None:
            try:
                self._on_show()
            except Exception:
                pass

    def _handle_toggle(self, icon=None, item=None):
        if self._on_toggle is not None:
            try:
                self._on_toggle()
            except Exception:
                pass

    def _handle_quit(self, icon=None, item=None):
        if self._on_quit is not None:
            try:
                self._on_quit()
            except Exception:
                pass
        else:
            self.stop()
