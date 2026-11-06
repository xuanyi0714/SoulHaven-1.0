"""Terminal client for SoulHaven's local HTTP API."""

import argparse
import http.client
import json
import sys
from urllib.parse import quote, urlencode


class ApiError(Exception):
    def __init__(self, kind, message, path, status=None):
        super().__init__(message)
        self.details = {"kind": kind, "message": message, "path": path}
        if status is not None:
            self.details["status"] = status


def request_json(port, timeout, path, payload=None):
    method = "GET" if payload is None else "POST"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"

    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(method, path, body, headers)
        with connection.getresponse() as response:
            status = response.status
            raw = response.read()
    except TimeoutError as exc:
        raise ApiError("timeout", "等待本地服务响应超时", path) from exc
    except (OSError, http.client.HTTPException) as exc:
        raise ApiError("connection", f"无法完成请求，请检查灵栖是否在端口 {port} 运行", path) from exc
    finally:
        connection.close()

    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    if not 200 <= status < 300:
        message = f"灵栖请求失败（HTTP {status}）"
        if 400 <= status < 500 and isinstance(data, dict) and isinstance(data.get("error"), str):
            message = data["error"]
        raise ApiError("http", message, path, status)
    if not isinstance(data, dict):
        raise ApiError("response", "服务未返回 JSON 对象", path, status)
    return data


def smoke_test(request):
    """Verify core read endpoints and return counts without printing private data."""
    checks = []
    for path, key in (("/api/characters", "characters"), ("/api/worlds", "worlds")):
        items = request(path).get(key)
        if not isinstance(items, list):
            raise ApiError("response", f"响应缺少列表字段 {key}", path)
        checks.append({"path": path, "count": len(items)})
    path = "/api/worlds/reality"
    if request(path).get("id") != "reality":
        raise ApiError("response", "默认世界详情的标识有误", path)
    checks.append({"path": path, "id": "reality"})
    return {"checks": checks}


def run_command(args, request):
    if args.command == "smoke":
        return smoke_test(request)
    if args.command in ("characters", "worlds"):
        return request(f"/api/{args.command}")
    if args.command == "world":
        return request("/api/worlds/" + quote(args.world_id, safe=""))

    character = "/api/characters/" + quote(args.english_name, safe="")
    if args.command == "character":
        return request(character)
    if args.command == "state":
        return request(character + "/state")
    if args.command == "history":
        query = {"limit": args.limit}
        if args.before is not None:
            query["before"] = args.before
        return request(character + "/messages?" + urlencode(query))

    options = {"recognition_time": args.recognition_time, "deep_thinking": args.deep_thinking}
    if args.command == "continue":
        return request(character + "/continue", options)
    return request("/api/chat", {**options, "english_name": args.english_name, "message": args.message})


def build_parser():
    parser = argparse.ArgumentParser(description="在终端调用本机灵栖。成功返回 JSON，运行错误写入 stderr。")
    parser.add_argument("--port", type=int, default=5000, help="本机 HTTP 端口（默认 5000）")
    parser.add_argument("--timeout", type=int, default=120, help="单次连接或读取超时秒数（默认 120）")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("smoke", help="只读检查角色列表、世界列表与默认世界详情")
    commands.add_parser("characters", help="列出角色")
    commands.add_parser("worlds", help="列出世界设定")
    world = commands.add_parser("world", help="读取世界详情")
    world.add_argument("world_id", help="世界标识，例如 reality")

    for name, help_text in (
        ("character", "读取角色档案"),
        ("state", "读取角色外在状态"),
        ("history", "读取聊天历史"),
        ("chat", "发送一轮对话并归档"),
        ("continue", "让角色续说并归档"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("english_name", help="角色英文名，取自 characters 输出")
        if name == "history":
            command.add_argument("--limit", type=int, default=20, help="消息条数（1–100，默认 20）")
            command.add_argument("--before", type=int, help="上一页返回的 next_before")
        if name == "chat":
            command.add_argument("message", help="用户消息，用引号保留空格")
        if name in ("chat", "continue"):
            command.add_argument("--recognition-time", action=argparse.BooleanOptionalAction, default=True)
            command.add_argument("--deep-thinking", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port 必须在 1–65535 之间")
    if not 1 <= args.timeout <= 3600:
        parser.error("--timeout 必须在 1–3600 秒之间")

    def request(path, payload=None):
        return request_json(args.port, args.timeout, path, payload)

    try:
        result = run_command(args, request)
    except ApiError as exc:
        print(json.dumps({"ok": False, "error": exc.details}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "data": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
