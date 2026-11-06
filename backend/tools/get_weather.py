"""获取指定城市实时天气的工具。"""

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.chat.outputs import RESPONSE_FORMAT_PARSER
from backend.use_tools.run_tool import (
    TOOL_LIMIT_MESSAGE,
    ToolCallLimitError,
    run_tool,
)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"  # 城市地理编码接口
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"  # 实时天气接口
REQUEST_TIMEOUT = 10  # 天气接口请求超时秒数
MAX_TOOL_FAILURES = 3  # 同一轮工具连续失败的最大重试次数

# Open-Meteo 使用的 WMO 天气代码到中文描述的映射。
WEATHER_CODE_LABELS = {  # WMO 天气代码标签
    0: "晴朗",
    1: "大部晴朗",
    2: "多云",
    3: "阴天",
    45: "有雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "中等毛毛雨",
    55: "大毛毛雨",
    56: "轻度冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "轻度冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中等阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}

# 工具执行过程写入同一条 assistant 消息的模板。
TOOL_ACTIVITY_TEMPLATE = """# 活动
调用了天气工具
# 结果
地区：{city}
天气：{weather}
气温：{temperature}
相对湿度：{humidity}
风速：{wind_speed}
观测时间：{observed_at}
工具调用完成，接下来将继续回答用户上一轮的问题"""

# 工具调用失败时写入同一条 assistant 消息的模板。
TOOL_FAILURE_TEMPLATE = """# 活动
工具调用失败
# 结果
{message}"""

# 模型在工具连续失败后仍然要求调用工具时的角色化兜底回复。
WEATHER_FAILURE_FALLBACK = "我这边暂时查不到天气，你那边现在怎么样？"

TOOL_SUCCESS_MESSAGE = "天气工具调用成功"  # 工具成功日志
TOOL_FAILURE_LOG_TEMPLATE = "[SoulHaven] 天气工具调用失败：{message}"  # 工具失败日志模板

# 模型最终回答追加到同一条 assistant 消息的模板。
FINAL_REPLY_TEMPLATE = """# 最终回复
{content}"""


class GetWeatherTool:
    """查询指定城市当前天气的工具。

    工具先通过 Open-Meteo 的地理编码接口把中文城市名转换成经纬度，再查询
    当前天气。执行过程和结果会写入最后一条 assistant 消息，然后继续请求
    模型，直到模型不再调用工具为止。

    Attributes:
        name: 工具名，必须与 backend.llms.llms_main.AVAILABLE_TOOL_NAMES 中的名称一致。
        description: 工具用途说明，供工具选择逻辑和系统提示词使用。
    """

    name = "get_weather_tool"  # 工具名
    description = "查询中国城市当前的实时天气，包括天气状况、气温、湿度和风速。"

    @staticmethod
    def _read_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
        """请求天气接口并解析 JSON。

        Args:
            url: 接口地址。
            params: 查询参数字典。

        Returns:
            解析后的 JSON 对象。

        Raises:
            RuntimeError: 网络请求失败或接口返回内容不是 JSON 对象。
        """
        query = urlencode(params)
        request = Request(
            f"{url}?{query}",
            headers={"User-Agent": "SoulHaven/1.0"},
        )
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"天气服务请求失败：{exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("天气服务返回了无法解析的数据") from exc
        if not isinstance(data, dict):
            raise RuntimeError("天气服务返回格式错误")
        return data

    def _find_place(self, city: str) -> dict[str, Any]:
        """查找城市对应的地理编码结果。

        优先选择行政中心（PPLC/PPLA 系列）；如果用户只写了“桂林”，
        额外查询“桂林市”，避免匹配到同名的乡镇。

        Args:
            city: 用户输入的城市名。

        Returns:
            地理编码接口返回的城市字典。

        Raises:
            ValueError: 找不到城市或返回格式错误。
        """
        queries = [city]
        if not city.endswith(("市", "县", "区", "盟", "州")):
            queries.append(f"{city}市")

        candidates: list[dict[str, Any]] = []
        for query in queries:
            location_data = self._read_json(
                GEOCODING_URL,
                {
                    "name": query,
                    "count": 10,
                    "language": "zh",
                    "countryCode": "CN",
                },
            )
            results = location_data.get("results")
            if not isinstance(results, list):
                continue
            for result in results:
                if isinstance(result, dict):
                    candidates.append(result)

        if not candidates:
            raise ValueError(f"找不到城市：{city}")

        def place_score(place: dict[str, Any]) -> tuple[int, float]:
            """按行政级别和人口给城市候选排序。"""
            feature_code = str(place.get("feature_code") or "").upper()
            if feature_code.startswith("PPLC"):
                level = 100
            elif feature_code.startswith("PPLA2"):
                level = 80
            elif feature_code.startswith("PPLA3"):
                level = 70
            elif feature_code.startswith("PPLA4"):
                level = 60
            elif feature_code.startswith("PPLA"):
                level = 90
            elif feature_code.startswith("PPL"):
                level = 30
            else:
                level = 10
            try:
                population = float(place.get("population") or 0)
            except (TypeError, ValueError):
                population = 0
            return level, population

        return max(candidates, key=place_score)

    def _fetch_weather(self, city: str) -> dict[str, str]:
        """查询城市经纬度并获取实时天气。

        Args:
            city: 城市名称，例如“桂林”。

        Returns:
            包含地区、天气、气温、湿度、风速和观测时间的展示字典。

        Raises:
            ValueError: 城市为空、找不到城市或天气数据不完整。
            RuntimeError: 天气接口请求或解析失败。
        """
        city = str(city or "").strip()
        if not city:
            raise ValueError("城市不能为空")

        place = self._find_place(city)

        try:
            latitude = place["latitude"]
            longitude = place["longitude"]
        except KeyError as exc:
            raise ValueError(f"城市信息缺少经纬度：{city}") from exc

        forecast_data = self._read_json(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "weather_code,wind_speed_10m"
                ),
                "timezone": "auto",
            },
        )
        current = forecast_data.get("current")
        if not isinstance(current, dict):
            raise ValueError("天气数据缺少 current 字段")

        temperature = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        wind_speed = current.get("wind_speed_10m")
        if temperature is None or humidity is None or wind_speed is None:
            raise ValueError("天气数据不完整")

        try:
            weather_code = int(current.get("weather_code"))
        except (TypeError, ValueError):
            weather_code = -1
        weather = WEATHER_CODE_LABELS.get(
            weather_code,
            f"未知天气（代码 {weather_code}）",
        )

        name_parts = [
            place.get("name"),
            place.get("admin1"),
            place.get("country"),
        ]
        display_name = "，".join(
            str(part).strip()
            for part in name_parts
            if str(part or "").strip()
        )
        if not display_name:
            display_name = city

        observed_at = str(current.get("time") or "未知").replace("T", " ")
        return {
            "city": display_name,
            "weather": weather,
            "temperature": f"{temperature}°C",
            "humidity": f"{humidity}%",
            "wind_speed": f"{wind_speed} km/h",
            "observed_at": observed_at,
        }

    @staticmethod
    def _format_result(weather: dict[str, str]) -> str:
        """把天气字典格式化成工具结果文本。"""
        return TOOL_ACTIVITY_TEMPLATE.format(**weather)

    @staticmethod
    def _request_model_and_parse(
        character: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """请求模型并把返回内容解析成结构化字典。"""
        from backend.chat.streaming import invoke_reply

        model_result = invoke_reply(character, character.messages)
        raw_content = model_result.get("content", "")
        if not isinstance(raw_content, str):
            raw_content = str(raw_content or "")

        try:
            parsed = RESPONSE_FORMAT_PARSER.parse(raw_content)
        except Exception:
            parsed = None
        if not isinstance(parsed, dict):
            parsed = {"content": raw_content, "tool": ""}
        if not str(parsed.get("tool") or "").strip() and str(parsed.get("content") or "").strip():
            model_result["_character_response"] = parsed

        return model_result, parsed

    @staticmethod
    def _get_tool(character: Any, tool_name: str, tool_args: Any) -> Any:
        """按工具名取出工具对象，并校验参数键是否都已声明。"""
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args 必须是键值对字典")

        tool_info = character.tools.get(tool_name)
        if not isinstance(tool_info, dict):
            raise ValueError(f"模型选择了不存在的工具：{tool_name}")

        tool = tool_info.get("tool")
        if tool is None:
            raise ValueError(f"工具缺少 tool 对象：{tool_name}")

        parameters = tool_info.get("parameters", [])
        if not isinstance(parameters, list):
            raise ValueError(f"工具参数声明格式错误：{tool_name}")

        unknown_args = set(tool_args) - {str(parameter) for parameter in parameters}
        if unknown_args:
            raise ValueError(
                "模型返回了工具未声明的参数："
                + "、".join(sorted(unknown_args))
            )

        return tool

    @staticmethod
    def _log_failure(message: Any) -> None:
        """在终端打印工具失败日志。"""
        print(TOOL_FAILURE_LOG_TEMPLATE.format(message=message))

    @staticmethod
    def _append_failure(last_message: dict[str, Any], message: str) -> None:
        """把工具失败信息追加到同一条 assistant 消息。"""
        last_message["content"] = (
            str(last_message.get("content") or "")
            + "\n\n"
            + TOOL_FAILURE_TEMPLATE.format(message=message)
        )

    @staticmethod
    def _finish(
        model_result: dict[str, Any],
        last_message: dict[str, Any],
        content: str,
    ) -> dict[str, Any]:
        """把最终回复追加到同一条 assistant 消息，并返回模型结果。"""
        last_message["content"] = (
            str(last_message.get("content") or "")
            + "\n\n"
            + FINAL_REPLY_TEMPLATE.format(content=content)
        )
        reasoning_content = model_result.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            last_message["reasoning_content"] = reasoning_content
        model_result["content"] = content
        return model_result

    def _finish_after_failure(
        self,
        character: Any,
        last_message: dict[str, Any],
    ) -> dict[str, Any]:
        """工具失败达到上限后，再请求一次模型并强制收尾。"""
        model_result, parsed = self._request_model_and_parse(character)
        if str(parsed.get("tool") or "").strip():
            content = WEATHER_FAILURE_FALLBACK
        else:
            content = str(parsed.get("content") or "").strip()
            if not content:
                content = WEATHER_FAILURE_FALLBACK
        return self._finish(model_result, last_message, content)

    def _continue(
        self,
        character: Any,
        last_message: dict[str, Any],
    ) -> dict[str, Any]:
        """继续请求模型，处理后续工具调用并生成最终回复。"""
        model_result, parsed = self._request_model_and_parse(character)
        failure_count = 0

        while True:
            tool_name = str(parsed.get("tool") or "").strip()
            if not tool_name:
                content = str(parsed.get("content") or "").strip()
                if not content:
                    if failure_count:
                        content = WEATHER_FAILURE_FALLBACK
                    else:
                        raise ValueError("模型没有返回最终内容")
                return self._finish(model_result, last_message, content)

            tool_args = parsed.get("tool_args", {})
            if tool_args is None:
                tool_args = {}
            try:
                tool = self._get_tool(character, tool_name, tool_args)
                return run_tool(tool, character, **tool_args)
            except ToolCallLimitError:
                self._log_failure(TOOL_LIMIT_MESSAGE)
                self._append_failure(last_message, TOOL_LIMIT_MESSAGE)
                return self._finish_after_failure(character, last_message)
            except Exception as exc:
                self._log_failure(exc)
                failure_count += 1
                self._append_failure(last_message, f"工具调用失败：{exc}")
                if failure_count >= MAX_TOOL_FAILURES:
                    return self._finish_after_failure(character, last_message)
                model_result, parsed = self._request_model_and_parse(character)

    def call(self, character: Any, city: str = "") -> dict[str, Any]:
        """查询指定城市天气，并把工具结果和模型最终回复写入历史。

        Args:
            character: 调用该工具的角色对象。它的 messages 最后一条必须
                是 chat() 刚写入的 assistant 占位消息。
            city: 要查询的城市名称，例如“桂林”。

        Returns:
            模型最终返回的结果字典，与 chat() 的返回值结构一致。

        Raises:
            ValueError: 最后一条消息不是 assistant，或模型没有返回最终内容。
            RuntimeError: 天气接口请求失败且无法完成兜底回复。
        """
        last_message = None
        try:
            if not character.messages:
                raise ValueError("角色消息为空，无法执行天气工具")

            last_message = character.messages[-1]
            if last_message.get("role") != "assistant":
                raise ValueError("天气工具执行前，最后一条消息必须是 assistant")

            weather = self._fetch_weather(city)

            # 先把执行结果写进同一条 assistant 消息，再打印成功日志。
            last_message["content"] = (
                str(last_message.get("content") or "")
                + "\n\n"
                + self._format_result(weather)
            )
            print(TOOL_SUCCESS_MESSAGE)
        except Exception as exc:
            self._log_failure(exc)
            if last_message is not None and last_message.get("role") == "assistant":
                self._append_failure(last_message, f"天气工具调用失败：{exc}")
                return self._finish_after_failure(character, last_message)
            raise

        try:
            return self._continue(character, last_message)
        except Exception as exc:
            self._log_failure(exc)
            raise
