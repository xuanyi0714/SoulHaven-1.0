"""Ollama 本地 Embedding 提供商。

作用：
1. 保存 Ollama 本地服务地址和 Embedding 模型名称；
2. 使用 LangChain 的 OllamaEmbeddings 创建向量模型对象；
3. Ollama 不需要 api_key。
"""

from langchain_ollama import OllamaEmbeddings


class OllamaEm:
    """Ollama 本地 Embedding 提供商。

    Attributes:
        base_url: Ollama 本地服务地址。
        model: Embedding 模型名称，例如 nomic-embed-text。
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
    ) -> None:
        """保存 Ollama Embedding 连接参数。

        Args:
            model: Ollama Embedding 模型名称，不能为空。
            base_url: Ollama 服务地址，默认本机 11434 端口。

        Raises:
            ValueError: 模型名为空。
        """
        if not model:
            raise ValueError("Ollama 的 Embedding 模型名不能为空")

        self.base_url = base_url or "http://127.0.0.1:11434"
        self.model = model

    def run(self, texts: str | list[str] | None = None):
        """创建 Embeddings 对象，或直接把文本转换为向量。

        Args:
            texts: 不传时返回 LangChain Embeddings 对象；传字符串时调用
                embed_query()；传字符串列表时调用 embed_documents()。

        Returns:
            不传 texts 时返回 OllamaEmbeddings 对象；传字符串时返回单条
            向量；传列表时返回向量列表。

        Raises:
            TypeError: texts 既不是字符串也不是字符串列表。
        """
        embeddings = OllamaEmbeddings(
            model=self.model,
            base_url=self.base_url,
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