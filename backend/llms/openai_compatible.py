"""OpenAI 兼容接口的公共实现。

作用：
1. 提供 ReasoningChatOpenAI，补回第三方接口返回的 reasoning_content；
2. 提供 OpenAICompatibleProvider，统一保存 base_url、model、api_key 和
   temperature，并创建对应的 ChatModel；
3. 各家 OpenAI 兼容提供商只需要继承并设置 display_name 与 base_url。
"""

from langchain_openai import ChatOpenAI


class ReasoningChatOpenAI(ChatOpenAI):
    """补回第三方 OpenAI 兼容接口返回的 reasoning_content。

    ChatOpenAI 默认只保留官方 OpenAI 字段，非标准的 reasoning_content
    不会进入 additional_kwargs。这里在父类解析完成后补上，供 Character
    统一提取。
    """

    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        generation = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or []
        if generation is not None and choices:
            delta = choices[0].get("delta") or {}
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(reasoning, str) and reasoning:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
        return generation

    def _create_chat_result(self, response, generation_info=None):
        """解析响应，并把第三方接口的思考内容补到 generation 上。

        Args:
            response: OpenAI SDK 返回的原始响应对象或字典。
            generation_info: 父类需要的附加生成信息，可为 None。

        Returns:
            父类生成的 ChatResult 对象；如果发现 reasoning_content，
            会写入每条 generation.message.additional_kwargs。
        """
        result = super()._create_chat_result(response, generation_info)
        reasoning = self._read_raw_reasoning(response)

        if reasoning:
            for generation in result.generations:
                generation.message.additional_kwargs["reasoning_content"] = reasoning

        return result

    @staticmethod
    def _read_raw_reasoning(response) -> str:
        """从原始响应中读取 reasoning_content 或 reasoning。

        Args:
            response: OpenAI SDK 响应对象或字典。

        Returns:
            找到的思考内容字符串；没有找到时返回空字符串。
        """
        raw_message = None

        if isinstance(response, dict):
            choices = response.get("choices") or []
            if choices:
                raw_message = choices[0].get("message") or {}
        else:
            try:
                message = response.choices[0].message
                reasoning = getattr(message, "reasoning_content", None)
                if isinstance(reasoning, str) and reasoning:
                    return reasoning
            except (AttributeError, IndexError, TypeError):
                pass

            try:
                dumped = response.model_dump()
                choices = dumped.get("choices") or []
                if choices:
                    raw_message = choices[0].get("message") or {}
            except (AttributeError, TypeError, ValueError):
                raw_message = None

        if isinstance(raw_message, dict):
            for key in ("reasoning_content", "reasoning"):
                value = raw_message.get(key)
                if isinstance(value, str) and value:
                    return value

        return ""


class OpenAICompatibleProvider:
    """OpenAI 兼容提供商基类。

    Attributes:
        display_name: 错误信息中显示的中文/英文提供商名称。
        base_url: 默认接口地址；子类通过类属性覆盖。
        model: 模型名称。
        api_key: 接口 API Key。
        temperature: 模型生成温度。
    """

    display_name = "OpenAI 兼容"
    base_url = ""

    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float = 0.8,
        base_url: str | None = None,
    ) -> None:
        """保存 OpenAI 兼容接口连接参数。

        Args:
            model: 模型名称，不能为空。
            api_key: API Key，不能为空。
            temperature: 生成温度，默认 0.8。
            base_url: 可选接口地址；不传时使用子类的 base_url。

        Returns:
            None。

        Raises:
            ValueError: 模型名、API Key 或 base_url 为空。
        """
        if not model:
            raise ValueError(f"{self.display_name} 的模型名称不能为空")
        if not api_key:
            raise ValueError(f"{self.display_name} 的 api_key 不能为空")

        resolved_base_url = base_url or self.base_url
        if not resolved_base_url:
            raise ValueError(f"{self.display_name} 的 base_url 不能为空")

        # 该提供商默认的 OpenAI 兼容接口地址。
        self.base_url = resolved_base_url

        # 要调用的模型名称。
        self.model = model

        # 访问接口所需的 API Key。
        self.api_key = api_key

        # 模型生成温度。
        self.temperature = temperature

    def run(self):
        """创建并返回 OpenAI 兼容的 LangChain ChatModel。

        Args:
            无。使用 __init__ 中保存的 base_url、model、api_key 和
            temperature。

        Returns:
            配置好的 ReasoningChatOpenAI 对象，具备 invoke() 方法，
            并会保留 reasoning_content。
        """
        return ReasoningChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            base_url=self.base_url,
            api_key=self.api_key,
        )
