"""硅基流动模型提供商。

硅基流动提供 OpenAI 兼容接口，因此直接复用 OpenAICompatibleProvider。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class SiliconFlow(OpenAICompatibleProvider):
    """硅基流动模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 硅基流动的 OpenAI 兼容接口地址。
        model: 模型名称，例如 deepseek-ai/DeepSeek-V3。
        api_key: 硅基流动 API Key。
        temperature: 模型生成温度。
    """

    display_name = "SiliconFlow"
    base_url = "https://api.siliconflow.cn/v1"