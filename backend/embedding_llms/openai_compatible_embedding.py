"""OpenAI 兼容 Embedding 接口的公共实现。

作用：
1. 统一保存 base_url、model 和 api_key；
2. 用 LangChain 的 OpenAIEmbeddings 创建 Embedding 对象；
3. 各家 OpenAI 兼容提供商只需要继承并设置 display_name 与 base_url。
"""

from langchain_openai import OpenAIEmbeddings


class OpenAICompatibleEmbeddingProvider:
    """OpenAI 兼容 Embedding 提供商基类。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 默认接口地址；子类通过类属性覆盖。
        model: Embedding 模型名称。
        api_key: 接口 API Key。
    """

    display_name = "OpenAI 兼容"
    base_url = ""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str | None = None,
    ) -> None:
        """保存 OpenAI 兼容 Embedding 接口参数。

        Args:
            model: Embedding 模型名称，不能为空。
            api_key: 接口 API Key，不能为空。
            base_url: 可选接口地址；不传时使用子类的 base_url。

        Raises:
            ValueError: 模型名、API Key 或 base_url 为空。
        """
        if not model:
            raise ValueError(f"{self.display_name} 的 Embedding 模型名不能为空")
        if not api_key:
            raise ValueError(f"{self.display_name} 的 Embedding api_key 不能为空")

        resolved_base_url = base_url or self.base_url
        if not resolved_base_url:
            raise ValueError(f"{self.display_name} 的 Embedding base_url 不能为空")

        self.base_url = resolved_base_url
        self.model = model
        self.api_key = api_key

    def run(self, texts: str | list[str] | None = None):
        """创建 Embeddings 对象，或直接把文本转换为向量。

        Args:
            texts: 不传时返回 LangChain Embeddings 对象；传字符串时调用
                embed_query()；传字符串列表时调用 embed_documents()。

        Returns:
            不传 texts 时返回 OpenAIEmbeddings 对象；传字符串时返回单条
            向量；传列表时返回向量列表。

        Raises:
            TypeError: texts 既不是字符串也不是字符串列表。
        """
        embeddings = OpenAIEmbeddings(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            # 非 OpenAI 官方接口不一定支持 tiktoken 的 token 预处理。
            check_embedding_ctx_length=False,
        )

        if texts is None:
            return embeddings
        if isinstance(texts, list):
            if not all(isinstance(text, str) for text in texts):
                raise TypeError("texts 列表中的每一项都必须是字符串")
            return embeddings.embed_documents(texts)
        if isinstance(texts, str):
            return embeddings.embed_query(texts)
        raise TypeError("texts 必须是字符串或字符串列表")