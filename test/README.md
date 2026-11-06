# 灵栖终端入口

`soulhaven.py` 是给终端用户和能运行命令的 AI Agent 使用的本机客户端，只需要 Python 标准库。它通过 HTTP 调用正在运行的灵栖服务。

在项目根目录启动后端，保持该终端运行。

```powershell
.\backend\.venv\Scripts\python.exe -m backend.app
```

在另一个终端运行只读冒烟检查。

```powershell
.\backend\.venv\Scripts\python.exe .\test\soulhaven.py smoke
```

## 命令

以下命令都接在 `python .\test\soulhaven.py` 后面。`<英文名>` 取自 `characters` 返回的 `english_name`，`<世界ID>` 取自 `worlds` 返回的 `id`。

| 命令 | 用途 |
| --- | --- |
| `smoke` | 只读检查角色列表、世界列表和默认世界详情，输出检查结果与数量 |
| `characters` / `character <英文名>` | 角色列表与档案 |
| `worlds` / `world <世界ID>` | 世界列表与详情 |
| `state <英文名>` | 角色外在状态 |
| `history <英文名> --limit 5` | 最近 5 条消息，按时间顺序返回。加载上一页时加 `--before <next_before>` |
| `chat <英文名> "你好，今天过得怎么样？"` | 发送消息，等待完整回复并走正常归档流程 |
| `continue <英文名>` | 让角色续说并走正常归档流程 |

默认连接 `127.0.0.1:5000`。可在子命令前用 `--port` 指定其他本机端口，或用 `--timeout` 调整连接及读取超时（默认 120 秒）。聊天和续说默认开启时间感知和深度思考，可用 `--no-recognition-time`、`--no-deep-thinking` 关闭。用 `--help` 查看所有命令，或用 `chat --help` 查看聊天参数。

## 给 AI Agent

- 验证服务时先运行 `smoke`，需要进一步定位时再运行 `world`、`character`、`state` 或 `history`。
- 成功时退出码为 `0`，stdout 为一行 UTF-8 JSON `{"ok":true,"data":...}`。运行失败时退出码为 `1`，stderr 为 `{"ok":false,"error":{"kind":...,"message":...,"path":...}}`，HTTP 错误带 `status`。命令行参数用法错误退出码为 `2`。
- `chat` 和 `continue` 会调用角色配置的模型，并可能更新真实历史和状态。自动回归使用专用测试角色。请求超时后先读历史核对结果，再决定是否重发。

可以直接给 Agent 这样的任务：「在项目根目录运行 `test/soulhaven.py smoke`，根据退出码和 JSON 报告结果。」
