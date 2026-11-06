"""其他 OpenAI 兼容模型提供商。

用于接入没有单独适配、但提供 OpenAI 兼容接口的服务。
"""

from backend.llms.openai_compatible import OpenAICompatibleProvider


class Other(OpenAICompatibleProvider):
    """自定义 OpenAI 兼容模型提供商。

    Attributes:
        display_name: 错误信息中显示的提供商名称。
        base_url: 用户填写的 OpenAI 兼容接口地址。
        model: 模型名称。
        api_key: 兼容接口的 API Key。
        temperature: 模型生成温度。
    """

    display_name = "Other"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        temperature: float = 0.8,
    ) -> None:
        """保存自定义 OpenAI 兼容接口参数。

        Args:
            base_url: 接口地址，不能为空。
            model: 模型名称，不能为空。
            api_key: API Key，不能为空。
            temperature: 生成温度，默认 0.8。

        Returns:
            None。

        Raises:
            ValueError: base_url、model 或 api_key 为空。
        """
        if not base_url:
            raise ValueError("Other 的 base_url 不能为空")

        super().__init__(
            model=model,
            api_key=api_key,
            temperature=temperature,
            base_url=base_url,
        )