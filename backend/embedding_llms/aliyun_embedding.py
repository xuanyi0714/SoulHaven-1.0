"""阿里云百炼 Embedding 提供商。

阿里云百炼提供 OpenAI 兼容接口，因此直接复用
OpenAICompatibleEmbeddingProvider。
"""

from backend.embedding_llms.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


class AliyunEm(OpenAICompatibleEmbeddingProvider):
    """阿里云百炼 Embedding 提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 阿里云百炼的 OpenAI 兼容接口地址。
        model: Embedding 模型名称，例如 text-embedding-v4。
        api_key: 阿里云百炼 API Key。
    """

    display_name = "Aliyun"
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
