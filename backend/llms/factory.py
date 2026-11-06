"""模型工厂。

作用：
1. 根据角色 settings 字典创建对应提供商的 LangChain ChatModel；
2. 创建角色和启动加载角色共用同一套模型构造逻辑；
3. 只返回模型对象，不负责读写 settings.json。

settings 字典约定：
{
    "provider": "ollama" | "aliyun" | "deepseek" | "siliconflow" |
                "volcengine" | "zhipu" | "kimi" | "other" |
                "claude_other",
    "model": "模型名称",
    "temperature": 0.8,
    "api_key": "API Key，可为空",
    "base_url": "自定义接口地址，可为空"
}
"""

from typing import Any

from backend.llms.aliyun import Aliyun
from backend.llms.claude_other import ClaudeOther
from backend.llms.deepseek import DeepSeek
from backend.llms.kimi import Kimi
from backend.llms.ollama import Ollama
from backend.llms.other import Other
from backend.llms.siliconflow import SiliconFlow
from backend.llms.volcengine import Volcengine
from backend.llms.zhipu import Zhipu


def build_llm(settings: dict[str, Any]):
    """根据角色配置创建 LangChain ChatModel。

    Args:
        settings: 角色模型配置字典，通常来自 settings.json，包含
            provider、model、temperature、api_key 和 base_url。

    Returns:
        对应提供商的 LangChain ChatModel 对象，具备 invoke() 方法。

    Raises:
        ValueError: provider 未知、model 为空、temperature 非法、
            固定提供商缺少 api_key，或自定义提供商缺少 base_url 或
            api_key。
    """
    provider = str(settings.get("provider") or "").strip().lower()
    model = str(settings.get("model") or "").strip()
    api_key = str(settings.get("api_key") or "").strip()
    base_url = str(settings.get("base_url") or "").strip()

    raw_temperature = settings.get("temperature", 0.8)
    try:
        temperature = float(raw_temperature)
    except (TypeError, ValueError) as exc:
        raise ValueError("temperature 必须是数字") from exc
    if not 0 <= temperature <= 2:
        raise ValueError("temperature 必须在 0 到 2 之间")

    if not provider:
        raise ValueError("provider 不能为空")
    if not model:
        raise ValueError("model 不能为空")

    if provider == "ollama":
        # Ollama 使用本机服务，不需要 api_key 和 base_url。
        return Ollama(model=model, temperature=temperature).run()

    # 这些提供商都有固定的 OpenAI 兼容地址，只需要模型名和 API Key。
    provider_classes = {
        "aliyun": Aliyun,
        "deepseek": DeepSeek,
        "siliconflow": SiliconFlow,
        "volcengine": Volcengine,
        "zhipu": Zhipu,
        "kimi": Kimi,
    }
    provider_class = provider_classes.get(provider)
    if provider_class is not None:
        return provider_class(
            model=model,
            api_key=api_key,
            temperature=temperature,
        ).run()

    if provider == "other":
        if not base_url:
            raise ValueError("自定义提供商的 base_url 不能为空")
        if not api_key:
            raise ValueError("自定义提供商的 api_key 不能为空")
        return Other(
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=temperature,
        ).run()

    if provider == "claude_other":
        if not base_url:
            raise ValueError("Claude 兼容提供商的 base_url 不能为空")
        if not api_key:
            raise ValueError("Claude 兼容提供商的 api_key 不能为空")
        return ClaudeOther(
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=temperature,
        ).run()

    raise ValueError(
        "provider 只支持 ollama、aliyun、deepseek、siliconflow、"
        "volcengine、zhipu、kimi、other 或 claude_other"
    )