# desktop-cli

Windows 后台桌面自动化 CLI，供 AI Agent 通过 Shell 调用。**不抢焦点**，适合人机协同。

API 风格对齐 [agent-browser](https://github.com/vercel-labs/agent-browser)：默认**纯文本 snapshot**、`@eN` ref、短命令循环。

## 核心循环

```powershell
desktop-cli open --title "Notepad"   # 绑定窗口 + snapshot
desktop-cli click "@e3"              # 后台点击
desktop-cli wait "新建"              # 等待 UI 就绪
desktop-cli fill "@e2" "hello"       # 清空并输入
desktop-cli snapshot               # UI 变化后重新 snapshot
desktop-cli health                 # 检测窗口是否卡顿/未响应
```

需要 JSON 时加 `--json`（全局选项，放在子命令前）；完整 JSON 加 `--json --full`。

```powershell
desktop-cli --json info
desktop-cli --json --full open --title "Notepad"
```

## 默认文本输出（省 token）

**windows**

```
1. *hello - Notepad (526334)
2. cli.py - Cursor (131696)
```

**open / snapshot**

```
窗口: *hello - Notepad
句柄: 526334

@e1 [Doc] "文本编辑器"
@e2 [Menu] "文件" id=File
@e3 [Tab] "hello. 已修改。"
```

**click / fill / type**

```
已点击 @e2 "文件"
已填入 @e2 "hello"
```

**health**

```
状态: 正常
窗口: Notepad (526334)
探测耗时: 42ms
未响应: 否
```

**wait**

```
已找到: "新建" [Menu] "新建" (1.2s, 3次)
```

ref 支持 `@e3`、`e3` 或 `3`。UI 变化后 ref 会失效，需重新 `snapshot`。

## Agent 命令

| 命令 | 说明 |
|------|------|
| `windows` | 列出窗口（可选） |
| `open` | 绑定 + snapshot（不抢焦点） |
| `snapshot` | 重新 snapshot |
| `click @eN` | 后台点击 |
| `fill @eN "text"` | 清空并输入 |
| `type "@eN" "text"` | 追加输入 |
| `wait "文本"` | 等待界面出现文本（超时退出码 2） |
| `wait --ref @eN` | 等待 ref 可解析 |
| `health` | 检测窗口未响应/卡顿 |
| `context` | 当前绑定与 refs |

兼容别名（隐藏）：`attach` = `open`，`refresh` = `snapshot`。

无需 `session acquire`、无需 `window focus`。Daemon 与 lease 自动处理。

## 典型流程

```powershell
# 绑定 Notepad 并获取 refs（Cursor 保持在前台）
desktop-cli open --title "Notepad"

# 点击菜单后等待展开，再快照
desktop-cli click "@e4"
desktop-cli wait "新建" --timeout 15
desktop-cli snapshot
```

## 架构

```
Agent → desktop-cli → daemon（常驻，隐式启动）
                        ├─ 自动 lease
                        ├─ open = bind + snapshot
                        └─ 后台 UIA 操作（不 SetForegroundWindow）
```

## 要求

- Windows Server 2012 R2 / Windows 8.1+
- 交互式用户会话（RDP 或控制台登录）

## 安装

```powershell
pip install -e .
```

## 开发与 CI

```powershell
pip install -e ".[dev]"
pytest -v
python -m build
```

GitHub Actions（`.github/workflows/ci.yml`）在 Windows 上运行：

- **test**：Python 3.8 / 3.11 / 3.12 单元测试 + CLI 冒烟
- **build**：构建 sdist / wheel 并上传 artifact

## 开源协议

本项目采用 [MIT License](LICENSE)。

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 未找到 |
| 2 | 超时 |
| 3 | 会话错误 |
| 4 | 其他错误 |
| 5 | lease 冲突（其他 Agent 占用） |

## 运维

```powershell
desktop-cli info           # 会话诊断
desktop-cli daemon status  # daemon 状态
desktop-cli daemon stop    # 停止 daemon（升级后建议先 stop 再操作）
```

## 环境变量

- `DESKTOP_CLI_AGENT_ID` — Agent 标识（默认 `default`）

## 打包

```powershell
pip install -e ".[dev]"
pyinstaller --onefile --name desktop-cli src/desktop_cli/__main__.py
pyinstaller --onefile --name desktop-daemon src/desktop_cli/daemon/__main__.py
```
