"""阿里云百炼模型提供商。

阿里云百炼提供 OpenAI 兼容接口，因此直接复用 OpenAICompatibleProvider。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class Aliyun(OpenAICompatibleProvider):
    """阿里云百炼模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 阿里云百炼的 OpenAI 兼容接口地址。
        model: 模型名称，例如 qwen-plus。
        api_key: 阿里云百炼 API Key。
        temperature: 模型生成温度。
    """

    display_name = "Aliyun"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
