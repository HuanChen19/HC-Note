# -*- coding: utf-8 -*-
"""HC-Note 自测脚本。

覆盖：数据层原子写入、任务增删改、时间区间校验、提醒节点触发、状态同步。
幂等设计：只覆盖写入，不做任何删除操作，可反复执行。
"""

import os
import shutil
import sys
import tempfile
import traceback

from datetime import datetime, timedelta


ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src", "backend"))

import storage  # noqa: E402
from storage import Store, StorageError  # noqa: E402


PASS = []
FAIL = []


def check(name, condition, detail=None):
    if condition:
        PASS.append(name)
    else:
        FAIL.append("%s%s" % (name, (" -> " + str(detail)) if detail else ""))


def fmt(dt):
    return dt.strftime(storage.TIME_FORMAT)


def test_store(sandbox):
    store = Store(sandbox)

    # --- 初始状态 ---
    check("初始任务列表为空", store.list_tasks() == [], store.list_tasks())
    check("初始设置含默认主题", store.get_settings().get("theme") == "system")

    # --- 创建任务 ---
    task = store.create_task({
        "title": "完成 Addon 模型材质烘焙",
        "description": "修复几何体重叠面的 UV 贴图拉伸",
        "priority": "high",
        "group": "开发",
    })
    check("创建任务返回 id", bool(task.get("id")))
    check("任务 id 形如 task_YYYYMMDD_NNN",
          task["id"].startswith("task_") and len(task["id"]) >= 16, task["id"])
    check("任务初始状态为 pending", task["status"] == "pending", task["status"])
    check("任务初始提醒标记全为 False",
          task["reminders_sent"] == {"start": False, "pre_end": False, "end": False})

    # --- 空标题被拒绝 ---
    try:
        store.create_task({"title": "   "})
        check("空标题应抛出 StorageError", False, "未抛出异常")
    except StorageError:
        check("空标题应抛出 StorageError", True)

    # --- 时间区间校验 ---
    try:
        store.create_task({
            "title": "非法区间",
            "start_time": "2026-09-20 18:00",
            "end_time": "2026-09-20 09:00",
        })
        check("结束早于开始应被拒绝", False, "未抛出异常")
    except StorageError:
        check("结束早于开始应被拒绝", True)

    # --- 原子写入：文件确实落地 ---
    tasks_path = os.path.join(sandbox, "tasks.json")
    check("tasks.json 已生成", os.path.isfile(tasks_path))
    check("备份文件已生成", os.path.isfile(os.path.join(sandbox, "tasks.backup.json")))

    # --- 重新载入验证持久化 ---
    store2 = Store(sandbox)
    reloaded = store2.get_task(task["id"])
    check("重新载入后任务存在", reloaded is not None)
    check("重新载入后标题一致",
          reloaded and reloaded["title"] == "完成 Addon 模型材质烘焙")
    check("重新载入后分组一致", reloaded and reloaded["group"] == "开发")

    # --- 更新任务 ---
    updated = store.update_task(task["id"], {"title": "改后的标题", "priority": "urgent"})
    check("更新标题成功", updated["title"] == "改后的标题")
    check("更新优先级成功", updated["priority"] == "urgent")

    # --- 改写时间应重置提醒标记 ---
    store.mark_reminder_sent(task["id"], "start")
    after = store.get_task(task["id"])
    check("标记提醒后 start=True", after["reminders_sent"]["start"] is True)
    store.update_task(task["id"], {"end_time": "2026-09-25 12:00"})
    after = store.get_task(task["id"])
    check("时间变更后提醒标记被重置",
          after["reminders_sent"]["start"] is False, after["reminders_sent"])

    # --- 状态切换与撤销 ---
    store.set_status(task["id"], storage.STATUS_COMPLETED)
    done = store.get_task(task["id"])
    check("设为完成状态生效", done["status"] == "completed")
    check("完成时间已记录", bool(done["completed_at"]))
    store.set_status(task["id"], storage.STATUS_PENDING)
    back = store.get_task(task["id"])
    check("撤销完成后状态回到 pending", back["status"] == "pending")
    check("撤销完成后 completed_at 清空", back["completed_at"] is None)

    # --- 统计 ---
    stats = store.stats()
    check("统计总数正确", stats["total"] == 1, stats)

    # --- 删除 ---
    check("删除任务返回 True", store.delete_task(task["id"]) is True)
    check("删除后任务不存在", store.get_task(task["id"]) is None)
    check("删除不存在的任务返回 False", store.delete_task("task_not_exist") is False)

    # --- 清空已完成 ---
    a = store.create_task({"title": "已完成项 A"})
    b = store.create_task({"title": "未完成项 B"})
    store.set_status(a["id"], storage.STATUS_COMPLETED)
    removed = store.clear_completed()
    check("清空已完成返回数量 1", removed == 1, removed)
    check("未完成项仍保留", store.get_task(b["id"]) is not None)

    return store


def test_reminders(store):
    """验证提醒节点触发逻辑。"""
    now = datetime.now()

    # 场景一：开始时间已过、结束时间未到 -> 应触发 start
    t1 = store.create_task({
        "title": "进行中的任务",
        "start_time": fmt(now - timedelta(minutes=5)),
        "end_time": fmt(now + timedelta(hours=3)),
    })
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t1["id"]]
    check("已过开始时间触发 start 提醒", "start" in kinds, kinds)

    # 标记后不应重复触发
    store.mark_reminder_sent(t1["id"], "start")
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t1["id"]]
    check("已标记的 start 提醒不再重复", "start" not in kinds, kinds)

    # 场景二：结束前 15 分钟窗口 -> 触发 pre_end
    # 先标记 start 已发送，以便独立验证 pre_end 节点（否则 start 更早到期会被优先）
    t2 = store.create_task({
        "title": "即将到期",
        "start_time": fmt(now - timedelta(hours=2)),
        "end_time": fmt(now + timedelta(minutes=8)),
    })
    store.mark_reminder_sent(t2["id"], "start")
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t2["id"]]
    check("结束前窗口内触发 pre_end", "pre_end" in kinds, kinds)

    # 场景三：已超过结束时间 -> 触发 end
    t3 = store.create_task({
        "title": "已超时任务",
        "start_time": fmt(now - timedelta(hours=3)),
        "end_time": fmt(now - timedelta(minutes=10)),
    })
    store.mark_reminder_sent(t3["id"], "start")
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t3["id"]]
    check("超过结束时间触发 end", "end" in kinds, kinds)

    # 场景三之二：三个节点同时到期时，每轮只推最紧迫的一个
    t3b = store.create_task({
        "title": "全部节点同时到期",
        "start_time": fmt(now - timedelta(hours=3)),
        "end_time": fmt(now - timedelta(minutes=10)),
    })
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t3b["id"]]
    check("多节点同时到期只推最紧迫的 end", kinds == ["end"], kinds)

    # 场景四：已完成任务不触发任何提醒
    store.set_status(t3["id"], storage.STATUS_COMPLETED)
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t3["id"]]
    check("已完成任务不触发提醒", len(kinds) == 0, kinds)

    # 场景五：notify_before_minutes 为 0 时不做结束前预警
    t4 = store.create_task({
        "title": "无预警窗口",
        "start_time": fmt(now - timedelta(hours=1)),
        "end_time": fmt(now + timedelta(minutes=8)),
    })
    store.mark_reminder_sent(t4["id"], "start")
    due = store.collect_due_reminders(0)
    kinds = [d[1] for d in due if d[0]["id"] == t4["id"]]
    check("预警分钟为 0 时不触发 pre_end", "pre_end" not in kinds, kinds)

    # 场景六：推迟后不再触发
    t5 = store.create_task({
        "title": "被推迟的任务",
        "start_time": fmt(now - timedelta(minutes=3)),
        "end_time": fmt(now + timedelta(hours=1)),
    })
    store.snooze_task(t5["id"], 30)
    due = store.collect_due_reminders(15)
    kinds = [d[1] for d in due if d[0]["id"] == t5["id"]]
    check("推迟中的任务不触发提醒", len(kinds) == 0, kinds)


def test_status_sync(store):
    """验证依时间校准任务状态。"""
    now = datetime.now()

    t_run = store.create_task({
        "title": "应变为进行中",
        "start_time": fmt(now - timedelta(minutes=30)),
        "end_time": fmt(now + timedelta(hours=2)),
    })
    t_exp = store.create_task({
        "title": "应变为已超时",
        "start_time": fmt(now - timedelta(hours=3)),
        "end_time": fmt(now - timedelta(hours=1)),
    })
    t_future = store.create_task({
        "title": "应保持未开始",
        "start_time": fmt(now + timedelta(hours=1)),
        "end_time": fmt(now + timedelta(hours=3)),
    })

    changed = store.sync_status_by_time()
    changed_ids = set([c["id"] for c in changed])

    check("进行中任务被校准", t_run["id"] in changed_ids, changed_ids)
    check("超时任务被校准", t_exp["id"] in changed_ids, changed_ids)
    check("未来任务未被改动", t_future["id"] not in changed_ids, changed_ids)

    check("进行中任务状态正确",
          store.get_task(t_run["id"])["status"] == "in_progress")
    check("超时任务状态正确",
          store.get_task(t_exp["id"])["status"] == "expired")
    check("未来任务状态仍为 pending",
          store.get_task(t_future["id"])["status"] == "pending")

    # 已完成任务不应被状态校准覆盖
    store.set_status(t_run["id"], storage.STATUS_COMPLETED)
    store.sync_status_by_time()
    check("已完成任务不被状态校准覆盖",
          store.get_task(t_run["id"])["status"] == "completed")


def test_corrupted_file(sandbox):
    """验证损坏数据文件的容错能力。"""
    bad_dir = os.path.join(sandbox, "bad")
    if not os.path.isdir(bad_dir):
        os.makedirs(bad_dir)
    bad_path = os.path.join(bad_dir, "tasks.json")
    with open(bad_path, "w", encoding="utf-8") as fh:
        fh.write("{ this is not valid json ]]")
    store = Store(bad_dir)
    check("损坏文件时降级为空数据", store.list_tasks() == [])
    check("损坏文件时仍有默认设置",
          store.get_settings().get("theme") == "system")


def test_scheduler_module():
    """验证调度器与通知模块可正常导入并构造。"""
    try:
        import notifier
        import scheduler

        n = notifier.Notifier(sound_enabled=False)
        check("Notifier 可构造", n is not None)
        check("Notifier 具备 Toast 探测结果", isinstance(n.is_toast_available(), bool))

        s = scheduler.Scheduler(None, n)
        check("Scheduler 可构造", s is not None)
        check("剩余时间格式化 - 分钟",
              scheduler.format_remaining(120) == "2 分钟",
              scheduler.format_remaining(120))
        check("剩余时间格式化 - 小时分钟",
              scheduler.format_remaining(3660) == "1 小时 1 分",
              scheduler.format_remaining(3660))
        check("剩余时间格式化 - 天",
              scheduler.format_remaining(90000) == "1 天 1 小时",
              scheduler.format_remaining(90000))
        check("负数剩余时间归零",
              scheduler.format_remaining(-50) == "0 分钟")
    except Exception:
        check("调度与通知模块导入", False, traceback.format_exc())


def main():
    # 每次运行使用独立沙箱目录，避免历史残留数据影响断言。
    # 目录名带时间戳与进程号，天然唯一，可反复执行且互不干扰。
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sandbox = os.path.join(ROOT, ".build", "selftest", "%s_%d" % (stamp, os.getpid()))
    if not os.path.isdir(sandbox):
        os.makedirs(sandbox)

    try:
        store = test_store(sandbox)
        test_reminders(store)
        test_status_sync(store)
        test_corrupted_file(sandbox)
        test_scheduler_module()
    except Exception:
        FAIL.append("未捕获异常:\n" + traceback.format_exc())

    lines = []
    lines.append("=" * 56)
    lines.append("HC-Note 自测报告")
    lines.append("=" * 56)
    lines.append("通过: %d    失败: %d" % (len(PASS), len(FAIL)))
    lines.append("")
    if FAIL:
        lines.append("--- 失败项 ---")
        for item in FAIL:
            lines.append("  [X] " + item)
        lines.append("")
    lines.append("--- 通过项 ---")
    for item in PASS:
        lines.append("  [v] " + item)

    report = "\n".join(lines)
    print(report)

    report_path = os.path.join(ROOT, ".build", "selftest_report.txt")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report)

    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
