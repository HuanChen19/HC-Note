/* ==========================================================================
   theme.js - 主题检测与切换
   支持 light / dark / system 三种模式，system 模式监听系统深浅色事件实时切换。
   ========================================================================== */

(function () {
    "use strict";

    var STORAGE_KEY = "hc-note-theme";
    var MODES = ["light", "dark", "system"];

    var listeners = [];
    var currentMode = "system";
    var resolved = "light";
    var mediaQuery = null;
    var urlLocked = false;   // URL 指定主题时锁定，不写回本地存储

    /* ------------------------------------------------------------------
       工具
       ------------------------------------------------------------------ */

    function normalizeMode(mode) {
        if (MODES.indexOf(mode) < 0) {
            return "system";
        }
        return mode;
    }

    function readStoredMode() {
        // URL 参数优先，便于预览与调试（?theme=light|dark|system）
        var fromUrl = readUrlMode();
        if (fromUrl) {
            return fromUrl;
        }
        try {
            var value = window.localStorage.getItem(STORAGE_KEY);
            if (value) {
                return normalizeMode(value);
            }
        } catch (err) {
            /* 隐私模式下 localStorage 可能不可用，静默降级 */
        }
        return "system";
    }

    function readUrlMode() {
        try {
            var m = /[?&]theme=([a-z]+)/i.exec(window.location.search);
            if (m) {
                var value = m[1].toLowerCase();
                if (MODES.indexOf(value) >= 0) {
                    return value;
                }
            }
        } catch (err) {
            /* 忽略解析失败 */
        }
        return null;
    }

    function writeStoredMode(mode) {
        try {
            window.localStorage.setItem(STORAGE_KEY, mode);
        } catch (err) {
            /* 忽略写入失败 */
        }
    }

    function getMediaQuery() {
        if (mediaQuery) {
            return mediaQuery;
        }
        if (window.matchMedia) {
            mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        }
        return mediaQuery;
    }

    function systemPrefersDark() {
        var mq = getMediaQuery();
        if (mq) {
            return !!mq.matches;
        }
        return false;
    }

    /* ------------------------------------------------------------------
       应用主题
       ------------------------------------------------------------------ */

    function resolve(mode) {
        if (mode === "system") {
            return systemPrefersDark() ? "dark" : "light";
        }
        return mode;
    }

    function applyTheme(theme, mode) {
        var root = document.documentElement;
        root.setAttribute("data-theme", theme);
        root.setAttribute("data-theme-mode", mode);
        resolved = theme;
    }

    function notify() {
        for (var i = 0; i < listeners.length; i += 1) {
            try {
                listeners[i](resolved, currentMode);
            } catch (err) {
                /* 单个监听器异常不影响其他监听器 */
            }
        }
    }

    function evaluate(persist) {
        var theme = resolve(currentMode);
        var changed = theme !== resolved;
        applyTheme(theme, currentMode);
        if (persist && !urlLocked) {
            writeStoredMode(currentMode);
        }
        if (changed) {
            notify();
        }
    }

    /* ------------------------------------------------------------------
       对外接口
       ------------------------------------------------------------------ */

    var ThemeManager = {
        init: function () {
            urlLocked = readUrlMode() !== null;
            currentMode = readStoredMode();
            resolved = resolve(currentMode);
            applyTheme(resolved, currentMode);

            var mq = getMediaQuery();
            if (mq) {
                var handler = function () {
                    if (currentMode === "system") {
                        evaluate(false);
                    }
                };
                if (mq.addEventListener) {
                    mq.addEventListener("change", handler);
                } else if (mq.addListener) {
                    mq.addListener(handler);
                }
            }
            return resolved;
        },

        getMode: function () {
            return currentMode;
        },

        getResolved: function () {
            return resolved;
        },

        setMode: function (mode) {
            currentMode = normalizeMode(mode);
            evaluate(true);
            return resolved;
        },

        /* 从后端读取系统主题（作为 prefers-color-scheme 的补充依据） */
        setSystemHint: function (systemTheme) {
            if (systemTheme !== "dark" && systemTheme !== "light") {
                return;
            }
            // 若媒体查询不可用，则退化为使用后端给出的系统主题
            if (!getMediaQuery() && currentMode === "system") {
                var theme = systemTheme;
                if (theme !== resolved) {
                    applyTheme(theme, currentMode);
                    notify();
                }
            }
        },

        onChange: function (fn) {
            if (typeof fn === "function") {
                listeners.push(fn);
            }
        }
    };

    window.HCNoteTheme = ThemeManager;
})();
