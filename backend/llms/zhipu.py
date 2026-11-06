"""智谱清言（BigModel）模型提供商。

智谱开放平台提供 OpenAI 兼容接口，因此直接复用 OpenAICompatibleProvider。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class Zhipu(OpenAICompatibleProvider):
    """智谱清言模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 智谱开放平台的 OpenAI 兼容接口地址。
        model: 模型名称，例如 glm-4-plus。
        api_key: 智谱 API Key。
        temperature: 模型生成温度。
    """

    display_name = "Zhipu"
    base_url = "https://open.bigmodel.cn/api/paas/v4"