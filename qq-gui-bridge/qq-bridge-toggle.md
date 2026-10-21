# QQ 桥接一键开关 使用说明

## 这是什么

`qq-bridge-toggle` 用来快速开启或关闭整套 QQ 桥接功能：

- **看护进程**（watchdog）：桥接意外退出时自动拉起
- **桥接进程**（bridge）：监听 QQ 窗口、收发消息
- **OpenCode Server**（端口 41873）：桥接调用的模型后端

注意：它只控制桥接本身，不会启动或关闭 QQ 客户端。

## 文件

| 文件 | 用途 |
|------|------|
| `qq-bridge-toggle.bat` | 双击使用：运行中则关闭，已停止则开启 |
| `qq-bridge-toggle.ps1` | 实际逻辑，支持 on / off / status / toggle |

两个文件必须和 `watchdog.ps1`、`run_bridge.ps1` 放在同一目录（项目根目录）。

## 使用方法

### 双击

双击 `qq-bridge-toggle.bat`，窗口会显示当前状态，按任意键关闭。

### 命令行

```powershell
.\qq-bridge-toggle.ps1                   # 切换（开着就关，关着就开）
.\qq-bridge-toggle.ps1 -Action on        # 开启
.\qq-bridge-toggle.ps1 -Action off       # 关闭
.\qq-bridge-toggle.ps1 -Action status    # 只看状态
```

如果 PowerShell 提示禁止运行脚本，用下面这种写法绕过：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\qq-bridge-toggle.ps1 -Action status
```

## 状态说明

```
桥接: 运行中 (PID 32096,35528)     监听 QQ、处理消息的进程
看护: 运行中                       负责自动重启桥接
服务: 运行中 (端口 41873, 健康 正常)  模型后端
```

- **服务未启动也没关系**：桥接检测到 server 不在，会自己拉起来。
- **健康 异常**：server 进程在但还没就绪，等几秒再查；持续异常请看 `logs\bridge.log`。

## 开启时做了什么

1. 检查桥接是否已在运行，已在运行则直接显示状态。
2. 没有看护进程时，后台启动 `watchdog.ps1`。
3. 看护发现桥接不存在，会启动 `run_bridge.ps1`。
4. 桥接连不上 server 时，自动用 `config.yaml` 的 `server_command` 和 `server_cwd` 拉起 server。
5. 脚本最多等 60 秒，直到桥接运行且 server 健康，然后打印状态。

## 关闭时做了什么

1. 先结束看护进程（否则它会在 10 秒内把桥接重新拉起来）。
2. 结束桥接进程。
3. 结束 41873 端口上的 OpenCode Server。

关闭后 QQ 不再自动回复，`logs\` 里的日志保留。重新开启会沿用原来的会话记录。

## 常见问题

**双击后窗口一闪而过？**
用命令行运行 `.\qq-bridge-toggle.bat off`（或 on / status）查看输出。

**开启失败？**
看 `logs\watchdog.log` 和 `logs\bridge.log`。常见原因：QQ 窗口没打开、`config.yaml` 路径不对、虚拟环境缺依赖。

**会不会重复启动多个桥接？**
不会。看护用互斥量保证只跑一个，脚本也会先检查已有进程。

**关闭时正好在回复怎么办？**
正在进行的回复会被中断；重新开启后，最后一条未回复的私聊会被自动补答。

**和手动启动冲突吗？**
不冲突。`run_bridge.ps1` 手动启动的桥接也能被这个脚本关闭；关闭时它会一并清掉看护。
