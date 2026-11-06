"""DeepSeek 及自定义兼容服务的网页搜索和抓取。"""

import json
import re
from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from typing import Any
from urllib.parse import SplitResult, urlsplit


_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_TRANSPORT_HEADERS = {"host", "content-length", "transfer-encoding", "connection", "upgrade"}
_MAX_CUSTOM_RESPONSE = 2 * 1024 * 1024


@dataclass(frozen=True)
class CustomSearchConfig:
    base_url: SplitResult
    headers: dict[str, str] = field(repr=False)

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "CustomSearchConfig":
        url = settings.get("base_url")
        try:
            if not isinstance(url, str) or not url or len(url) > 2048 or any(
                not 33 <= ord(char) <= 126 or char in "\\?#" for char in url
            ):
                raise ValueError
            parts = urlsplit(url)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username is not None:
                raise ValueError
            if parts.port == 0:
                raise ValueError
        except ValueError:
            raise ValueError("自定义搜索 Base URL 必须是有效的 HTTP(S) 接口前缀，且不含账号、查询参数或片段") from None

        api_key = settings.get("api_key")
        if not isinstance(api_key, str) or not api_key or any(not 33 <= ord(char) <= 126 for char in api_key):
            raise ValueError("自定义搜索 API Key 格式无效")
        raw_header = settings.get("header") or ""
        if not raw_header:
            return cls(parts, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        try:
            headers = json.loads(raw_header)
        except (TypeError, ValueError, RecursionError):
            headers = None
        if not isinstance(headers, dict):
            raise ValueError("自定义请求头必须是 JSON 对象")
        resolved = {}
        names = set()
        for key, value in headers.items():
            name = key.lower()
            if not _HEADER_NAME.fullmatch(key) or name in _TRANSPORT_HEADERS or name in names:
                raise ValueError("自定义请求头包含无效、重复或保留的名称")
            if not isinstance(value, str):
                raise ValueError("自定义请求头的值必须是字符串")
            value = value.replace("{api_key}", api_key)
            if any(not 32 <= ord(char) <= 126 for char in value):
                raise ValueError("自定义请求头的值必须是可打印 ASCII 字符")
            names.add(name)
            resolved[key] = value
        return cls(parts, resolved)


def valid_query(query: Any) -> bool:
    return isinstance(query, str) and 1 <= len(query.strip()) <= 128


class WebSearchTool:
    name = "web_search"

    @staticmethod
    def available(character: Any) -> bool:
        return bool(getattr(character, "custom_search", None) or getattr(character, "search_api_key", ""))

    @staticmethod
    def _post(api_key: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not api_key or any(not 33 <= ord(char) <= 126 for char in api_key):
            raise ValueError("DeepSeek 搜索 API Key 格式无效")
        # 固定官方主机，不跟随重定向，密钥只发送给 DeepSeek。
        connection = HTTPSConnection("api.deepseek.com", timeout=60)
        try:
            connection.request(
                "POST", f"/v1/tools/{action}",
                body=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"DeepSeek 接口返回 HTTP {response.status}")
            result = json.loads(response.read())
            if isinstance(result, dict):
                return result
        except (OSError, HTTPException, UnicodeError, json.JSONDecodeError):
            raise ValueError("DeepSeek 接口暂时不可用或返回了无效数据") from None
        finally:
            connection.close()
        raise ValueError("DeepSeek 接口返回了无效数据")

    def _request(self, character: Any, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        config = getattr(character, "custom_search", None)
        if config is None:
            return self._post(character.search_api_key, action, payload)
        parts = config.base_url
        connection_type = HTTPSConnection if parts.scheme == "https" else HTTPConnection
        connection = connection_type(parts.hostname, parts.port, timeout=60)
        try:
            connection.request("POST", f"{parts.path.rstrip('/')}/{action}",
                               body=json.dumps(payload).encode("utf-8"), headers=config.headers)
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError(f"自定义搜索接口返回 HTTP {response.status}")
            data = response.read(_MAX_CUSTOM_RESPONSE + 1)
            if len(data) > _MAX_CUSTOM_RESPONSE:
                raise ValueError("自定义搜索接口响应过大")
            result = json.loads(data)
        except (OSError, HTTPException, UnicodeError, json.JSONDecodeError, RecursionError):
            raise ValueError("自定义搜索接口暂时不可用或返回了无效数据") from None
        finally:
            connection.close()
        if not isinstance(result, dict):
            raise ValueError("自定义搜索接口返回了无效数据")
        return result

    def call(self, character: Any, query: str) -> list[dict[str, Any]]:
        response = self._request(character, "search", {"query": query, "count": 10})
        results = response.get("results")
        if not isinstance(results, list):
            raise ValueError("搜索接口未返回有效的结果列表")
        candidates = []
        seen_urls = set()
        for number, result in enumerate(results[:10], start=1):
            if not isinstance(result, dict):
                continue
            url = result.get("url")
            if not isinstance(url, str) or len(url) > 8192 or url in seen_urls:
                continue
            try:
                parts = urlsplit(url)
                if parts.scheme not in {"http", "https"} or not parts.hostname or "@" in parts.netloc:
                    continue
            except ValueError:
                continue
            seen_urls.add(url)
            candidates.append({
                "number": number,
                "title": str(result.get("title") or "")[:300],
                "url": url,
                "snippet": str(result.get("summary") or result.get("snippet") or "")[:600],
            })
        return candidates

    def fetch(self, character: Any, candidate: dict[str, Any]) -> dict[str, Any]:
        page = self._request(character, "fetch", {"url": candidate["url"]})
        content = page.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("抓取接口未返回可用的网页正文")
        return {
            "number": candidate["number"],
            "title": str(page.get("title") or candidate["title"])[:300],
            "url": candidate["url"],
            "content": content[:8000] + ("\n[正文已截断]" if len(content) > 8000 else ""),
        }
