/* ==========================================================================
   app.js - HC-Note 页面业务逻辑与状态绑定
   负责：与后端 API 通信、渲染任务列表、处理交互、主题切换、定时刷新。
   ========================================================================== */

(function () {
    "use strict";

    var P = window.HCNoteTimePicker;
    var Theme = window.HCNoteTheme;

    /* ------------------------------------------------------------------
       全局状态
       ------------------------------------------------------------------ */

    var state = {
        tasks: [],
        stats: {},
        settings: {},
        capabilities: {},
        systemTheme: "light",
        filter: { kind: "all", value: "" },
        sort: "time",
        keyword: "",
        editingId: null,
        ready: false
    };

    var FILTERS = [
        { kind: "all", label: "全部待办" },
        { kind: "status", value: "pending", label: "未开始" },
        { kind: "status", value: "in_progress", label: "进行中" },
        { kind: "status", value: "expired", label: "已超时" },
        { kind: "status", value: "completed", label: "已完成" },
        { kind: "dated", label: "已设时间" },
        { kind: "undated", label: "未设时间" }
    ];

    var PRIORITY_LABELS = {
        low: "低",
        medium: "中",
        high: "高",
        urgent: "紧急"
    };

    var STATUS_LABELS = {
        pending: "未开始",
        in_progress: "进行中",
        completed: "已完成",
        expired: "已超时"
    };

    var PRIORITY_RANK = { urgent: 0, high: 1, medium: 2, low: 3 };

    /* ------------------------------------------------------------------
       DOM 引用
       ------------------------------------------------------------------ */

    var el = {};

    function cacheDom() {
        el.stats = {
            total: document.getElementById("stat-total"),
            running: document.getElementById("stat-running"),
            done: document.getElementById("stat-done"),
            expired: document.getElementById("stat-expired")
        };
        el.filterList = document.getElementById("filter-list");
        el.groupList = document.getElementById("group-list");
        el.listTitle = document.getElementById("list-title");
        el.taskList = document.getElementById("task-list");
        el.emptyState = document.getElementById("empty-state");
        el.emptyText = document.getElementById("empty-text");
        el.searchInput = document.getElementById("search-input");
        el.sortSelect = document.getElementById("sort-select");
        el.quickInput = document.getElementById("quick-input");
        el.quickSubmit = document.getElementById("quick-submit");
        el.btnNew = document.getElementById("btn-new");
        el.btnTray = document.getElementById("btn-tray");
        el.btnSettings = document.getElementById("btn-settings");
        el.btnClearDone = document.getElementById("btn-clear-done");
        el.themeSeg = document.getElementById("theme-seg");
        el.toastStack = document.getElementById("toast-stack");

        el.taskModal = document.getElementById("task-modal");
        el.taskModalTitle = document.getElementById("task-modal-title");
        el.taskModalClose = document.getElementById("task-modal-close");
        el.taskModalCancel = document.getElementById("task-modal-cancel");
        el.taskModalSave = document.getElementById("task-modal-save");
        el.fTitle = document.getElementById("f-title");
        el.fDesc = document.getElementById("f-desc");
        el.fPriority = document.getElementById("f-priority");
        el.fGroup = document.getElementById("f-group");
        el.fStart = document.getElementById("f-start");
        el.fEnd = document.getElementById("f-end");
        el.groupOptions = document.getElementById("group-options");
        el.formError = document.getElementById("form-error");
        el.presetsWrap = document.getElementById("dtp-presets");

        el.settingsModal = document.getElementById("settings-modal");
        el.settingsModalClose = document.getElementById("settings-modal-close");
        el.settingsModalSave = document.getElementById("settings-modal-save");
        el.sBefore = document.getElementById("s-before");
        el.sTheme = document.getElementById("s-theme");
        el.sSound = document.getElementById("s-sound");
        el.sTray = document.getElementById("s-tray");
        el.envInfo = document.getElementById("env-info");
    }

    /* ------------------------------------------------------------------
       API 桥接
       ------------------------------------------------------------------ */

    function apiReady() {
        return !!(window.pywebview && window.pywebview.api);
    }

    /* ------------------------------------------------------------------
       预览数据注入
       仅当 URL 带 ?mock=1 时启用，用于在没有 pywebview 容器的浏览器中
       验证界面渲染效果，不影响正常打包运行时的行为。
       ------------------------------------------------------------------ */

    function mockEnabled() {
        return /[?&]mock=1/.test(window.location.search);
    }

    function mockNow() {
        var d = new Date();
        return P.format(d);
    }

    function buildMockApi() {
        var now = new Date();
        var iso = function (date) {
            return P.format(date);
        };
        var minus = function (minutes) {
            return iso(new Date(now.getTime() - minutes * 60000));
        };
        var plus = function (minutes) {
            return iso(new Date(now.getTime() + minutes * 60000));
        };

        var tasks = [
            {
                id: "task_20260919_001",
                title: "完成 Addon 模型材质烘焙",
                description: "修复几何体重叠面的 UV 贴图拉伸，并重新输出 16x16 贴图集。",
                priority: "urgent",
                status: "in_progress",
                group: "开发",
                start_time: minus(95),
                end_time: plus(42),
                created_at: minus(300),
                completed_at: null,
                reminders_sent: { start: true, pre_end: false, end: false },
                snooze_until: null,
                remaining_seconds: 2520,
                remaining_text: "42 分钟",
                overdue: false,
                progress: 69
            },
            {
                id: "task_20260919_002",
                title: "整理基岩版 Jigsaw 结构池配置",
                description: "把 template_pools 的 hc_feature 分组补充完整。",
                priority: "high",
                status: "pending",
                group: "开发",
                start_time: plus(120),
                end_time: plus(420),
                created_at: minus(240),
                completed_at: null,
                reminders_sent: { start: false, pre_end: false, end: false },
                snooze_until: null,
                remaining_seconds: 25200,
                remaining_text: "7 小时 0 分",
                overdue: false,
                progress: 0
            },
            {
                id: "task_20260919_003",
                title: "重构任务列表滚动区样式",
                description: "嵌套滚动容器每一级都要 min-height: 0，否则内容会溢出。",
                priority: "medium",
                status: "expired",
                group: "开发",
                start_time: minus(300),
                end_time: minus(25),
                created_at: minus(600),
                completed_at: null,
                reminders_sent: { start: true, pre_end: true, end: true },
                snooze_until: null,
                remaining_seconds: -1500,
                remaining_text: "25 分钟",
                overdue: true,
                progress: 100
            },
            {
                id: "task_20260919_004",
                title: "更新 README 截图与打包说明",
                description: "",
                priority: "low",
                status: "pending",
                group: "文档",
                start_time: null,
                end_time: null,
                created_at: minus(120),
                completed_at: null,
                reminders_sent: { start: false, pre_end: false, end: false },
                snooze_until: null,
                remaining_seconds: null,
                remaining_text: "",
                overdue: false,
                progress: 0
            },
            {
                id: "task_20260919_005",
                title: "完成 Ore UI 控件九宫格切片",
                description: "按钮、复选框、输入框、滚动条四类控件各三态。",
                priority: "high",
                status: "completed",
                group: "开发",
                start_time: minus(1440),
                end_time: minus(720),
                created_at: minus(1500),
                completed_at: minus(780),
                reminders_sent: { start: true, pre_end: true, end: true },
                snooze_until: null,
                remaining_seconds: null,
                remaining_text: "",
                overdue: false,
                progress: 100
            },
            {
                id: "task_20260919_006",
                title: "确认 WebView2 运行时版本覆盖",
                description: "确认目标机器上 WebView2 Runtime 不低于 100 版本。",
                priority: "medium",
                status: "completed",
                group: "测试",
                start_time: minus(2000),
                end_time: minus(1800),
                created_at: minus(2100),
                completed_at: minus(1850),
                reminders_sent: { start: true, pre_end: true, end: true },
                snooze_until: null,
                remaining_seconds: null,
                remaining_text: "",
                overdue: false,
                progress: 100
            }
        ];

        var settings = {
            theme: "system",
            sound_enabled: true,
            notify_before_minutes: 15,
            minimize_to_tray: true,
            launch_at_startup: false
        };

        function computeStats() {
            var stats = { total: tasks.length, completed: 0, in_progress: 0, expired: 0, pending: 0 };
            for (var i = 0; i < tasks.length; i += 1) {
                stats[tasks[i].status] = (stats[tasks[i].status] || 0) + 1;
            }
            return stats;
        }

        function ok(payload) {
            payload.ok = true;
            return Promise.resolve(payload);
        }

        return {
            bootstrap: function () {
                return ok({
                    settings: settings,
                    tasks: tasks,
                    stats: computeStats(),
                    system_theme: "light",
                    capabilities: { toast: true, tray: true }
                });
            },
            list_tasks: function () {
                return ok({ tasks: tasks, stats: computeStats() });
            },
            get_settings: function () {
                return Promise.resolve(settings);
            },
            stats: function () {
                return Promise.resolve(computeStats());
            },
            create_task: function (payload) {
                var t = {
                    id: "task_mock_" + (tasks.length + 1),
                    title: payload.title,
                    description: payload.description || "",
                    priority: payload.priority || "medium",
                    status: "pending",
                    group: payload.group || "默认",
                    start_time: payload.start_time || null,
                    end_time: payload.end_time || null,
                    created_at: mockNow(),
                    completed_at: null,
                    reminders_sent: { start: false, pre_end: false, end: false },
                    snooze_until: null,
                    remaining_seconds: null,
                    remaining_text: "",
                    overdue: false,
                    progress: 0
                };
                tasks.push(t);
                return ok({ task: t, stats: computeStats() });
            },
            update_task: function (id, patch) {
                var found = null;
                for (var i = 0; i < tasks.length; i += 1) {
                    if (tasks[i].id === id) {
                        found = tasks[i];
                        break;
                    }
                }
                if (!found) {
                    return Promise.resolve({ ok: false, error: "任务不存在" });
                }
                for (var k in patch) {
                    if (patch.hasOwnProperty(k)) {
                        found[k] = patch[k];
                    }
                }
                return ok({ task: found, stats: computeStats() });
            },
            set_status: function (id, status) {
                for (var i = 0; i < tasks.length; i += 1) {
                    if (tasks[i].id === id) {
                        tasks[i].status = status;
                        return ok({ task: tasks[i], stats: computeStats() });
                    }
                }
                return Promise.resolve({ ok: false, error: "任务不存在" });
            },
            toggle_complete: function (id) {
                for (var i = 0; i < tasks.length; i += 1) {
                    if (tasks[i].id === id) {
                        tasks[i].status = tasks[i].status === "completed" ? "pending" : "completed";
                        return ok({ task: tasks[i], stats: computeStats() });
                    }
                }
                return Promise.resolve({ ok: false, error: "任务不存在" });
            },
            delete_task: function (id) {
                for (var i = 0; i < tasks.length; i += 1) {
                    if (tasks[i].id === id) {
                        tasks.splice(i, 1);
                        break;
                    }
                }
                return ok({ stats: computeStats() });
            },
            clear_completed: function () {
                var before = tasks.length;
                tasks = tasks.filter(function (t) {
                    return t.status !== "completed";
                });
                return ok({ removed: before - tasks.length, stats: computeStats() });
            },
            snooze_task: function (id, minutes) {
                for (var i = 0; i < tasks.length; i += 1) {
                    if (tasks[i].id === id) {
                        tasks[i].snooze_until = P.format(new Date(new Date().getTime() + minutes * 60000));
                        return ok({ task: tasks[i] });
                    }
                }
                return Promise.resolve({ ok: false, error: "任务不存在" });
            },
            update_settings: function (patch) {
                for (var k in patch) {
                    if (patch.hasOwnProperty(k)) {
                        settings[k] = patch[k];
                    }
                }
                return ok({ settings: settings });
            },
            set_theme: function (theme) {
                settings.theme = theme;
                return ok({ settings: settings });
            },
            hide_to_tray: function () {
                return Promise.resolve({ ok: false, error: "浏览器预览模式不支持托盘" });
            },
            show_window: function () {
                return Promise.resolve({ ok: true });
            },
            quit_app: function () {
                return Promise.resolve({ ok: true });
            },
            get_system_theme: function () {
                return Promise.resolve("light");
            }
        };
    }

    function installMockApi() {
        window.pywebview = { api: buildMockApi() };
    }

    function callApi(name) {
        var args = Array.prototype.slice.call(arguments, 1);
        if (!apiReady()) {
            return Promise.reject(new Error("后端接口尚未就绪"));
        }
        return window.pywebview.api[name].apply(window.pywebview.api, args);
    }

    /* ------------------------------------------------------------------
       提示条
       ------------------------------------------------------------------ */

    function toast(message, isError) {
        if (!el.toastStack) {
            return;
        }
        var node = document.createElement("div");
        node.className = "toast-item" + (isError ? " is-error" : "");
        node.textContent = message;
        el.toastStack.appendChild(node);
        window.setTimeout(function () {
            if (node.parentNode) {
                node.parentNode.removeChild(node);
            }
        }, 2600);
    }

    /* ------------------------------------------------------------------
       数据加载
       ------------------------------------------------------------------ */

    function bootstrap() {
        return callApi("bootstrap").then(function (data) {
            if (!data || !data.ok) {
                throw new Error("初始化失败");
            }
            state.settings = data.settings || {};
            state.tasks = data.tasks || [];
            state.stats = data.stats || {};
            state.capabilities = data.capabilities || {};
            state.systemTheme = data.system_theme || "light";
            state.ready = true;

            Theme.setSystemHint(state.systemTheme);
            syncThemeUi();
            renderAll();
            return data;
        });
    }

    function refresh() {
        if (!state.ready) {
            return Promise.resolve();
        }
        return callApi("list_tasks").then(function (data) {
            if (!data || !data.ok) {
                return;
            }
            state.tasks = data.tasks || [];
            state.stats = data.stats || {};
            renderAll();
        }).catch(function () {
            /* 刷新失败时保持现有视图，避免界面闪烁 */
        });
    }

    /* ------------------------------------------------------------------
       过滤与排序
       ------------------------------------------------------------------ */

    function matchesFilter(task) {
        var f = state.filter;
        if (f.kind === "all") {
            return true;
        }
        if (f.kind === "status") {
            return task.status === f.value;
        }
        if (f.kind === "dated") {
            return !!(task.start_time || task.end_time);
        }
        if (f.kind === "undated") {
            return !task.start_time && !task.end_time;
        }
        if (f.kind === "group") {
            return (task.group || "默认") === f.value;
        }
        return true;
    }

    function matchesKeyword(task) {
        if (!state.keyword) {
            return true;
        }
        var kw = state.keyword.toLowerCase();
        var title = (task.title || "").toLowerCase();
        var desc = (task.description || "").toLowerCase();
        var group = (task.group || "").toLowerCase();
        return title.indexOf(kw) >= 0 || desc.indexOf(kw) >= 0 || group.indexOf(kw) >= 0;
    }

    function visibleTasks() {
        var list = state.tasks.filter(function (t) {
            return matchesFilter(t) && matchesKeyword(t);
        });

        var sort = state.sort;
        list.sort(function (a, b) {
            if (sort === "priority") {
                var ra = PRIORITY_RANK[a.priority] !== undefined ? PRIORITY_RANK[a.priority] : 9;
                var rb = PRIORITY_RANK[b.priority] !== undefined ? PRIORITY_RANK[b.priority] : 9;
                if (ra !== rb) {
                    return ra - rb;
                }
            } else if (sort === "created") {
                return String(b.created_at || "").localeCompare(String(a.created_at || ""));
            }
            // 默认按结束时间排序，无时间的排在最后
            var ea = a.end_time || "";
            var eb = b.end_time || "";
            if (ea && eb) {
                return ea.localeCompare(eb);
            }
            if (ea) {
                return -1;
            }
            if (eb) {
                return 1;
            }
            return String(a.created_at || "").localeCompare(String(b.created_at || ""));
        });

        // 已完成的始终沉底
        var active = [];
        var done = [];
        for (var i = 0; i < list.length; i += 1) {
            if (list[i].status === "completed") {
                done.push(list[i]);
            } else {
                active.push(list[i]);
            }
        }
        return active.concat(done);
    }

    /* ------------------------------------------------------------------
       渲染
       ------------------------------------------------------------------ */

    function renderAll() {
        renderStats();
        renderFilters();
        renderGroups();
        renderTaskList();
        renderGroupOptions();
    }

    function renderStats() {
        var s = state.stats || {};
        if (el.stats.total) {
            el.stats.total.textContent = s.total || 0;
        }
        if (el.stats.running) {
            el.stats.running.textContent = s.in_progress || 0;
        }
        if (el.stats.done) {
            el.stats.done.textContent = s.completed || 0;
        }
        if (el.stats.expired) {
            el.stats.expired.textContent = s.expired || 0;
        }
    }

    function countByFilter(filter) {
        var saved = state.filter;
        state.filter = filter;
        var count = state.tasks.filter(function (t) {
            return matchesFilter(t);
        }).length;
        state.filter = saved;
        return count;
    }

    function renderFilters() {
        if (!el.filterList) {
            return;
        }
        var html = "";
        for (var i = 0; i < FILTERS.length; i += 1) {
            var f = FILTERS[i];
            var active = state.filter.kind === f.kind &&
                (f.kind !== "status" || state.filter.value === f.value);
            html += '<button class="filter-item' + (active ? " is-active" : "") +
                '" type="button" data-filter-index="' + i + '">' +
                '<span>' + f.label + "</span>" +
                '<span class="filter-count">' + countByFilter(f) + "</span>" +
                "</button>";
        }
        el.filterList.innerHTML = html;
    }

    function collectGroups() {
        var map = {};
        for (var i = 0; i < state.tasks.length; i += 1) {
            var g = state.tasks[i].group || "默认";
            map[g] = (map[g] || 0) + 1;
        }
        var names = Object.keys(map);
        names.sort(function (a, b) {
            return a.localeCompare(b, "zh-Hans-CN");
        });
        return names.map(function (name) {
            return { name: name, count: map[name] };
        });
    }

    function renderGroups() {
        if (!el.groupList) {
            return;
        }
        var groups = collectGroups();
        var html = "";
        for (var i = 0; i < groups.length; i += 1) {
            var g = groups[i];
            var active = state.filter.kind === "group" && state.filter.value === g.name;
            html += '<button class="filter-item' + (active ? " is-active" : "") +
                '" type="button" data-group="' + escapeAttr(g.name) + '">' +
                "<span>" + escapeHtml(g.name) + "</span>" +
                '<span class="filter-count">' + g.count + "</span>" +
                "</button>";
        }
        if (!html) {
            html = '<div class="form-hint" style="padding:6px 2px;">暂无分组</div>';
        }
        el.groupList.innerHTML = html;
    }

    function renderGroupOptions() {
        if (!el.groupOptions) {
            return;
        }
        var groups = collectGroups();
        var html = "";
        for (var i = 0; i < groups.length; i += 1) {
            html += '<option value="' + escapeAttr(groups[i].name) + '"></option>';
        }
        el.groupOptions.innerHTML = html;
    }

    function currentFilterLabel() {
        var f = state.filter;
        if (f.kind === "group") {
            return "分组：" + f.value;
        }
        for (var i = 0; i < FILTERS.length; i += 1) {
            if (FILTERS[i].kind === f.kind && (f.kind !== "status" || FILTERS[i].value === f.value)) {
                return FILTERS[i].label;
            }
        }
        return "全部待办";
    }

    function renderTaskList() {
        if (!el.taskList) {
            return;
        }
        var list = visibleTasks();
        if (el.listTitle) {
            el.listTitle.textContent = currentFilterLabel() + "（" + list.length + "）";
        }

        if (!list.length) {
            el.taskList.innerHTML = "";
            if (el.emptyState) {
                el.emptyState.hidden = false;
                if (el.emptyText) {
                    el.emptyText.textContent = state.tasks.length
                        ? "当前过滤条件下没有匹配的待办"
                        : "暂无待办事项，点击右上角「新增待办」开始";
                }
            }
            return;
        }

        if (el.emptyState) {
            el.emptyState.hidden = true;
        }

        var html = "";
        for (var i = 0; i < list.length; i += 1) {
            html += renderTaskCard(list[i]);
        }
        el.taskList.innerHTML = html;
    }

    function priorityClass(task) {
        return "prio-" + (task.priority || "medium");
    }

    function statusClass(task) {
        if (task.status === "completed") {
            return "is-done";
        }
        if (task.status === "expired") {
            return "is-expired";
        }
        if (task.status === "in_progress") {
            return "is-running";
        }
        return "";
    }

    function renderTaskCard(task) {
        var prio = task.priority || "medium";
        var classes = ["todo-item", statusClass(task)];
        var checked = task.status === "completed" ? "true" : "false";

        var html = '<article class="' + classes.join(" ").trim() + '" data-task-id="' +
            escapeAttr(task.id) + '">';
        html += '<span class="prio-bar ' + priorityClass(task) + '"></span>';

        var arrow = task.description ? "▸" : "&nbsp;";
        html += '<div class="todo-main">';
        html += '<button class="mc-checkbox" type="button" data-act="toggle" data-checked="' +
            checked + '" title="标记完成 / 撤销"></button>';
        html += '<div class="todo-body">';
        html += '<div class="todo-headline">';
        html += '<span class="todo-title">' + escapeHtml(task.title) + "</span>";
        html += '<span class="badge badge-prio-' + prio + '">' +
            (PRIORITY_LABELS[prio] || "中") + "</span>";
        if (task.status === "completed") {
            html += '<span class="badge badge-done">已完成</span>';
        } else if (task.status === "expired") {
            html += '<span class="badge badge-expired">已超时</span>';
        } else if (task.status === "in_progress") {
            html += '<span class="badge badge-running">进行中</span>';
        }
        if (task.group && task.group !== "默认") {
            html += '<span class="badge">' + escapeHtml(task.group) + "</span>";
        }
        html += "</div>";

        if (task.description) {
            html += '<p class="todo-desc">' + escapeHtml(task.description) + "</p>";
        }

        html += '<div class="todo-meta">';
        html += '<span class="todo-time">开始 ' +
            escapeHtml(task.start_time || "未设置") + "</span>";
        html += '<span class="todo-time">结束 ' +
            escapeHtml(task.end_time || "未设置") + "</span>";
        if (task.remaining_text && task.status !== "completed") {
            html += '<span class="todo-time">' +
                (task.overdue ? "已超时 " : "剩余 ") + escapeHtml(task.remaining_text) + "</span>";
        }
        if (task.snooze_until) {
            html += '<span class="todo-time">推迟至 ' + escapeHtml(task.snooze_until) + "</span>";
        }
        html += "</div>";

        // 区间进度条（已完成任务不再展示，避免视觉噪音）
        if (task.start_time && task.end_time && task.status !== "completed") {
            var fillClass = "progress-fill";
            if (task.status === "expired") {
                fillClass += " is-expired";
            }
            html += '<div class="todo-progress">';
            html += '<div class="progress"><div class="' + fillClass +
                '" style="width:' + (task.progress || 0) + '%"></div></div>';
            html += "</div>";
        }

        html += "</div>";

        html += '<div class="todo-actions">';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-act="edit" title="编辑">编辑</button>';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-act="snooze" title="推迟 10 分钟提醒">推迟</button>';
        html += '<button class="btn btn-sm btn-danger" type="button" data-act="delete" title="删除">删除</button>';
        html += "</div>";

        html += "</div>";

        // 展开抽屉
        html += '<div class="todo-drawer">';
        html += '<p class="drawer-desc">' +
            escapeHtml(task.description || "（无详细描述）") + "</p>";
        html += '<div class="drawer-row">';
        html += "<span>状态：" + (STATUS_LABELS[task.status] || task.status) + "</span>";
        html += "<span>创建：" + escapeHtml(task.created_at || "") + "</span>";
        if (task.completed_at) {
            html += "<span>完成：" + escapeHtml(task.completed_at) + "</span>";
        }
        html += "<span>ID：" + escapeHtml(task.id) + "</span>";
        html += "</div>";
        html += "</div>";

        html += "</article>";
        return html;
    }

    /* ------------------------------------------------------------------
       转义
       ------------------------------------------------------------------ */

    function escapeHtml(text) {
        return String(text === null || text === undefined ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function escapeAttr(text) {
        return escapeHtml(text);
    }

    /* ------------------------------------------------------------------
       交互：任务列表
       ------------------------------------------------------------------ */

    function findTask(taskId) {
        for (var i = 0; i < state.tasks.length; i += 1) {
            if (state.tasks[i].id === taskId) {
                return state.tasks[i];
            }
        }
        return null;
    }

    function handleTaskListClick(event) {
        var actionBtn = closestWith(event.target, "[data-act]");
        if (actionBtn) {
            var card = closestWith(actionBtn, "[data-task-id]");
            if (!card) {
                return;
            }
            var taskId = card.getAttribute("data-task-id");
            var act = actionBtn.getAttribute("data-act");
            event.preventDefault();
            event.stopPropagation();
            runTaskAction(act, taskId);
            return;
        }

        var item = closestWith(event.target, "[data-task-id]");
        if (item) {
            // 点击卡片空白处切换详情抽屉
            item.classList.toggle("is-open");
        }
    }

    function runTaskAction(act, taskId) {
        if (act === "toggle") {
            callApi("toggle_complete", taskId).then(function (res) {
                if (res && res.ok) {
                    refresh();
                } else {
                    toast((res && res.error) || "操作失败", true);
                }
            }).catch(function (err) {
                toast(err.message || "操作失败", true);
            });
            return;
        }

        if (act === "edit") {
            openTaskModal(findTask(taskId));
            return;
        }

        if (act === "snooze") {
            callApi("snooze_task", taskId, 10).then(function (res) {
                if (res && res.ok) {
                    toast("已推迟 10 分钟提醒");
                    refresh();
                } else {
                    toast((res && res.error) || "推迟失败", true);
                }
            }).catch(function (err) {
                toast(err.message || "推迟失败", true);
            });
            return;
        }

        if (act === "delete") {
            var task = findTask(taskId);
            var name = task ? task.title : "该任务";
            if (!window.confirm("确定删除「" + name + "」？此操作不可撤销。")) {
                return;
            }
            callApi("delete_task", taskId).then(function (res) {
                if (res && res.ok) {
                    toast("已删除");
                    refresh();
                } else {
                    toast("删除失败", true);
                }
            }).catch(function (err) {
                toast(err.message || "删除失败", true);
            });
        }
    }

    function closestWith(node, selector) {
        var current = node;
        while (current && current !== document) {
            if (current.nodeType === 1 && current.matches && current.matches(selector)) {
                return current;
            }
            current = current.parentNode;
        }
        return null;
    }

    /* ------------------------------------------------------------------
       交互：过滤与搜索
       ------------------------------------------------------------------ */

    function handleFilterClick(event) {
        var idxBtn = closestWith(event.target, "[data-filter-index]");
        if (idxBtn) {
            var idx = parseInt(idxBtn.getAttribute("data-filter-index"), 10);
            var f = FILTERS[idx];
            if (f) {
                state.filter = { kind: f.kind, value: f.value || "" };
                renderFilters();
                renderGroups();
                renderTaskList();
            }
            return;
        }

        var groupBtn = closestWith(event.target, "[data-group]");
        if (groupBtn) {
            var name = groupBtn.getAttribute("data-group");
            if (state.filter.kind === "group" && state.filter.value === name) {
                state.filter = { kind: "all", value: "" };
            } else {
                state.filter = { kind: "group", value: name };
            }
            renderFilters();
            renderGroups();
            renderTaskList();
        }
    }

    /* ------------------------------------------------------------------
       交互：新增 / 编辑弹窗
       ------------------------------------------------------------------ */

    var startPicker = null;
    var endPicker = null;

    function initPickers() {
        startPicker = P.create(document.getElementById("dtp-start"), {
            presetsWrap: null,
            onError: setFormError
        });
        endPicker = P.create(document.getElementById("dtp-end"), {
            presetsWrap: null,
            onError: setFormError
        });

        // 预设统一由这里设置两个组件，避免互相覆盖
        var wrap = el.presetsWrap;
        if (!wrap) {
            return;
        }
        wrap.innerHTML = "";
        for (var i = 0; i < P.presets.length; i += 1) {
            (function (preset) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "preset-btn";
                btn.textContent = preset.label;
                btn.addEventListener("click", function (e) {
                    e.preventDefault();
                    var result = preset.build(new Date());
                    startPicker.setValue(result.start || "");
                    endPicker.setValue(result.end || "");
                    setFormError("");
                });
                wrap.appendChild(btn);
            })(P.presets[i]);
        }
    }

    function setFormError(message) {
        if (el.formError) {
            el.formError.textContent = message || "";
        }
    }

    function openTaskModal(task) {
        state.editingId = task ? task.id : null;
        if (el.taskModalTitle) {
            el.taskModalTitle.textContent = task ? "编辑待办" : "新增待办";
        }
        el.fTitle.value = task ? task.title || "" : "";
        el.fDesc.value = task ? task.description || "" : "";
        el.fPriority.value = task ? task.priority || "medium" : "medium";
        el.fGroup.value = task ? (task.group === "默认" ? "" : task.group) || "" : "";
        startPicker.setValue(task ? task.start_time || "" : "");
        endPicker.setValue(task ? task.end_time || "" : "");
        setFormError("");
        openModal(el.taskModal);
        window.setTimeout(function () {
            el.fTitle.focus();
        }, 40);
    }

    function closeTaskModal() {
        closeModal(el.taskModal);
        state.editingId = null;
        startPicker.closePop();
        endPicker.closePop();
    }

    function saveTask() {
        var title = (el.fTitle.value || "").trim();
        if (!title) {
            setFormError("请填写标题");
            el.fTitle.focus();
            return;
        }

        if (!startPicker.isValid()) {
            setFormError("开始时间格式应为 YYYY-MM-DD HH:mm");
            return;
        }
        if (!endPicker.isValid()) {
            setFormError("结束时间格式应为 YYYY-MM-DD HH:mm");
            return;
        }

        var startText = startPicker.getValue();
        var endText = endPicker.getValue();
        var startDate = startText ? P.parse(startText) : null;
        var endDate = endText ? P.parse(endText) : null;
        if (startDate && endDate && endDate < startDate) {
            setFormError("结束时间不能早于开始时间");
            return;
        }

        var payload = {
            title: title,
            description: el.fDesc.value || "",
            priority: el.fPriority.value,
            group: (el.fGroup.value || "").trim() || "默认",
            start_time: startText || null,
            end_time: endText || null
        };

        var request = state.editingId
            ? callApi("update_task", state.editingId, payload)
            : callApi("create_task", payload);

        request.then(function (res) {
            if (res && res.ok) {
                closeTaskModal();
                toast(state.editingId ? "已保存修改" : "已新增待办");
                refresh();
            } else {
                setFormError((res && res.error) || "保存失败");
            }
        }).catch(function (err) {
            setFormError(err.message || "保存失败");
        });
    }

    /* ------------------------------------------------------------------
       交互：设置弹窗
       ------------------------------------------------------------------ */

    function syncCheckbox(node, checked) {
        if (!node) {
            return;
        }
        node.checked = !!checked;
        node.setAttribute("data-checked", checked ? "true" : "false");
    }

    function openSettings() {
        var s = state.settings || {};
        el.sTheme.value = s.theme || "system";
        el.sBefore.value = s.notify_before_minutes !== undefined ? s.notify_before_minutes : 15;
        syncCheckbox(el.sSound, s.sound_enabled !== false);
        syncCheckbox(el.sTray, s.minimize_to_tray !== false);

        if (el.envInfo) {
            var caps = state.capabilities || {};
            var parts = [];
            parts.push("原生通知：" + (caps.toast ? "可用" : "降级"));
            parts.push("系统托盘：" + (caps.tray ? "可用" : "不可用"));
            el.envInfo.textContent = parts.join("　|　");
        }
        openModal(el.settingsModal);
    }

    function closeSettings() {
        closeModal(el.settingsModal);
    }

    function saveSettings() {
        var patch = {
            theme: el.sTheme.value,
            notify_before_minutes: parseInt(el.sBefore.value, 10) || 0,
            sound_enabled: !!el.sSound.checked,
            minimize_to_tray: !!el.sTray.checked
        };
        callApi("update_settings", patch).then(function (res) {
            if (res && res.ok) {
                state.settings = res.settings || state.settings;
                Theme.setMode(patch.theme);
                syncThemeUi();
                closeSettings();
                toast("设置已保存");
                refresh();
            } else {
                toast("设置保存失败", true);
            }
        }).catch(function (err) {
            toast(err.message || "设置保存失败", true);
        });
    }

    /* ------------------------------------------------------------------
       模态通用
       ------------------------------------------------------------------ */

    function openModal(node) {
        if (node) {
            node.classList.add("is-open");
        }
    }

    function closeModal(node) {
        if (node) {
            node.classList.remove("is-open");
        }
    }

    /* ------------------------------------------------------------------
       主题 UI 同步
       ------------------------------------------------------------------ */

    function syncThemeUi() {
        if (!el.themeSeg) {
            return;
        }
        var mode = Theme.getMode();
        var btns = el.themeSeg.querySelectorAll("[data-theme-value]");
        for (var i = 0; i < btns.length; i += 1) {
            if (btns[i].getAttribute("data-theme-value") === mode) {
                btns[i].classList.add("is-active");
            } else {
                btns[i].classList.remove("is-active");
            }
        }
    }

    function handleThemeClick(event) {
        var btn = closestWith(event.target, "[data-theme-value]");
        if (!btn) {
            return;
        }
        var mode = btn.getAttribute("data-theme-value");
        Theme.setMode(mode);
        syncThemeUi();
        callApi("set_theme", mode).then(function (res) {
            if (res && res.ok) {
                state.settings = res.settings || state.settings;
            }
        }).catch(function () {
            /* 主题已本地生效，后端保存失败不阻塞用户 */
        });
    }

    /* ------------------------------------------------------------------
       快速新增
       ------------------------------------------------------------------ */

    function quickAdd() {
        var title = (el.quickInput.value || "").trim();
        if (!title) {
            return;
        }
        callApi("create_task", { title: title, priority: "medium", group: "默认" }).then(function (res) {
            if (res && res.ok) {
                el.quickInput.value = "";
                // 新建任务后打开编辑弹窗补充时间区间
                openTaskModal(res.task);
                refresh();
            } else {
                toast((res && res.error) || "新增失败", true);
            }
        }).catch(function (err) {
            toast(err.message || "新增失败", true);
        });
    }

    /* ------------------------------------------------------------------
       事件绑定
       ------------------------------------------------------------------ */

    function bindEvents() {
        if (el.taskList) {
            el.taskList.addEventListener("click", handleTaskListClick);
        }
        if (el.filterList) {
            el.filterList.addEventListener("click", handleFilterClick);
        }
        if (el.groupList) {
            el.groupList.addEventListener("click", handleFilterClick);
        }

        if (el.searchInput) {
            el.searchInput.addEventListener("input", function () {
                state.keyword = (this.value || "").trim();
                renderTaskList();
            });
        }

        if (el.sortSelect) {
            el.sortSelect.addEventListener("change", function () {
                state.sort = this.value;
                renderTaskList();
            });
        }

        if (el.quickSubmit) {
            el.quickSubmit.addEventListener("click", quickAdd);
        }
        if (el.quickInput) {
            el.quickInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    quickAdd();
                }
            });
        }

        if (el.btnNew) {
            el.btnNew.addEventListener("click", function () {
                openTaskModal(null);
            });
        }

        if (el.btnTray) {
            el.btnTray.addEventListener("click", function () {
                callApi("hide_to_tray").catch(function () {
                    toast("最小化到托盘失败", true);
                });
            });
        }

        if (el.btnSettings) {
            el.btnSettings.addEventListener("click", openSettings);
        }

        if (el.btnClearDone) {
            el.btnClearDone.addEventListener("click", function () {
                var doneCount = (state.stats && state.stats.completed) || 0;
                if (!doneCount) {
                    toast("没有可清理的已完成任务");
                    return;
                }
                if (!window.confirm("将删除 " + doneCount + " 条已完成任务，确定继续？")) {
                    return;
                }
                callApi("clear_completed").then(function (res) {
                    if (res && res.ok) {
                        toast("已清理 " + (res.removed || 0) + " 条");
                        refresh();
                    }
                }).catch(function (err) {
                    toast(err.message || "清理失败", true);
                });
            });
        }

        if (el.themeSeg) {
            el.themeSeg.addEventListener("click", handleThemeClick);
        }

        // 任务弹窗
        if (el.taskModalClose) {
            el.taskModalClose.addEventListener("click", closeTaskModal);
        }
        if (el.taskModalCancel) {
            el.taskModalCancel.addEventListener("click", closeTaskModal);
        }
        if (el.taskModalSave) {
            el.taskModalSave.addEventListener("click", saveTask);
        }
        if (el.taskModal) {
            el.taskModal.addEventListener("mousedown", function (e) {
                if (e.target === el.taskModal) {
                    closeTaskModal();
                }
            });
        }

        // 设置弹窗
        if (el.settingsModalClose) {
            el.settingsModalClose.addEventListener("click", closeSettings);
        }
        if (el.settingsModalSave) {
            el.settingsModalSave.addEventListener("click", saveSettings);
        }
        if (el.settingsModal) {
            el.settingsModal.addEventListener("mousedown", function (e) {
                if (e.target === el.settingsModal) {
                    closeSettings();
                }
            });
        }

        // 复选框外观同步
        var boxes = document.querySelectorAll(".mc-checkbox");
        for (var i = 0; i < boxes.length; i += 1) {
            boxes[i].addEventListener("change", function () {
                this.setAttribute("data-checked", this.checked ? "true" : "false");
            });
        }

        // 全局快捷键
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                closeTaskModal();
                closeSettings();
            }
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
                e.preventDefault();
                openTaskModal(null);
            }
        });
    }

    /* ------------------------------------------------------------------
       对外刷新钩子（后端主动调用）
       ------------------------------------------------------------------ */

    window.HCNoteRefresh = function () {
        refresh();
    };

    /* ------------------------------------------------------------------
       启动
       ------------------------------------------------------------------ */

    function start() {
        cacheDom();
        Theme.init();
        initPickers();
        bindEvents();
        renderFilters();
        renderGroups();
        renderTaskList();
        syncThemeUi();

        // 浏览器预览模式：直接注入模拟数据，跳过等待容器桥接
        if (mockEnabled()) {
            installMockApi();
            bootstrap().catch(function (err) {
                toast(err.message || "初始化失败", true);
            });
            window.setInterval(function () {
                refresh();
            }, 60000);
            return;
        }

        // 等待 pywebview 注入完成
        var attempts = 0;
        var timer = window.setInterval(function () {
            attempts += 1;
            if (apiReady()) {
                window.clearInterval(timer);
                bootstrap().catch(function (err) {
                    toast(err.message || "初始化失败", true);
                });
            } else if (attempts > 100) {
                window.clearInterval(timer);
                toast("未能连接到后端服务", true);
            }
        }, 50);

        // 每分钟刷新一次，保持剩余时间与状态显示准确
        window.setInterval(function () {
            refresh();
        }, 60000);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
