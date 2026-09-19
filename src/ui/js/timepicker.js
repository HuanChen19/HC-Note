/* ==========================================================================
   timepicker.js - Minecraft 风格的日期时间选择组件
   提供 YYYY-MM-DD HH:mm 精确输入、像素风日历弹层、时间微调与快捷预设。
   ========================================================================== */

(function () {
    "use strict";

    var TIME_RE = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/;
    var DOW_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

    /* ------------------------------------------------------------------
       时间工具
       ------------------------------------------------------------------ */

    function pad(n) {
        return n < 10 ? "0" + n : "" + n;
    }

    function format(date) {
        if (!date) {
            return "";
        }
        return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()) +
            " " + pad(date.getHours()) + ":" + pad(date.getMinutes());
    }

    function parse(text) {
        if (!text) {
            return null;
        }
        var m = TIME_RE.exec(String(text).trim());
        if (!m) {
            return null;
        }
        var year = parseInt(m[1], 10);
        var month = parseInt(m[2], 10) - 1;
        var day = parseInt(m[3], 10);
        var hour = parseInt(m[4], 10);
        var minute = parseInt(m[5], 10);
        if (month < 0 || month > 11 || day < 1 || day > 31 || hour > 23 || minute > 59) {
            return null;
        }
        var d = new Date(year, month, day, hour, minute, 0, 0);
        // 校验溢出（例如 2 月 31 日会自动进位）
        if (d.getFullYear() !== year || d.getMonth() !== month || d.getDate() !== day) {
            return null;
        }
        return d;
    }

    function isValid(text) {
        return text === "" || text === null || parse(text) !== null;
    }

    function startOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
    }

    function endOfDay(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 0, 0);
    }

    function addDays(date, days) {
        var d = new Date(date.getTime());
        d.setDate(d.getDate() + days);
        return d;
    }

    /* ------------------------------------------------------------------
       快捷预设
       ------------------------------------------------------------------ */

    var PRESETS = [
        {
            label: "今天剩余时间",
            build: function (now) {
                return {
                    start: format(now),
                    end: format(endOfDay(now))
                };
            }
        },
        {
            label: "明天全天",
            build: function (now) {
                var t = addDays(now, 1);
                var start = startOfDay(t);
                start.setHours(9, 0, 0, 0);
                return {
                    start: format(start),
                    end: format(endOfDay(t))
                };
            }
        },
        {
            label: "未来 3 天",
            build: function (now) {
                return {
                    start: format(startOfDay(now)),
                    end: format(endOfDay(addDays(now, 2)))
                };
            }
        },
        {
            label: "本周剩余",
            build: function (now) {
                // 以周日为本周末尾
                var dow = now.getDay() === 0 ? 7 : now.getDay();
                var remain = 7 - dow;
                return {
                    start: format(now),
                    end: format(endOfDay(addDays(now, remain)))
                };
            }
        },
        {
            label: "2 小时后",
            build: function (now) {
                var end = new Date(now.getTime() + 120 * 60000);
                return {
                    start: format(now),
                    end: format(end)
                };
            }
        },
        {
            label: "清空时间",
            build: function () {
                return { start: "", end: "" };
            }
        }
    ];

    /* ==================================================================
       TimePicker：绑定到一个 dtp 容器
       ================================================================== */

    function TimePicker(root, options) {
        this.root = root;
        this.options = options || {};
        this.input = root.querySelector(".dtp-value");
        this.toggleBtn = root.querySelector(".dtp-toggle");
        this.pop = root.querySelector(".cal-pop");
        this.presetsWrap = this.options.presetsWrap || null;

        this.viewMonth = new Date();
        this.selected = null;
        this.open = false;
        this.errorHandler = this.options.onError || null;
        this.changeHandler = this.options.onChange || null;

        this._bind();
        this._buildPresets();
        this.setValue(this.input.value || "");
    }

    TimePicker.prototype._bind = function () {
        var self = this;

        if (this.toggleBtn) {
            this.toggleBtn.addEventListener("click", function (e) {
                e.preventDefault();
                self.togglePop();
            });
        }

        this.input.addEventListener("focus", function () {
            self.toggleBtn.classList.add("is-active");
        });

        this.input.addEventListener("blur", function () {
            self.toggleBtn.classList.remove("is-active");
            self.commitInput();
        });

        this.input.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                self.commitInput();
            } else if (e.key === "Escape") {
                self.closePop();
            }
        });

        // 点击外部关闭日历
        document.addEventListener("mousedown", function (e) {
            if (!self.open) {
                return;
            }
            if (self.root.contains(e.target)) {
                return;
            }
            self.closePop();
        });
    };

    TimePicker.prototype._buildPresets = function () {
        var wrap = this.presetsWrap;
        if (!wrap) {
            return;
        }
        var self = this;
        wrap.innerHTML = "";
        for (var i = 0; i < PRESETS.length; i += 1) {
            (function (preset) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "preset-btn";
                btn.textContent = preset.label;
                btn.addEventListener("click", function (e) {
                    e.preventDefault();
                    self.applyPreset(preset);
                });
                wrap.appendChild(btn);
            })(PRESETS[i]);
        }
    };

    TimePicker.prototype.applyPreset = function (preset) {
        var now = new Date();
        var result = preset.build(now);
        if (this.options.onPreset) {
            // 交由外部统一设置开始与结束，避免两个组件互相覆盖
            this.options.onPreset(result);
            return;
        }
        this.setValue(result.start || "");
    };

    TimePicker.prototype.commitInput = function () {
        var raw = (this.input.value || "").trim();
        if (raw === "") {
            this.selected = null;
            this._emitChange("");
            this._clearError();
            return;
        }
        var parsed = parse(raw);
        if (parsed === null) {
            this._setError("时间格式应为 YYYY-MM-DD HH:mm");
            return;
        }
        this.selected = parsed;
        this.viewMonth = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
        this._clearError();
        this._emitChange(format(parsed));
    };

    TimePicker.prototype._emitChange = function (value) {
        if (typeof this.changeHandler === "function") {
            this.changeHandler(value);
        }
    };

    TimePicker.prototype._setError = function (message) {
        if (typeof this.errorHandler === "function") {
            this.errorHandler(message);
        }
    };

    TimePicker.prototype._clearError = function () {
        if (typeof this.errorHandler === "function") {
            this.errorHandler("");
        }
    };

    /* ------------------------------------------------------------------
       取值 / 设值
       ------------------------------------------------------------------ */

    TimePicker.prototype.setValue = function (value) {
        var text = value === null || value === undefined ? "" : String(value);
        this.input.value = text;
        var parsed = parse(text);
        this.selected = parsed;
        if (parsed) {
            this.viewMonth = new Date(parsed.getFullYear(), parsed.getMonth(), 1);
        }
        this._clearError();
    };

    TimePicker.prototype.getValue = function () {
        var raw = (this.input.value || "").trim();
        if (raw === "") {
            return "";
        }
        var parsed = parse(raw);
        return parsed ? format(parsed) : raw;
    };

    TimePicker.prototype.isValid = function () {
        return isValid((this.input.value || "").trim());
    };

    /* ------------------------------------------------------------------
       日历弹层
       ------------------------------------------------------------------ */

    TimePicker.prototype.togglePop = function () {
        if (this.open) {
            this.closePop();
        } else {
            this.openPop();
        }
    };

    TimePicker.prototype.openPop = function () {
        this.open = true;
        this.pop.classList.add("is-open");
        var parsed = parse((this.input.value || "").trim());
        var base = parsed || new Date();
        this.viewMonth = new Date(base.getFullYear(), base.getMonth(), 1);
        this.renderCalendar();
    };

    TimePicker.prototype.closePop = function () {
        this.open = false;
        this.pop.classList.remove("is-open");
    };

    TimePicker.prototype.renderCalendar = function () {
        var self = this;
        var year = this.viewMonth.getFullYear();
        var month = this.viewMonth.getMonth();
        var today = new Date();

        var first = new Date(year, month, 1);
        // 以周一为每周第一天
        var offset = (first.getDay() + 6) % 7;
        var daysInMonth = new Date(year, month + 1, 0).getDate();

        var html = "";
        html += '<div class="cal-head">';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-nav="-1">‹</button>';
        html += '<span class="cal-month">' + year + " 年 " + (month + 1) + " 月</span>";
        html += '<button class="btn btn-sm btn-ghost" type="button" data-nav="1">›</button>';
        html += "</div>";

        html += '<div class="cal-grid">';
        for (var d = 0; d < 7; d += 1) {
            html += '<span class="cal-dow">' + DOW_LABELS[d] + "</span>";
        }
        for (var b = 0; b < offset; b += 1) {
            html += '<span class="cal-day is-blank"></span>';
        }
        for (var day = 1; day <= daysInMonth; day += 1) {
            var cls = "cal-day";
            if (year === today.getFullYear() && month === today.getMonth() && day === today.getDate()) {
                cls += " is-today";
            }
            if (this.selected && year === this.selected.getFullYear() &&
                month === this.selected.getMonth() && day === this.selected.getDate()) {
                cls += " is-sel";
            }
            html += '<button class="' + cls + '" type="button" data-day="' + day + '">' + day + "</button>";
        }
        html += "</div>";

        // 时间微调
        var hour = this.selected ? this.selected.getHours() : 9;
        var minute = this.selected ? this.selected.getMinutes() : 0;
        html += '<div class="time-stepper">';
        html += '<span class="form-hint">时间</span>';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-step="h-1">−</button>';
        html += '<input class="field" type="text" data-time="hour" value="' + pad(hour) + '">';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-step="h1">+</button>';
        html += '<span class="form-hint">:</span>';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-step="m-5">−</button>';
        html += '<input class="field" type="text" data-time="minute" value="' + pad(minute) + '">';
        html += '<button class="btn btn-sm btn-ghost" type="button" data-step="m5">+</button>';
        html += "</div>";

        this.pop.innerHTML = html;
        this._bindPopEvents();
    };

    TimePicker.prototype._bindPopEvents = function () {
        var self = this;
        var navs = this.pop.querySelectorAll("[data-nav]");
        for (var i = 0; i < navs.length; i += 1) {
            navs[i].addEventListener("click", function (e) {
                e.preventDefault();
                var delta = parseInt(this.getAttribute("data-nav"), 10);
                self.viewMonth = new Date(self.viewMonth.getFullYear(), self.viewMonth.getMonth() + delta, 1);
                self.renderCalendar();
            });
        }

        var days = this.pop.querySelectorAll("[data-day]");
        for (var j = 0; j < days.length; j += 1) {
            days[j].addEventListener("click", function (e) {
                e.preventDefault();
                var day = parseInt(this.getAttribute("data-day"), 10);
                self._pickDay(day);
            });
        }

        var steps = this.pop.querySelectorAll("[data-step]");
        for (var k = 0; k < steps.length; k += 1) {
            steps[k].addEventListener("click", function (e) {
                e.preventDefault();
                var step = this.getAttribute("data-step");
                self._step(step);
            });
        }

        var hourInput = this.pop.querySelector('[data-time="hour"]');
        var minuteInput = this.pop.querySelector('[data-time="minute"]');
        if (hourInput) {
            hourInput.addEventListener("change", function () {
                self._setTimePart("hour", this.value);
            });
        }
        if (minuteInput) {
            minuteInput.addEventListener("change", function () {
                self._setTimePart("minute", this.value);
            });
        }
    };

    TimePicker.prototype._pickDay = function (day) {
        var year = this.viewMonth.getFullYear();
        var month = this.viewMonth.getMonth();
        var hour = this.selected ? this.selected.getHours() : 9;
        var minute = this.selected ? this.selected.getMinutes() : 0;
        this.selected = new Date(year, month, day, hour, minute, 0, 0);
        this._sync();
        // 选完日期后同步刷新时间微调区域
        this.renderCalendar();
    };

    TimePicker.prototype._step = function (step) {
        var parsed = parse((this.input.value || "").trim());
        var base = parsed ? new Date(parsed.getTime()) : new Date();
        if (!parsed) {
            base.setSeconds(0, 0);
        }
        var type = step.charAt(0);
        var amount = parseInt(step.slice(1), 10);
        if (type === "h") {
            base.setHours(base.getHours() + amount);
        } else if (type === "m") {
            base.setMinutes(base.getMinutes() + amount);
        }
        this.selected = base;
        this.viewMonth = new Date(base.getFullYear(), base.getMonth(), 1);
        this._sync();
        this.renderCalendar();
    };

    TimePicker.prototype._setTimePart = function (part, raw) {
        var value = parseInt(raw, 10);
        if (isNaN(value)) {
            return;
        }
        var parsed = parse((this.input.value || "").trim());
        var base = parsed ? new Date(parsed.getTime()) : new Date();
        if (part === "hour") {
            value = Math.max(0, Math.min(23, value));
            base.setHours(value);
        } else {
            value = Math.max(0, Math.min(59, value));
            base.setMinutes(value);
        }
        base.setSeconds(0, 0);
        this.selected = base;
        this._sync();
    };

    TimePicker.prototype._sync = function () {
        var text = format(this.selected);
        this.input.value = text;
        this._clearError();
        this._emitChange(text);
    };

    /* ------------------------------------------------------------------
       工厂
       ------------------------------------------------------------------ */

    window.HCNoteTimePicker = {
        create: function (root, options) {
            return new TimePicker(root, options);
        },
        format: format,
        parse: parse,
        isValid: isValid,
        presets: PRESETS,
        addDays: addDays,
        startOfDay: startOfDay,
        endOfDay: endOfDay
    };
})();
