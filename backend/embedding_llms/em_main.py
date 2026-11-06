"""Embedding 模型调用封装。

作用：
1. 接收一个已经创建好的 Embedding 模型对象；
2. 提供和 Character.invoke() 类似的 invoke() 入口；
3. 根据输入是字符串还是字符串列表，选择单条或批量向量化方法。

当前主要用途是把结果写入 ChromaDB，返回值不是业务层必须依赖的内容，
但保留向量返回值便于测试和后续扩展。
"""

from typing import Any


class EmLLM:
    """Embedding 模型调用封装。

    Attributes:
        embedding_model: LangChain Embeddings 对象，需要具备
            embed_query() 和 embed_documents() 方法。
    """

    def __init__(self, embedding_model: Any) -> None:
        """保存 Embedding 模型对象。

        Args:
            embedding_model: 已经实例化的 Embeddings 对象，例如
                OllamaEmbeddings 或 OpenAIEmbeddings；也可以传带 run() 的
                提供商包装对象，例如 OllamaEm(...)。

        Raises:
            TypeError: 传入对象无法提供 embed_query() 和
                embed_documents()。
        """
        # 也允许直接传 OllamaEm / AliyunEm 这类包装对象。
        if not (
            hasattr(embedding_model, "embed_query")
            and hasattr(embedding_model, "embed_documents")
        ) and callable(getattr(embedding_model, "run", None)):
            embedding_model = embedding_model.run()

        if not hasattr(embedding_model, "embed_query"):
            raise TypeError("embedding_model 必须提供 embed_query() 方法")
        if not hasattr(embedding_model, "embed_documents"):
            raise TypeError("embedding_model 必须提供 embed_documents() 方法")

        self.embedding_model = embedding_model

    def invoke(self, texts: str | list[str]):
        """把字符串或字符串列表转换为向量。

        Args:
            texts: 单条字符串，或字符串列表。

        Returns:
            单条字符串返回一条向量；字符串列表返回向量列表。

        Raises:
            TypeError: texts 类型非法，或列表中包含非字符串。
        """
        if isinstance(texts, str):
            return self.embedding_model.embed_query(texts)

        if isinstance(texts, list):
            if not all(isinstance(text, str) for text in texts):
                raise TypeError("texts 列表中的每一项都必须是字符串")
            return self.embedding_model.embed_documents(texts)

        raise TypeError("texts 必须是字符串或字符串列表")
