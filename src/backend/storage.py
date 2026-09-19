# -*- coding: utf-8 -*-
"""HC-Note 数据持久化层。

采用本地 JSON 文件存储，所有写入均走「先写临时文件再原子替换」流程，
避免断电或异常退出导致数据文件损坏。
"""

import json
import os
import shutil
import tempfile
import threading
import time

from datetime import datetime, timedelta


SCHEMA_VERSION = "1.0"

PRIORITIES = ("low", "medium", "high", "urgent")

STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_EXPIRED = "expired"

STATUSES = (STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_EXPIRED)

TIME_FORMAT = "%Y-%m-%d %H:%M"

DEFAULT_SETTINGS = {
    "theme": "system",
    "sound_enabled": True,
    "notify_before_minutes": 15,
    "minimize_to_tray": True,
    "launch_at_startup": False,
}

PRIORITY_ORDER = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def now_string():
    """返回当前时间的标准格式字符串。"""
    return datetime.now().strftime(TIME_FORMAT)


def parse_time(value):
    """把 "YYYY-MM-DD HH:mm" 字符串解析为 datetime，失败返回 None。"""
    if not value:
        return None
    try:
        return datetime.strptime(value, TIME_FORMAT)
    except (ValueError, TypeError):
        return None


def format_time(dt):
    """把 datetime 格式化为存储字符串。"""
    if dt is None:
        return None
    return dt.strftime(TIME_FORMAT)


class StorageError(Exception):
    """存储层异常。"""

    pass


class Store(object):
    """任务与设置的数据仓库。

    所有公开方法均加锁，保证调度线程与界面线程并发访问安全。
    """

    def __init__(self, data_dir):
        self._lock = threading.RLock()
        self._data_dir = data_dir
        self._tasks_path = os.path.join(data_dir, "tasks.json")
        self._backup_path = os.path.join(data_dir, "tasks.backup.json")
        self._tasks = []
        self._settings = dict(DEFAULT_SETTINGS)
        self._ensure_dir()
        self.load()

    # ------------------------------------------------------------------
    # 路径与初始化
    # ------------------------------------------------------------------

    def _ensure_dir(self):
        if not os.path.isdir(self._data_dir):
            os.makedirs(self._data_dir)

    def get_data_dir(self):
        return self._data_dir

    # ------------------------------------------------------------------
    # 读写
    # ------------------------------------------------------------------

    def load(self):
        """从磁盘载入数据，文件缺失或损坏时回退到备份或空数据。"""
        with self._lock:
            payload = self._read_json(self._tasks_path)
            if payload is None:
                payload = self._read_json(self._backup_path)
                if payload is not None:
                    self._tasks, self._settings = self._normalize(payload)
                    self.save(reason="recovered-from-backup")
                    return
                self._tasks = []
                self._settings = dict(DEFAULT_SETTINGS)
                return
            self._tasks, self._settings = self._normalize(payload)

    def _read_json(self, path):
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, IOError, OSError):
            return None

    def _normalize(self, payload):
        """把任意来源的数据规整成合法结构，容错处理缺失字段。"""
        if not isinstance(payload, dict):
            payload = {}
        raw_tasks = payload.get("tasks")
        if not isinstance(raw_tasks, list):
            raw_tasks = []

        tasks = []
        for item in raw_tasks:
            task = self._normalize_task(item)
            if task is not None:
                tasks.append(task)

        raw_settings = payload.get("settings")
        settings = dict(DEFAULT_SETTINGS)
        if isinstance(raw_settings, dict):
            for key in DEFAULT_SETTINGS:
                if key in raw_settings:
                    settings[key] = raw_settings[key]

        return tasks, settings

    def _normalize_task(self, item):
        if not isinstance(item, dict):
            return None
        task_id = item.get("id")
        if not task_id:
            return None

        priority = item.get("priority")
        if priority not in PRIORITIES:
            priority = "medium"

        status = item.get("status")
        if status not in STATUSES:
            status = STATUS_PENDING

        reminders = item.get("reminders_sent")
        if not isinstance(reminders, dict):
            reminders = {}
        reminders_sent = {
            "start": bool(reminders.get("start", False)),
            "pre_end": bool(reminders.get("pre_end", False)),
            "end": bool(reminders.get("end", False)),
        }

        tags = item.get("tags")
        if not isinstance(tags, list):
            tags = []

        return {
            "id": str(task_id),
            "title": str(item.get("title") or ""),
            "description": str(item.get("description") or ""),
            "priority": priority,
            "status": status,
            "group": str(item.get("group") or "默认"),
            "tags": [str(t) for t in tags],
            "start_time": item.get("start_time") or None,
            "end_time": item.get("end_time") or None,
            "created_at": item.get("created_at") or now_string(),
            "updated_at": item.get("updated_at") or now_string(),
            "completed_at": item.get("completed_at") or None,
            "reminders_sent": reminders_sent,
            "snooze_until": item.get("snooze_until") or None,
        }

    def save(self, reason=None):
        """原子写入数据文件，并滚动保留一份备份。"""
        with self._lock:
            payload = {
                "version": SCHEMA_VERSION,
                "saved_at": now_string(),
                "settings": dict(self._settings),
                "tasks": list(self._tasks),
            }
            self._atomic_write(self._tasks_path, payload)
            if os.path.isfile(self._tasks_path):
                try:
                    shutil.copyfile(self._tasks_path, self._backup_path)
                except (IOError, OSError):
                    pass

    def _atomic_write(self, path, payload):
        """先写同目录临时文件，再 os.replace 原子替换。"""
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory)

        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    # ------------------------------------------------------------------
    # 设置
    # ------------------------------------------------------------------

    def get_settings(self):
        with self._lock:
            return dict(self._settings)

    def update_settings(self, patch):
        """局部更新设置项，返回更新后的完整设置。"""
        with self._lock:
            if not isinstance(patch, dict):
                return dict(self._settings)
            for key in DEFAULT_SETTINGS:
                if key in patch:
                    self._settings[key] = patch[key]
            self.save(reason="settings")
            return dict(self._settings)

    # ------------------------------------------------------------------
    # 任务查询
    # ------------------------------------------------------------------

    def list_tasks(self):
        with self._lock:
            return [dict(t) for t in self._tasks]

    def get_task(self, task_id):
        with self._lock:
            for t in self._tasks:
                if t["id"] == task_id:
                    return dict(t)
            return None

    def _find_index(self, task_id):
        for idx, t in enumerate(self._tasks):
            if t["id"] == task_id:
                return idx
        return -1

    def _next_id(self):
        """生成 task_YYYYMMDD_NNN 形式的唯一标识。"""
        stamp = datetime.now().strftime("%Y%m%d")
        prefix = "task_%s_" % stamp
        used = set()
        for t in self._tasks:
            tid = t.get("id") or ""
            if tid.startswith(prefix):
                try:
                    used.add(int(tid.rsplit("_", 1)[1]))
                except (ValueError, IndexError):
                    continue
        seq = 1
        while seq in used:
            seq += 1
        return "%s%03d" % (prefix, seq)

    # ------------------------------------------------------------------
    # 任务写操作
    # ------------------------------------------------------------------

    def create_task(self, payload):
        """新增任务，返回创建后的任务对象。"""
        with self._lock:
            title = (payload or {}).get("title") or ""
            title = title.strip()
            if not title:
                raise StorageError("任务标题不能为空")

            priority = (payload or {}).get("priority")
            if priority not in PRIORITIES:
                priority = "medium"

            start_time = (payload or {}).get("start_time") or None
            end_time = (payload or {}).get("end_time") or None
            self._validate_range(start_time, end_time)

            task = {
                "id": self._next_id(),
                "title": title,
                "description": (payload or {}).get("description") or "",
                "priority": priority,
                "status": STATUS_PENDING,
                "group": (payload or {}).get("group") or "默认",
                "tags": (payload or {}).get("tags") or [],
                "start_time": start_time,
                "end_time": end_time,
                "created_at": now_string(),
                "updated_at": now_string(),
                "completed_at": None,
                "reminders_sent": {"start": False, "pre_end": False, "end": False},
                "snooze_until": None,
            }
            self._tasks.append(task)
            self.save(reason="create")
            return dict(task)

    def _validate_range(self, start_time, end_time):
        s = parse_time(start_time)
        e = parse_time(end_time)
        if s is not None and e is not None and e < s:
            raise StorageError("结束时间不能早于开始时间")

    def update_task(self, task_id, patch):
        """更新任务字段，返回更新后的任务，未找到返回 None。"""
        with self._lock:
            idx = self._find_index(task_id)
            if idx < 0:
                return None
            task = self._tasks[idx]
            patch = patch or {}

            if "title" in patch:
                title = (patch.get("title") or "").strip()
                if not title:
                    raise StorageError("任务标题不能为空")
                task["title"] = title
            if "description" in patch:
                task["description"] = patch.get("description") or ""
            if "priority" in patch:
                if patch.get("priority") in PRIORITIES:
                    task["priority"] = patch["priority"]
            if "group" in patch:
                task["group"] = patch.get("group") or "默认"
            if "tags" in patch:
                tags = patch.get("tags")
                task["tags"] = [str(t) for t in tags] if isinstance(tags, list) else []

            if "start_time" in patch or "end_time" in patch:
                start_time = patch.get("start_time", task.get("start_time"))
                end_time = patch.get("end_time", task.get("end_time"))
                self._validate_range(start_time, end_time)
                if task.get("start_time") != start_time or task.get("end_time") != end_time:
                    # 时间变动后需要重新触发各节点提醒
                    task["reminders_sent"] = {"start": False, "pre_end": False, "end": False}
                    task["snooze_until"] = None
                task["start_time"] = start_time
                task["end_time"] = end_time

            if "status" in patch:
                self._apply_status(task, patch["status"])

            task["updated_at"] = now_string()
            self.save(reason="update")
            return dict(task)

    def _apply_status(self, task, status):
        if status not in STATUSES:
            return
        task["status"] = status
        if status == STATUS_COMPLETED:
            task["completed_at"] = now_string()
        else:
            task["completed_at"] = None

    def set_status(self, task_id, status):
        """切换任务状态（完成 / 撤销完成等）。"""
        with self._lock:
            idx = self._find_index(task_id)
            if idx < 0:
                return None
            task = self._tasks[idx]
            self._apply_status(task, status)
            task["updated_at"] = now_string()
            self.save(reason="status")
            return dict(task)

    def delete_task(self, task_id):
        """删除任务，返回是否成功。"""
        with self._lock:
            idx = self._find_index(task_id)
            if idx < 0:
                return False
            self._tasks.pop(idx)
            self.save(reason="delete")
            return True

    def clear_completed(self):
        """清空所有已完成任务，返回删除数量。"""
        with self._lock:
            before = len(self._tasks)
            self._tasks = [t for t in self._tasks if t["status"] != STATUS_COMPLETED]
            removed = before - len(self._tasks)
            if removed:
                self.save(reason="clear-completed")
            return removed

    def snooze_task(self, task_id, minutes):
        """把任务的提醒推迟指定分钟数。"""
        with self._lock:
            idx = self._find_index(task_id)
            if idx < 0:
                return None
            task = self._tasks[idx]
            base = datetime.now()
            task["snooze_until"] = format_time((base + timedelta(minutes=minutes)).replace(second=0, microsecond=0))
            # 清理结束类提醒标记，使推迟到期后能再次推送
            reminders = task.get("reminders_sent") or {}
            reminders["end"] = False
            task["reminders_sent"] = reminders
            task["updated_at"] = now_string()
            self.save(reason="snooze")
            return dict(task)

    # ------------------------------------------------------------------
    # 调度支持
    # ------------------------------------------------------------------

    def mark_reminder_sent(self, task_id, kind):
        """标记某个提醒节点已推送，避免重复通知。"""
        with self._lock:
            idx = self._find_index(task_id)
            if idx < 0:
                return False
            task = self._tasks[idx]
            reminders = task.get("reminders_sent") or {}
            reminders[kind] = True
            task["reminders_sent"] = reminders
            self.save(reason="reminder")
            return True

    def sync_status_by_time(self):
        """依据当前时间校准任务状态，返回发生变化的任务列表。

        在电脑休眠唤醒后调用，可立即补偿错过的状态切换。
        """
        with self._lock:
            current = datetime.now()
            changed = []
            for task in self._tasks:
                if task["status"] == STATUS_COMPLETED:
                    continue
                start = parse_time(task.get("start_time"))
                end = parse_time(task.get("end_time"))
                target = None
                if start is not None and current >= start:
                    if end is not None and current > end:
                        target = STATUS_EXPIRED
                    else:
                        target = STATUS_IN_PROGRESS
                if target and target != task["status"]:
                    task["status"] = target
                    task["updated_at"] = now_string()
                    changed.append(dict(task))
            if changed:
                self.save(reason="sync-status")
            return changed

    def collect_due_reminders(self, notify_before_minutes):
        """收集当前应当推送的提醒，返回 (task, kind, moment) 列表。

        kind 取值：start / pre_end / end。
        三个节点独立判定：休眠唤醒后可能出现多个节点同时到期的情况。
        为避免同一任务连环弹窗，每轮只取该任务最紧迫的一个节点，
        其余节点留待下一轮（届时前一个节点已被标记为已发送）。
        """
        with self._lock:
            current = datetime.now()
            due = []
            for task in self._tasks:
                if task["status"] == STATUS_COMPLETED:
                    continue
                reminders = task.get("reminders_sent") or {}

                snooze_until = parse_time(task.get("snooze_until"))
                if snooze_until is not None and current < snooze_until:
                    continue

                start = parse_time(task.get("start_time"))
                end = parse_time(task.get("end_time"))

                candidates = []

                if start is not None and not reminders.get("start") and current >= start:
                    candidates.append(("start", start))

                if end is not None:
                    if notify_before_minutes > 0 and not reminders.get("pre_end"):
                        warn_at = end - timedelta(minutes=notify_before_minutes)
                        if warn_at <= current < end:
                            candidates.append(("pre_end", warn_at))
                    if not reminders.get("end") and current >= end:
                        candidates.append(("end", end))

                if not candidates:
                    continue

                # 越靠后的节点越紧迫：end > pre_end > start
                priority_of = {"start": 0, "pre_end": 1, "end": 2}
                candidates.sort(key=lambda c: priority_of.get(c[0], 9))
                kind, moment = candidates[-1]
                due.append((dict(task), kind, moment))

            return due

    def stats(self):
        """返回任务统计信息，供界面顶部概览使用。"""
        with self._lock:
            total = len(self._tasks)
            done = len([t for t in self._tasks if t["status"] == STATUS_COMPLETED])
            running = len([t for t in self._tasks if t["status"] == STATUS_IN_PROGRESS])
            expired = len([t for t in self._tasks if t["status"] == STATUS_EXPIRED])
            return {
                "total": total,
                "completed": done,
                "in_progress": running,
                "expired": expired,
                "pending": total - done - running - expired,
            }
