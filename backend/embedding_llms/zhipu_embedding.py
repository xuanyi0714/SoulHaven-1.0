"""智谱 BigModel Embedding 提供商。

智谱开放平台提供 OpenAI 兼容接口，因此直接复用
OpenAICompatibleEmbeddingProvider。
"""

from backend.embedding_llms.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


class ZhipuEm(OpenAICompatibleEmbeddingProvider):
    """智谱 BigModel Embedding 提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 智谱开放平台的 OpenAI 兼容接口地址。
        model: Embedding 模型名称，例如 embedding-3。
        api_key: 智谱 API Key。
    """

    display_name = "Zhipu"
    base_url = "https://open.bigmodel.cn/api/paas/v4"