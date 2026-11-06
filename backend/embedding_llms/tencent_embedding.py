"""腾讯云混元 Embedding 提供商。

腾讯云混元提供 OpenAI 兼容接口，因此直接复用
OpenAICompatibleEmbeddingProvider。
"""

from backend.embedding_llms.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


class TencentEm(OpenAICompatibleEmbeddingProvider):
    """腾讯云混元 Embedding 提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 腾讯云混元的 OpenAI 兼容接口地址。
        model: Embedding 模型名称，例如 hunyuan-embedding。
        api_key: 腾讯云 API Key。
    """

    display_name = "Tencent"
    base_url = "https://api.hunyuan.cloud.tencent.com/v1"