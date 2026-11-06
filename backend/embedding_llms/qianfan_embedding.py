"""百度千帆 Embedding 提供商。

百度千帆提供 OpenAI 兼容接口，因此直接复用
OpenAICompatibleEmbeddingProvider。
"""

from backend.embedding_llms.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


class QianfanEm(OpenAICompatibleEmbeddingProvider):
    """百度千帆 Embedding 提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 百度千帆的 OpenAI 兼容接口地址。
        model: Embedding 模型名称，例如 embedding-v1。
        api_key: 百度千帆 API Key。
    """

    display_name = "Qianfan"
    base_url = "https://qianfan.baidubce.com/v2"