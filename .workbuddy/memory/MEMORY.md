# HC-Note 项目长期记忆

## 项目定位

Windows 桌面待办事项客户端，Minecraft Ore UI 风格，支持精确到分钟的起止区间
定时提醒、系统托盘常驻、Windows 原生 Toast 通知。

- 仓库：`https://github.com/HuanChen19/HC-Note`（账号 `HuanChen19`）
- 本地：`E:\1My_Files\.Project\HC-Note`
- 作者署名：幻尘

## 架构约定

- **后端**：Python 3.10+，`src/backend/` 下 5 个模块
  - `app.py` 主入口 + `Api` JS 桥接类 + `Controller` 控制器
  - `storage.py` 数据层（所有写操作走 `_atomic_write`）
  - `scheduler.py` 调度线程、`notifier.py` 通知、`tray.py` 托盘
- **前端**：`src/ui/`，原生 JS（无框架、无构建步骤），三 CSS + 三 JS
- **容器**：PyWebView 6.x + 系统 Edge WebView2（**绝不内置 Chromium**）
- **数据**：`data/tasks.json`，schema 版本 `"1.0"`

## 硬性约束

1. **路径解析**：`resource_root()` 从 `src/backend/app.py` 上溯**三级**到项目根。
   打包后静态资源在 `sys._MEIPASS`，可写数据在 exe 同级 `data/`。
2. **视觉方案**：纯 CSS 手绘 Ore UI，不引入外部贴图。
   立体边框用分层 `box-shadow`（外凸=左上亮/右下暗，内凹=反向）。
3. **前端刷新钩子**：后端通过 `window.HCNoteRefresh()` 主动触发前端重载。
4. **接口对齐**：前端 `callApi("方法名")` 必须与 `Api` 类方法一一对应，
   改接口时两边同步改。用 `.build/startup_check.py` 可自动校验对齐情况。
5. **测试沙箱唯一性**：`selftest.py` 的沙箱目录名带时间戳 + pid，不可复用固定目录。

## 开发环境备忘（本机特有）

- 项目 venv：`.build/venv`（Python 3.13.12 受控版创建）
- 已装：pywebview 6.2.1 / windows-toasts 1.3.1 / pystray 0.19.5 / Pillow 12.3.0 / pyinstaller
- 装包时 `TEMP`/`TMP` 必须指到同盘（`E:\1My_Files\.Project\HC-Note\.build\tmp`），
  否则跨盘 move 会失败；且**不要升级 pip**
- 网络不稳，pip 需 `--retries 8 --timeout 60`；git push 需重试
- **sandbox bash 缺 coreutils**（无 ls/tail/mkdir/head/dirname），
  文件操作走 PowerShell 或 Python，仅 `cd`/`echo`/`for` 内联命令可用

## 验证入口

```bash
# 数据层与调度逻辑（51 项断言）
.build/venv/Scripts/python.exe selftest.py

# 启动链路与接口对齐（20 项断言）
.build/venv/Scripts/python.exe .build/startup_check.py

# 打包
build_exe.bat    # 或手动指定 --distpath 为绝对路径
```

## 待办 / 后续方向

- 用户手动验证 Toast 按钮点击与托盘菜单交互（沙箱无法测 GUI）
- 如需内置像素字体，放到 `assets/fonts/` 并在 `themes.css` 的
  `--font-pixel` 变量处声明 `@font-face`，全局自动生效
- 音效目前用 `winsound` 系统别名；若改用 `.ogg` 需引入解码库
