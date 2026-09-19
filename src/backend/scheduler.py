# -*- coding: utf-8 -*-
"""后台高精度定时轮询器。

以短间隔守护线程轮询任务时间节点，负责：
1. 依据当前时间校准任务状态（pending -> in_progress -> expired）；
2. 在开始 / 结束前 / 结束节点推送提醒，且同一节点只推送一次；
3. 检测系统休眠唤醒造成的时间跳变，唤醒后立即补偿推送错过的提醒。
"""

import threading
import time

from datetime import datetime

import storage


TICK_SECONDS = 20           # 轮询间隔，保证分钟级精度
SLEEP_JUMP_SECONDS = 120    # 单次 tick 实际耗时超过该值即判定发生休眠


class Scheduler(object):
    """任务时间节点调度器。"""

    def __init__(self, store, notifier, on_change=None, on_wake=None):
        self._store = store
        self._notifier = notifier
        self._on_change = on_change
        self._on_wake = on_wake
        self._thread = None
        self._stop_event = threading.Event()
        self._last_tick = None
        self._lock = threading.Lock()
        self._manual_check = threading.Event()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="hc-note-scheduler")
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)

    def trigger_check(self):
        """立即触发一次检查，用于界面操作后即时刷新。"""
        self._manual_check.set()

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def _run(self):
        self._last_tick = time.time()
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                # 单次异常不应终止调度线程
                pass

            self._manual_check.wait(timeout=TICK_SECONDS)
            self._manual_check.clear()

    def _tick(self):
        now = time.time()
        elapsed = now - self._last_tick
        slept = elapsed > SLEEP_JUMP_SECONDS

        self._last_tick = now

        if slept:
            # 休眠唤醒补偿：先校准状态，再立即收集所有逾期提醒
            self._handle_wake()

        changed = self._store.sync_status_by_time()
        self._dispatch_reminders()

        if changed and self._on_change is not None:
            try:
                self._on_change("status")
            except Exception:
                pass

    def _handle_wake(self):
        """处理休眠唤醒后的时间跳变。"""
        try:
            self._store.sync_status_by_time()
        except Exception:
            pass
        if self._on_wake is not None:
            try:
                self._on_wake()
            except Exception:
                pass

    def _dispatch_reminders(self):
        """收集并推送到期的提醒。"""
        settings = self._store.get_settings()
        before = settings.get("notify_before_minutes", 15)
        try:
            before = int(before)
        except (TypeError, ValueError):
            before = 15

        due = self._store.collect_due_reminders(before)
        if not due:
            return

        # 同一轮内按时间先后排序，先到期的先推送
        due.sort(key=lambda item: item[2] or datetime.now())

        for task, kind, _moment in due:
            task_id = task.get("id")
            if not task_id:
                continue
            # 先标记后推送，避免推送过程中异常导致重复提醒
            self._store.mark_reminder_sent(task_id, kind)
            self._notifier.notify(kind, task)

        if self._on_change is not None:
            try:
                self._on_change("reminder")
            except Exception:
                pass

    def next_due_summary(self, limit=5):
        """汇总即将到期任务，供托盘菜单展示。"""
        tasks = self._store.list_tasks()
        pending = []
        current = datetime.now()
        for task in tasks:
            if task.get("status") == storage.STATUS_COMPLETED:
                continue
            end = storage.parse_time(task.get("end_time"))
            if end is None:
                continue
            if end < current:
                continue
            pending.append((end, task))
        pending.sort(key=lambda item: item[0])
        return pending[:limit]


def format_remaining(delta_seconds):
    """把剩余秒数格式化为易读文本。"""
    if delta_seconds is None:
        return ""
    if delta_seconds < 0:
        delta_seconds = 0
    total_minutes = int(delta_seconds // 60)
    days, rest = divmod(total_minutes, 1440)
    hours, minutes = divmod(rest, 60)
    if days > 0:
        return "%d 天 %d 小时" % (days, hours)
    if hours > 0:
        return "%d 小时 %d 分" % (hours, minutes)
    return "%d 分钟" % minutes
