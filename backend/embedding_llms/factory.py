"""Embedding 模型工厂。

作用：
1. 根据角色配置创建对应提供商的 LangChain Embeddings 对象；
2. 创建角色、启动恢复和后续写入 ChromaDB 共用同一套构造逻辑；
3. 只返回 Embeddings 对象，不负责读写 settings.json 或 ChromaDB。

settings 字典约定：
{
    "provider": "ollama" | "aliyun" | "volcengine" | "zhipu" |
                "qianfan" | "tencent" | "other",
    "model": "Embedding 模型名称",
    "api_key": "API Key，Ollama 可为空",
    "base_url": "接口地址；Ollama 可选，other 必填"
}
"""

from typing import Any

from backend.embedding_llms.aliyun_embedding import AliyunEm
from backend.embedding_llms.ollama_embedding import OllamaEm
from backend.embedding_llms.other_embedding import OtherEm
from backend.embedding_llms.qianfan_embedding import QianfanEm
from backend.embedding_llms.tencent_embedding import TencentEm
from backend.embedding_llms.volcengine_embedding import VolcengineEm
from backend.embedding_llms.zhipu_embedding import ZhipuEm


def build_embeddings(settings: dict[str, Any]):
    """根据配置创建 LangChain Embeddings 对象。

    Args:
        settings: Embedding 配置字典，包含 provider、model、api_key 和
            base_url。

    Returns:
        对应提供商的 LangChain Embeddings 对象，具备 embed_query() 和
        embed_documents() 方法。

    Raises:
        ValueError: provider 未知、模型名为空、固定提供商缺少 API Key，
            或自定义提供商缺少 base_url。
    """
    provider = str(settings.get("provider") or "").strip().lower()
    model = str(settings.get("model") or "").strip()
    api_key = str(settings.get("api_key") or "").strip()
    base_url = str(settings.get("base_url") or "").strip()

    if not provider:
        raise ValueError("embedding provider 不能为空")
    if not model:
        raise ValueError("embedding model 不能为空")

    if provider == "ollama":
        return OllamaEm(
            model=model,
            base_url=base_url or "http://127.0.0.1:11434",
        ).run()

    provider_classes = {
        "aliyun": AliyunEm,
        "volcengine": VolcengineEm,
        "zhipu": ZhipuEm,
        "qianfan": QianfanEm,
        "tencent": TencentEm,
    }
    provider_class = provider_classes.get(provider)
    if provider_class is not None:
        return provider_class(
            model=model,
            api_key=api_key,
            base_url=base_url or None,
        ).run()

    if provider == "other":
        if not base_url:
            raise ValueError("自定义 Embedding 提供商的 base_url 不能为空")
        return OtherEm(
            base_url=base_url,
            model=model,
            api_key=api_key,
        ).run()

    raise ValueError(
        "embedding provider 只支持 ollama、aliyun、volcengine、zhipu、"
        "qianfan、tencent 或 other"
    )