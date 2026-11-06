"""自定义 Claude 兼容模型提供商。

Claude 使用 Anthropic Messages API，不是 OpenAI 兼容接口。因此该提供商
使用 langchain-anthropic 的 ChatAnthropic，并要求调用方提供中转站的
base_url。没有默认地址，因为这里只适配兼容 Anthropic Messages API 的
中转站，不针对 Claude 官方网站。
"""

from langchain_anthropic import ChatAnthropic


class ClaudeOther:
    """自定义 Claude 兼容模型提供商。

    Attributes:
        base_url: Anthropic 兼容中转站地址，由用户填写。
        model: Claude 模型名称。
        api_key: 中转站 API Key。
        temperature: 模型生成温度。
        max_tokens: 单次回复的最大 token 数。
    """

    # Claude Messages API 必须提供 max_tokens；这里给一个适合角色扮演的默认值。
    max_tokens = 4096

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        temperature: float = 0.8,
    ) -> None:
        """保存 Claude 兼容接口参数。

        Args:
            base_url: Anthropic 兼容中转站的根地址，不能为空。
            model: Claude 模型名称，不能为空。
            api_key: 中转站 API Key，不能为空。
            temperature: 生成温度，默认 0.8。

        Returns:
            None。

        Raises:
            ValueError: base_url、model 或 api_key 为空。
        """
        if not base_url:
            raise ValueError("Claude 兼容提供商的 base_url 不能为空")
        if not model:
            raise ValueError("Claude 兼容提供商的模型名称不能为空")
        if not api_key:
            raise ValueError("Claude 兼容提供商的 api_key 不能为空")

        # Anthropic 兼容中转站地址；去掉尾部斜杠，避免拼接出重复斜杠。
        self.base_url = base_url.rstrip("/")

        # 要调用的 Claude 模型名称。
        self.model = model

        # 访问中转站所需的 API Key。
        self.api_key = api_key

        # 模型生成温度。
        self.temperature = temperature

    def run(self):
        """创建 LangChain 的 Claude 聊天模型对象。

        Args:
            无。使用 __init__ 中保存的 base_url、model、api_key 和
            temperature。

        Returns:
            配置好的 ChatAnthropic 对象，具备 invoke() 方法。
        """
        return ChatAnthropic(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )