"""火山引擎方舟 Embedding 提供商。

火山方舟提供 OpenAI 兼容接口，因此直接复用
OpenAICompatibleEmbeddingProvider。
"""

from backend.embedding_llms.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


class VolcengineEm(OpenAICompatibleEmbeddingProvider):
    """火山引擎方舟 Embedding 提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 火山方舟的 OpenAI 兼容接口地址。
        model: Embedding 模型名称或推理接入点 ID。
        api_key: 火山方舟 API Key。
    """

    display_name = "Volcengine"
    base_url = "https://ark.cn-beijing.volces.com/api/v3"