# HC-Note

一个 Minecraft Ore UI 风格的 Windows 桌面待办事项客户端，支持精确到分钟的
起止区间定时提醒、系统托盘常驻与 Windows 原生 Toast 通知。

## 特性

- **待办生命周期管理**：标题、多行描述、四级优先级（MC 羊毛色标识）、自定义分组，
  支持完成划线动画、撤销完成、归档过滤。
- **起止区间定时提醒**：为任务设置 `YYYY-MM-DD HH:mm` 的开始与结束时间，
  在开始节点、结束前预警、结束超时三个节点推送通知，并带快捷预设区间。
- **休眠唤醒补偿**：电脑休眠唤醒后自动校准状态并立即补推错过的提醒节点。
- **Ore UI 视觉体系**：纯 CSS 手绘的基岩颗粒质感、立体浮雕边框、像素风按钮与
  复选框，不依赖任何外部贴图。
- **亮色 / 暗色 / 跟随系统**：三档主题，跟随系统模式下实时响应 Windows 深浅色切换。
- **系统托盘常驻**：关闭窗口默认最小化到托盘，右键菜单可直接查看即将到期任务。
- **原生 Toast 交互**：通知上附带「标记完成」「推迟 10 分钟」「查看」按钮。

## 环境要求

- Windows 10 / Windows 11
- **Microsoft Edge WebView2 Runtime**（Win10/11 通常已预装；
  如缺失请从 [微软官网](https://developer.microsoft.com/microsoft-edge/webview2/) 下载 Evergreen 安装包）
- Python 3.10 或更高版本（仅源码运行时需要）

## 快速开始

### 方式一：直接运行打包好的程序

将 `HC-Note.exe` 放到任意目录，双击运行。程序会在同级目录自动创建 `data`
文件夹用于存放任务数据，整个目录可便携拷贝。

### 方式二：源码运行

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 启动程序，双击 `启动(源码运行).bat`，或执行：

```bash
python src/backend/app.py
```

## 目录结构

```text
HC-Note/
├── assets/                     # 静态资源
│   ├── fonts/                  # 像素字体（可选）
│   ├── icons/                  # 应用图标、托盘图标
│   ├── images/                 # 其他图像资源
│   └── sounds/                 # 音效资源
├── src/
│   ├── backend/                # Python 后端
│   │   ├── app.py              # 主入口，集成 PyWebView 与 API 桥接
│   │   ├── storage.py          # 数据读写（原子写入保护）
│   │   ├── scheduler.py        # 后台高精度定时轮询器
│   │   ├── notifier.py         # Windows 原生 Toast 通知与声音
│   │   └── tray.py             # 系统托盘与后台常驻管理
│   └── ui/                     # 前端展示层（Ore UI）
│       ├── index.html          # 主界面
│       ├── css/
│       │   ├── ore_ui.css      # Ore UI 核心控件样式
│       │   ├── themes.css      # 亮色 / 暗色 CSS 变量定义
│       │   └── layout.css      # 响应式布局与滚动条
│       └── js/
│           ├── app.js          # 页面业务逻辑与状态绑定
│           ├── timepicker.js   # MC 风格精确起止时间选择组件
│           └── theme.js        # 主题检测与切换逻辑
├── data/                       # 运行时数据（自动生成）
│   └── tasks.json              # 任务与设置持久化文件
├── build_logo.py               # LOGO 去背景与图标生成脚本
├── build_exe.bat               # 一键打包 PyInstaller 脚本
├── HC-Note.spec                # PyInstaller 打包规格
├── 启动(源码运行).bat          # 快捷启动脚本
├── requirements.txt            # Python 依赖清单
└── README.md                   # 本文件
```

## 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl` + `N` | 新增待办 |
| `Esc` | 关闭当前弹窗 |
| `Enter` | 快速新增框中直接添加；弹窗内保存 |

## 数据存储

任务数据以 JSON 格式保存在 `data/tasks.json`，写入采用「先写临时文件 → 原子替换」
的策略，并保留一份 `tasks.backup.json` 备份，避免断电或异常退出损坏数据。

数据模型示例：

```json
{
  "version": "1.0",
  "settings": {
    "theme": "system",
    "sound_enabled": true,
    "notify_before_minutes": 15
  },
  "tasks": [
    {
      "id": "task_20260919_001",
      "title": "完成 Addon 模型材质烘焙",
      "description": "修复几何体重叠面的 UV 贴图拉伸",
      "priority": "high",
      "status": "in_progress",
      "start_time": "2026-09-20 09:00",
      "end_time": "2026-09-20 18:00",
      "created_at": "2026-09-19 21:00",
      "completed_at": null,
      "reminders_sent": {
        "start": false,
        "pre_end": false,
        "end": false
      }
    }
  ]
}
```

## 打包为 EXE

双击 `build_exe.bat`，脚本会自动安装 PyInstaller 并依据 `HC-Note.spec` 打包，
产物位于 `dist/HC-Note.exe`。

## 常见问题

**界面白屏或无法启动**

确认已安装 Edge WebView2 Runtime。在 PowerShell 中执行以下命令可检查版本：

```powershell
Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
```

**收不到 Toast 通知**

检查 Windows 设置 → 系统 → 通知，确认「HC-Note」的通知权限已开启，
同时确认未处于「专注助手」模式。程序在原生 Toast 不可用时会自动降级为
托盘气泡提示。

**关闭窗口后程序消失**

这是预期行为：关闭窗口默认最小化到系统托盘，定时提醒仍在后台运行。
可在设置中关闭「关闭窗口时最小化到系统托盘」，或在托盘右键菜单中退出。

## 许可

本项目基于 MIT 许可开源，详见 [LICENSE](LICENSE)。
