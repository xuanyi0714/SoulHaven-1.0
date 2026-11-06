"""DeepSeek 模型提供商。

DeepSeek 提供 OpenAI 兼容接口，因此直接复用 OpenAICompatibleProvider。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class DeepSeek(OpenAICompatibleProvider):
    """DeepSeek 模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: DeepSeek 的 OpenAI 兼容接口地址。
        model: 模型名称，例如 deepseek-chat。
        api_key: DeepSeek API Key。
        temperature: 模型生成温度。
    """

    display_name = "DeepSeek"
    base_url = "https://api.deepseek.com"