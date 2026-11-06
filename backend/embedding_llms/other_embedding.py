"""自定义 OpenAI 兼容 Embedding 提供商。

用于接入没有单独适配、但提供 OpenAI 兼容 Embedding 接口的服务。
"""

from backend.embedding_llms.openai_compatible_embedding import (
    OpenAICompatibleEmbeddingProvider,
)


class OtherEm(OpenAICompatibleEmbeddingProvider):
    """自定义 OpenAI 兼容 Embedding 提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 用户填写的 OpenAI 兼容接口地址。
        model: Embedding 模型名称。
        api_key: 兼容接口的 API Key。
    """

    display_name = "Other"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
    ) -> None:
        """保存自定义 Embedding 接口参数。

        Args:
            base_url: 接口地址，不能为空。
            model: Embedding 模型名称，不能为空。
            api_key: API Key，不能为空。

        Raises:
            ValueError: base_url、model 或 api_key 为空。
        """
        if not base_url:
            raise ValueError("Other 的 Embedding base_url 不能为空")

        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
        )