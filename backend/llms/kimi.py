"""Kimi（月之暗面）模型提供商。

Kimi 开放平台提供 OpenAI 兼容接口，因此直接复用 OpenAICompatibleProvider。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class Kimi(OpenAICompatibleProvider):
    """Kimi（月之暗面）模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: Kimi 的 OpenAI 兼容接口地址。
        model: 模型名称，例如 moonshot-v1-8k。
        api_key: Kimi API Key。
        temperature: 模型生成温度。
    """

    display_name = "Kimi"
    base_url = "https://api.moonshot.cn/v1"