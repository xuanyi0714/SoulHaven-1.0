"""火山引擎方舟（豆包）模型提供商。

火山方舟提供 OpenAI 兼容接口。模型字段既可以填方舟的模型 ID，也可以
填推理接入点 ID（通常以 ep- 开头）。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class Volcengine(OpenAICompatibleProvider):
    """火山引擎方舟（豆包）模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 火山方舟的 OpenAI 兼容接口地址。
        model: 模型 ID 或推理接入点 ID。
        api_key: 火山方舟 API Key。
        temperature: 模型生成温度。
    """

    display_name = "Volcengine"
    base_url = "https://ark.cn-beijing.volces.com/api/v3"