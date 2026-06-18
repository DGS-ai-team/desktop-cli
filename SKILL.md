# Desktop CLI Skill

Windows 后台桌面自动化，供 AI Agent 通过 Shell 调用。**不抢焦点**，适合人机协同。

## 核心循环

```powershell
desktop-cli open --title "Notepad"   # 绑定 + 快照
desktop-cli click "@e3"              # 后台点击
desktop-cli wait "新建"              # 等待 UI 就绪（可选）
desktop-cli snapshot               # UI 变化后重新快照
desktop-cli fill "@e2" "hello"     # 清空并输入
```

## 命令

| 命令 | 说明 |
|------|------|
| `windows` | 列出打开的窗口 |
| `open --title "X"` | 绑定窗口 + 快照 |
| `snapshot` | 重新快照 |
| `click "@eN"` | 后台点击 |
| `fill "@eN" "text"` | 清空并输入 |
| `type "@eN" "text"` | 追加输入 |
| `wait "文本"` | 等待界面出现指定文本（子串） |
| `wait --ref @eN` | 等待 ref 可解析 |
| `health` | 检测窗口是否未响应/卡顿 |
| `context` | 当前绑定与 refs |

ref 来自 `open` / `snapshot` 输出，支持 `@e3`、`e3`、`3`。PowerShell 中 ref 需加引号：`"@e3"`。

## 输出

- **默认**：纯文本（约 200–400 token/快照）
- **`--json`**：紧凑 JSON（全局选项，放在子命令前）
- **`--json --full`**：完整 JSON

```powershell
desktop-cli --json snapshot
desktop-cli --json --full open --title "Notepad"
```

## 应对 UI 卡顿

1. **操作后等待**：`click` 不会自动 snapshot，用 `wait` 代替手写 sleep
2. **检测未响应**：`health` 返回 `状态: 正常/卡顿/未响应`
3. **超时退出码 2**：`wait` 超时表示 UI 未在预期时间内就绪

```powershell
desktop-cli click "@e4"
desktop-cli wait "新建" --timeout 15
desktop-cli snapshot
desktop-cli health
```

## 规则

1. 操作前先 `open` 或 `snapshot`
2. UI 变化后 ref 失效，必须重新 `snapshot`
3. `click` / `fill` / `type` **不会**自动 snapshot
4. 需在交互式用户会话（RDP/控制台）运行，不能 Session 0

## 错误示例

```
错误: 未绑定窗口，请先 open
错误: 等待超时 (10s)：未找到文本 '新建'
```

退出码：0=成功，1=未找到，2=超时，5=lease 冲突。

## 示例会话

```powershell
desktop-cli windows
desktop-cli open --title "Notepad"
desktop-cli click "@e4"
desktop-cli wait "新建" --timeout 10
desktop-cli snapshot
desktop-cli health
desktop-cli context
```
