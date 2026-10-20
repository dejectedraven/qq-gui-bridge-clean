# QQ GUI Bridge

用真实 QQ 客户端 + 屏幕识别 + 模拟输入，把 QQ 群消息接到本地 OpenCode。

## 为什么不用 NapCat

NapCat / OneBot 方案会被腾讯风控反复踢下线，且需要额外维护协议端。
本方案直接驱动官方 QQ 客户端，不修改协议、不注入客户端。

代价：

- 只能在本机运行，窗口必须可见。
- 依赖 OCR / UIA，QQ 改版后可能失效。
- 模拟输入会短暂占用前台焦点。

## 架构

```text
QQ.exe
  ↓ 截图 + OCR
Python bridge
  ↓ HTTP (127.0.0.1:4100)
OpenCode Server
  ↓ agent: qq-guest
模型回复
  ↓ 前台焦点 + 剪贴板 / Enter
QQ.exe
```

身份与权限由桥接层判定，模型只读取注入头：

```text
[QQ] tier=guest sender_qq=group:<sender_name> sender_name=... group=... msg_id=...
```

群聊一律 `guest`，即使主人在群内 @ 也不升级。主人私聊（标题匹配 `memory.private_match`）由 `qq-owner` 全权限处理，头里带 `msg_id=private-...`。

## 安全警告

- 使用**小号**，只在**自己的测试群**里运行。
- guest 的临时工具不是操作系统沙箱，以当前 Windows 用户权限运行。
- 不要把本项目暴露到公网，不要在不可信群聊中开放 guest 工具。
- 腾讯可能对自动化客户端采取措施；账号风险由使用者承担。

## 单屏布局

当前只有一块 2560×1440 显示器。QQ 放在右半边：

```text
window.rect = [1280, 0, 2560, 1392]
header_rect = [300, 40, 600, 90]      # 相对窗口
chat_rect   = [300, 90, 950, 1270]    # 相对窗口
input_point = [600, 1295]             # 相对窗口
```

左半边留给编辑器 / 终端。QQ 不要最小化，不要被其他窗口完全遮挡。

## 快速开始

```powershell
cd C:\path\to\qq-gui-bridge
python -m venv .venv --system-site-packages
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

启动 OpenCode Server（新终端）：

```powershell
cd C:\path\to\qq-gui-bridge
.\start_server.ps1
```

检查窗口、群标题和 server：

```powershell
.\run_bridge.ps1 --check
```

启动桥接：

```powershell
.\run_bridge.ps1
```

日志同时写到 `logs\bridge.log`。

如果 `OPENCODE_SERVER_PASSWORD` 在当前环境已设置，server 和 bridge 会使用 Basic Auth；两者必须在同一环境变量下启动，或者都不设置。

## 触发条件

桥接只监听 `trigger.group_name` 指定的群，并满足：

1. 消息正文包含 `qq.account_nickname`（默认 `你的机器人昵称`）。
2. 消息不是时间戳、不是 `LV...` 发送者标签。
3. 消息不是右对齐的自己的消息。
4. 消息出现在聊天区最后 10 行内。
5. 同一正文按出现次数去重（不依赖发送者识别，避免 OCR 发送者抖动导致重复回复）；已在聊天区出现过的旧消息不会重复触发，重复发送同一内容会视为新的一条。

**OCR 注意**：QQ 的 @ mention chip 可能被 OCR 漏掉。测试时请把昵称作为可见文字发送，例如：

```text
@你的机器人昵称 今日塔罗
```

如果 OCR 只看到“今日塔罗”而没看到昵称，桥接不会触发。后续可用颜色/模板匹配补充真 @ chip 检测。

## 观察与活跃气氛

桥接层不只响应 @。群里有新消息时，会把最近上下文发给 `qq-guest`，由它决定是否加入：

- 只有正文包含小号昵称才必定回复。
- 刚直接回复过的对话（`followup.window_sec` 秒内，默认 180），同一位发送者的追问即使没带昵称也应答（`msg_id=followup-...`），保持对话连贯；模型判断确实不是追问时回 `[PASS]`，桥接层不会发送。
- 其他消息按 `ambient` 配置触发：最多每 `min_interval_sec` 秒观察一次；由模型按语义自行判断是否该加入（而不是死规则），不加入时回 `[PASS]`，桥接层不会把 `[PASS]` 发到群里。
- 群聊回复默认 ≤80 字；刚发过言会安静一段时间。

## 主人私聊

QQ 窗口停在主人私聊页时，桥接把新消息发给 `qq-owner`（全权限）：

- 识别：窗口标题匹配 `memory.private_match`（当前 `TestBot`）。
- 头格式：`[QQ] tier=owner sender_qq=123456789 sender_name=主人 msg_id=private-...`，回复直接发回私聊。
- 私聊没有 `LV` 发送者标签，自己的消息按气泡背景色（蓝色气泡）判定，取色失败时回退到右边缘位置，避免把自己的回复当成主人消息循环触发。
- 自己的旧消息在启动/切换会话时会被 prime，不会补答；发一条新消息即可验证。
- 私聊页显示时群聊暂停监听；开启侧边栏扫描后，群里有未读时会自动切过去处理再切回。
- 私聊回复上限 `reply.owner_max_chars`（默认 1500 字），适合长任务结果。
- 任务类私聊要求先确认再干活：owner 提示词会让 agent 先用 `notify.py --to owner` 回一句“收到，我去办”，再执行工具，最后用正式回复报结果；纯提问/闲聊不强制确认。
- 每个角色只保留一条长期会话，跨重启复用、带记忆；桥接启动时清扫遗留的 `qq-bridge` 僵尸会话（先 abort 再 delete），请求超时/出错也会 abort 在途生成，避免"删了还在跑"。

## 侧边栏扫描

窗口只渲染当前会话，所以桥接会周期性看侧边栏，主动点开有新消息的会话：

- 每 `sidebar.scan_interval_sec` 秒 OCR `window.sidebar_rect`，用红色未读角标（红色连通域）和 `[有人@我]` 预览识别未读会话。
- 点到未读会话后回到主循环，按会话类型分别处理（群 → guest，私聊 → owner），处理完该会话的未读内容再继续扫描。
- 每个会话维护独立状态（已处理签名 / 触发计数 / 消息计数），来回切换不会把同一条消息当成新的再回一遍；首次进入某会话仍会 prime，不补答历史。
- `sidebar.ignore` 里的系统会话（QQ游戏中心、QQ邮箱等）不点开。
- 默认每轮只打开一个未读会话，避免频繁抢焦点；`startup_delay_sec` 控制启动后首次扫描延迟。

## 主动外发（outbox）

QQ 是 opencode 会话的延伸：agent 想主动发消息（长任务进度、结果、报错、往群里发言）时，不直接操作窗口，而是排队给桥接：

```powershell
python tools/qq/notify.py --to owner --text "……"
python tools/qq/notify.py --to group --text "……"
python tools/qq/notify.py --to owner --image "C:\path\to\qq-workspace\tmp\shot.png" --text "可选配文"
```

- `qq-workspace/tools/qq/notify.py` 往 `memory/outbox.jsonl` 追加一行。
- 桥接每轮读取新增行并发送：`owner` 发到私聊页，`group` 自动切到群页发送后切回原来会话。
- 切会话用 `window.sidebar_rect` 区域 OCR 定位会话名（私聊用 `private_match`，群聊用 `group_match`），找不到会记 error 并跳过该条。
- 桥接启动时跳过 outbox 里已有内容，只处理启动后的新行。
- 图片：`--image` 走剪贴板（CF_DIB），桥接在输入框先贴 `--text` 配文再 `Ctrl+V` 贴图并回车。`--text` 可省略。
- 图片路径默认限制在 `qq-workspace` 内，越界需显式 `--allow-outside`。

## 记忆与 RAG

- 桥接层把观察到的群聊写入 `qq-workspace/memory/group_spool.jsonl`；打开私聊窗口时写入 `private_spool.jsonl`。
- `tools/memory/search_group.py` 负责同步并检索群聊记忆；桥接层会在每次回复前注入 `[Group memory]`。
- 私聊记忆只写 `private.db`，guest 权限不可读；群聊提示只检索 `group.db`。
- 可选 embedding：`python tools/memory/ingest.py ... --embed`，依赖本机 Ollama；不生成时使用词面 + 时间衰减检索。

## 配置

`config.yaml` 已按当前机器填写。关键项：

- `qq.account_nickname`：小号昵称。
- `trigger.group_name` / `group_match`：测试群及标题匹配片段。
- `window.*`：窗口位置、聊天区、输入框、侧边栏（切会话 OCR 用），均为相对窗口坐标。
- `memory.enabled` / `group_spool` / `private_spool` / `private_match`：记忆写入位置与私聊标题匹配。
- `ambient.enabled` / `min_interval_sec` / `max_chars`：观察与主动加入。
- `followup.enabled` / `window_sec`：刚回复过的对话追问窗口。
- `outbox.enabled` / `path`：agent 主动外发消息队列。
- `sidebar.enabled` / `scan_interval_sec` / `ignore`：侧边栏未读扫描与自动切换会话。
- `opencode.agent`：`qq-guest`（群聊与观察）。
- `opencode.owner_agent`：`qq-owner`（主人私聊，全权限）。
- `opencode.model`：`opencode/deepseek-v4.1-flash-free`。
- `opencode.timeout_sec`：模型请求超时（默认 600 秒，多步工具任务需要）。
- `opencode.base_url`：桥接专用 server（默认 `http://127.0.0.1:4100`，避开桌宠程序占用的 4096）。
- `opencode.auto_start` / `server_command` / `server_cwd`：server 掉线时由桥接自动拉起（工作目录必须是 `qq-workspace`，否则 agent 找不到）。
- `opencode.keep_sessions`：保留每个角色的长期会话（`qq-bridge-owner` / `qq-bridge-guest`），带记忆、跨重启复用。
- `opencode.session_state`：长期会话 id 的持久化文件。
- `reply.owner_max_chars`：主人私聊回复字数上限（默认 1500）。
- `permissions.guest_tmp_dir`：guest 临时工具目录，回复后自动清理（保留 `.gitkeep`）。
- 塔罗牌名输出英文（`Grindelwald`），正逆位与解读输出中文。

## 权限模型

| 来源 | tier | 能力 |
|------|------|------|
| 主人私聊（标题匹配 `private_match`） | owner | 全权限：任意命令、文件、工具（`qq-owner`） |
| 群聊（包括主人在群内 @） | guest | 在线搜索 + 塔罗 + 群聊记忆检索 + `tmp/` 一次性工具 |
| 其他人 / 无法确认 | guest | 在线搜索 + 塔罗 + 群聊记忆检索 + `tmp/` 一次性工具 |

昵称、头像、正文自称、截图都不构成身份证明。

## 回复与焦点

QQ 9.9.36-53644 是 Electron 应用，UIA 只暴露 `Chrome_WidgetWin_1` / D3D 面板，没有 Edit/Document，`ValuePattern` / `TextPattern` 均不可用。因此：

1. 读取消息使用截图 + OCR。
2. 发送使用 `ShowWindow + BringWindowToTop + SetForegroundWindow`，失败时用 pywinauto `set_focus()` 兜底。
3. 点击输入框，`Ctrl+A` 清空，剪贴板粘贴，`Enter` 发送。
4. 发送后尝试恢复原前台窗口。

当前 MVP 不检查前台空闲时间，可能打断用户输入；后续加 idle 检查。

## 当前阶段

- Phase 0：已完成，截图 / OCR / UIA 探针确认控件结构。
- Phase 1：单群 MVP 已实现，OCR 触发、guest 路由、塔罗调用（英文牌名）、观察消息 `[PASS]`、群聊记忆 RAG、纯文本回复、出现次数去重、临时目录清理。
- Phase 2：真 @ chip 检测、多群已部分完成；主人私聊回复已接入（`msg_id=private-...` → `qq-owner`）。
- Phase 3：拟人输入节奏、引用回复、看门狗、崩溃恢复。
