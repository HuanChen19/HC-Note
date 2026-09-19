# -*- coding: utf-8 -*-
"""HC-Note 启动链路校验。

不创建真实窗口（沙箱/CI 环境无法弹窗），仅校验：
1. 路径解析是否正确（resource_root / data_root / UI_INDEX）；
2. index.html 引用的静态资源是否全部存在；
3. 后端 Api 类是否暴露了全部前端需要的接口；
4. 前端 callApi() 调用的方法名是否都能在后端找到（前后端接口对齐）；
5. 任务装饰字段是否完整。

适合在改动后端或前端接口后快速回归。
"""

import os
import re
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "src", "backend")
sys.path.insert(0, BACKEND)

PASS = []
FAIL = []


def check(name, cond, detail=None):
    if cond:
        PASS.append(name)
    else:
        FAIL.append("%s%s" % (name, (" -> " + str(detail)) if detail else ""))


def main():
    import app as hc_app

    # --- 路径解析 ---
    check("resource_root 指向项目根",
          os.path.normcase(hc_app.resource_root()) == os.path.normcase(ROOT),
          hc_app.resource_root())
    check("data_root 位于项目根下 data 目录",
          os.path.normcase(hc_app.data_root()) ==
          os.path.normcase(os.path.join(ROOT, "data")),
          hc_app.data_root())
    check("UI_INDEX 路径正确",
          os.path.normcase(hc_app.UI_INDEX) ==
          os.path.normcase(os.path.join(ROOT, "src", "ui", "index.html")),
          hc_app.UI_INDEX)
    check("界面文件真实存在", os.path.isfile(hc_app.UI_INDEX))
    check("应用图标真实存在", os.path.isfile(hc_app.ICON_ICO))
    check("托盘图标真实存在", os.path.isfile(hc_app.ICON_TRAY))

    # --- 前端资源引用完整性 ---
    with open(hc_app.UI_INDEX, "r", encoding="utf-8") as fh:
        html = fh.read()

    ui_dir = os.path.dirname(hc_app.UI_INDEX)
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    missing = []
    checked = 0
    for ref in refs:
        if ref.startswith(("http://", "https://", "#", "data:")):
            continue
        target = os.path.normpath(os.path.join(ui_dir, ref))
        if not os.path.isfile(target):
            missing.append(ref)
        else:
            checked += 1
    check("index.html 引用的资源全部存在（%d 个）" % checked, not missing, missing)

    # --- 前端文件有效性 ---
    for rel in [
        os.path.join("css", "themes.css"),
        os.path.join("css", "ore_ui.css"),
        os.path.join("css", "layout.css"),
        os.path.join("js", "theme.js"),
        os.path.join("js", "timepicker.js"),
        os.path.join("js", "app.js"),
    ]:
        p = os.path.join(ui_dir, rel)
        ok = os.path.isfile(p) and os.path.getsize(p) > 200
        check("前端文件有效: %s" % rel, ok,
              "size=%s" % (os.path.getsize(p) if os.path.isfile(p) else "missing"))

    # --- CSS 变量完整性：所有 var(--x) 引用都应有定义 ---
    css_files = [os.path.join(ui_dir, "css", n)
                 for n in ("themes.css", "ore_ui.css", "layout.css")]
    defined = set()
    used = set()
    for path in css_files:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        for m in re.finditer(r"(--[a-z0-9-]+)\s*:", text):
            defined.add(m.group(1))
        for m in re.finditer(r"var\(\s*(--[a-z0-9-]+)", text):
            used.add(m.group(1))
    undefined = sorted(used - defined)
    check("CSS 变量引用均有定义（定义 %d / 引用 %d）" % (len(defined), len(used)),
          not undefined, undefined)

    # --- 后端 API 接口完整性 ---
    controller = hc_app.Controller()
    api = hc_app.Api(controller)
    expected = [
        "bootstrap", "list_tasks", "get_settings", "stats",
        "create_task", "update_task", "set_status", "toggle_complete",
        "delete_task", "clear_completed", "snooze_task",
        "update_settings", "set_theme",
        "hide_to_tray", "show_window", "quit_app", "get_system_theme",
    ]
    absent = [m for m in expected if not callable(getattr(api, m, None))]
    check("Api 暴露全部 %d 个前端接口" % len(expected), not absent, absent)

    # --- 前后端接口对齐 ---
    app_js = os.path.join(ui_dir, "js", "app.js")
    with open(app_js, "r", encoding="utf-8") as fh:
        js_src = fh.read()
    called = set(re.findall(r'callApi\(\s*"([a-z_]+)"', js_src))
    unknown = sorted([m for m in called if not hasattr(api, m)])
    check("前端调用的后端方法均存在（%d 个）" % len(called), not unknown, unknown)

    # --- 系统主题读取 ---
    theme = controller.system_theme()
    check("系统主题读取返回合法值", theme in ("light", "dark"), theme)

    # --- 任务装饰字段完整性 ---
    task = controller.store.create_task({
        "title": "校验用任务",
        "start_time": "2026-09-20 09:00",
        "end_time": "2026-09-20 18:00",
    })
    decorated = controller._decorate(task)
    for field in ("remaining_seconds", "remaining_text", "overdue", "progress"):
        check("装饰字段存在: %s" % field, field in decorated)
    controller.store.delete_task(task["id"])

    try:
        controller.scheduler.stop()
    except Exception:
        pass

    lines = []
    lines.append("=" * 56)
    lines.append("HC-Note 启动链路校验报告")
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

    out = os.path.join(ROOT, "startup_check_report.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(report)

    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
