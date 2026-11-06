"""Ollama 模型提供商。

作用：
1. 保存 Ollama 的本地服务地址、模型名称和温度；
2. 使用 LangChain 的 ChatOllama 创建模型对象；
3. Ollama 不需要 api_key。
"""

from langchain_ollama import ChatOllama


class Ollama:
    """Ollama 本地模型提供商。

    该类只保存连接参数，并在 run() 中创建 LangChain 的 ChatOllama
    对象。Ollama 使用本地服务，不需要 api_key。

    Attributes:
        base_url: Ollama 本地服务地址。
        model: 模型名称，例如 qwen3:8b。
        temperature: 生成温度，范围通常为 0 到 2。
    """

    def __init__(self, model: str, temperature: float = 0.8) -> None:
        """保存 Ollama 连接参数。

        Args:
            model: Ollama 模型名称，不能为空。
            temperature: 生成温度，默认 0.8。

        Returns:
            None。

        Raises:
            ValueError: model 为空。
        """
        if not model:
            raise ValueError("Ollama 的模型名称不能为空")

        # Ollama 默认监听本机 11434 端口。
        self.base_url = "http://127.0.0.1:11434"

        # 要调用的 Ollama 模型名称。
        self.model = model

        # 模型生成温度。
        self.temperature = temperature

    def run(self):
        """创建 LangChain 的 Ollama 聊天模型对象。

        Args:
            无。使用 __init__ 中保存的 base_url、model 和 temperature。

        Returns:
            配置好的 ChatOllama 对象，具备 invoke() 方法。
        """
        return ChatOllama(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url,
            # 让支持思考的 Ollama 模型把思考内容放到 reasoning_content 中。
            reasoning=True,
        )
