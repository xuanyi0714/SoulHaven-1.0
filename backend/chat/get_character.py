"""角色注册与创建。

作用：
1. CharacterRegistry 维护英文名到 Character 对象的对应关系；
2. load_all 在启动时扫描 characters 目录，恢复角色资料和模型配置；
3. get_character 按英文名查询角色；
4. add 只把新角色加入内存字典，不重新扫描目录；
5. create_character 负责创建对象、写入 description.json 和 settings.json，
   配置了 Embedding 时初始化 ChromaDB 记忆库，并注册到字典；
6. load_all 会读取 settings.json，并用它恢复角色的模型对象；
7. load_all 会补建历史归档，并从 original.json 恢复最后一次归档的上下文。

save_character 只负责落盘，不在这里重新加载所有角色，避免覆盖运行时
对象中的模型对象和聊天记忆。
"""

import base64
from copy import deepcopy
import binascii
import json
import os
import shutil
import tempfile
import warnings
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.chat.outputs import EMOTIONS
from backend.embedding_llms.em_main import EmLLM
from backend.embedding_llms.factory import build_embeddings
from backend.llms.factory import build_llm
from backend.llms.llms_main import (
    CHARACTERS_DIR,  # 角色目录
    DESCRIPTION_FILENAME,  # 角色描述文件名
    ENGLISH_NAME_PATTERN,  # 英文名格式正则
    SETTINGS_FILENAME,  # 角色模型配置文件名
    WINDOWS_RESERVED_NAMES,  # Windows 保留名称
    Character,
    save_character,
)
from backend.memory.chromadb_init import init_chromadb
from backend.memory.sum_up_history import HistoryMemory


MAX_CHARACTER_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CHARACTER_IMAGE_PIXELS = 25_000_000


def get_character_image_path(english_name: str, emotion: str = "calm") -> Path:
    """定位白名单内的情绪图片，并兼容暂时无法迁移的旧平静图。"""
    if (
        not ENGLISH_NAME_PATTERN.fullmatch(english_name)
        or english_name.upper() in WINDOWS_RESERVED_NAMES
    ):
        raise ValueError("角色英文名非法")
    if emotion not in EMOTIONS:
        raise ValueError("角色图片情绪非法")
    root = CHARACTERS_DIR.resolve()
    character_dir = root / english_name
    image_path = character_dir / "images" / f"{emotion}.png"
    if (
        character_dir.resolve().parent != root
        or image_path.resolve() != image_path
    ):
        raise ValueError("角色图片路径非法")
    gif_path = image_path.with_suffix(".gif")
    if not image_path.exists() and gif_path.resolve() == gif_path and gif_path.is_file():
        return gif_path
    if emotion == "calm" and not image_path.exists():
        legacy_path = character_dir / "image" / "calm.png"
        if legacy_path.resolve() == legacy_path and legacy_path.is_file():
            return legacy_path
    return image_path


def migrate_character_images(english_name: str) -> None:
    """无冲突时重命名旧目录；存在目标目录时保留两者，绝不覆盖。"""
    root = CHARACTERS_DIR.resolve()
    character_dir = root / english_name
    if (not ENGLISH_NAME_PATTERN.fullmatch(english_name)
            or english_name.upper() in WINDOWS_RESERVED_NAMES
            or character_dir.resolve().parent != root):
        raise ValueError("角色目录非法")
    legacy = character_dir / "image"
    destination = character_dir / "images"
    if not legacy.exists():
        return
    if legacy.resolve() != legacy or destination.resolve() != destination:
        raise ValueError("角色图片目录不能使用链接")
    if not legacy.is_dir():
        raise ValueError("旧角色图片目录不是文件夹")
    if destination.exists():
        print(f"[SoulHaven] {english_name} 同时存在 image 和 images，保留两者供检查")
        return
    legacy.rename(destination)


def prepare_character_image(image_data: bytes) -> bytes:
    """验证 PNG/JPEG/GIF；静态图转 PNG，GIF 保留动画。"""
    if len(image_data) > MAX_CHARACTER_IMAGE_BYTES:
        raise ValueError("角色形象图不能超过 10MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image_data)) as source:
                if source.format not in {"PNG", "JPEG", "GIF"}:
                    raise ValueError("角色形象图仅支持 PNG / JPG / JPEG / GIF")
                if source.width * source.height > MAX_CHARACTER_IMAGE_PIXELS:
                    raise ValueError("角色形象图不能超过 2500 万像素，请缩小后重试")
                source.verify()
            if image_data[:6] in (b"GIF87a", b"GIF89a"):
                with Image.open(BytesIO(image_data)) as animated:
                    frame_count = getattr(animated, "n_frames", 1)
                    if frame_count > 1000 or animated.width * animated.height * frame_count > 500_000_000:
                        raise ValueError("GIF 帧数或总像素过多，请缩小后重试")
                    for frame in range(frame_count):
                        animated.seek(frame)
                        animated.load()
                return image_data
            # verify 不解码像素；重新打开并完整 load，拒绝截断/损坏数据。
            with Image.open(BytesIO(image_data)) as source:
                source.load()
                with ImageOps.exif_transpose(source) as oriented:
                    mode = "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
                    pixels = oriented.convert(mode)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("角色形象图像素过多，请缩小后重试") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, EOFError) as exc:
        raise ValueError("角色形象图损坏或无法解码，请选择有效的 PNG / JPG / JPEG / GIF") from exc
    # 编码/运行环境故障属于服务端错误，不混同用户上传的损坏文件。
    with pixels:
        pixels.info.clear()
        output = BytesIO()
        pixels.save(output, format="PNG")
        return output.getvalue()


def save_character_image(english_name: str, png_data: bytes, emotion: str = "calm") -> Path:
    """在新角色目录内写临时文件，再替换为情绪 PNG 或 GIF。"""
    image_path = get_character_image_path(english_name, emotion)
    if image_path.parent.name != "images":
        raise ValueError("不能覆盖旧角色图片目录")
    image_path = image_path.with_suffix(".gif" if png_data[:6] in (b"GIF87a", b"GIF89a") else ".png")
    image_path.parent.mkdir(exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=image_path.parent, prefix=f".{emotion}-", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(png_data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, image_path)
        image_path.with_suffix(".png" if image_path.suffix == ".gif" else ".gif").unlink(missing_ok=True)
        image_path.with_suffix(".mp4").unlink(missing_ok=True)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return image_path


def _clean_text(value: Any) -> str | None:
    """把 JSON 中的可选字段统一成去掉首尾空白的字符串。

    Args:
        value: 任意输入值，通常是 JSON 字符串、None 或其他类型。

    Returns:
        去掉首尾空白后的字符串；输入为 None 或去空白后为空时返回 None。
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def save_settings(english_name: str, settings: dict[str, Any]) -> Path:
    """把角色模型配置写入 characters/<英文名>/settings.json。

    Args:
        english_name: 角色英文名，也是角色文件夹名。
        settings: 模型配置字典，包含 provider、model、temperature、
            api_key 和 base_url。

    Returns:
        已写入的 settings.json 路径。

    Raises:
        OSError: 角色文件夹不存在或写入文件失败。

    Side Effects:
        - api_key 非空时会进行 Base64 编码，并写入 api_key_encoding。
        - Base64 是编码而不是真正的加密，只用于避免明文直接出现在文件里。
    """
    character_dir = CHARACTERS_DIR / english_name  # 角色目录
    settings_path = character_dir / SETTINGS_FILENAME  # 角色模型配置文件名

    # 先读取并解码已有配置，合并后统一编码，避免丢失未来配置或重复编码。
    existing = load_settings(english_name) if settings_path.is_file() else None
    saved_data = deepcopy(existing or {})
    for key, value in settings.items():
        if isinstance(value, dict) and isinstance(saved_data.get(key), dict):
            saved_data[key].update(deepcopy(value))
        else:
            saved_data[key] = deepcopy(value)
    saved_data.setdefault("temperature", 0.8)
    if not isinstance(saved_data.get("output"), dict):
        saved_data["output"] = {}
    saved_data["output"].setdefault("stream", False)
    saved_data["output"].setdefault("segmented", False)
    saved_data.setdefault("embedding", {
        "enabled": False, "provider": "", "model": "", "api_key": "", "base_url": ""
    })
    # 自定义请求头也可能携带凭据，与 API Key 一起做 Base64 编码。
    groups = [saved_data]
    while groups:
        group = groups.pop()
        groups.extend(value for value in group.values() if isinstance(value, dict))
        fields = ("api_key", "header") if group is saved_data.get("search") else ("api_key",)
        for field in fields:
            if field not in group:
                continue
            value = str(group.get(field) or "").strip()
            group.pop(f"{field}_encoding", None)
            group[field] = ""
            if value:
                group[field] = base64.b64encode(value.encode("utf-8")).decode("ascii")
                group[f"{field}_encoding"] = "base64"

    settings_path.write_text(
        json.dumps(saved_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return settings_path


def load_settings(english_name: str) -> dict[str, Any] | None:
    """读取并解析角色模型配置。

    Args:
        english_name: 角色英文名，也是角色文件夹名。

    Returns:
        配置字典；settings.json 不存在时返回 None。api_key 会在返回前
        自动从 Base64 解码成原始字符串，search.header 同样解码。

    Raises:
        OSError: 配置文件读取失败。
        json.JSONDecodeError: settings.json 不是合法 JSON。
        ValueError: 顶层不是对象、api_key_encoding 非法，或 API Key
            不是合法的 Base64。
    """
    character_dir = CHARACTERS_DIR / english_name  # 角色目录
    settings_path = character_dir / SETTINGS_FILENAME  # 角色模型配置文件名
    if not settings_path.is_file():
        return None

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("settings.json 顶层必须是对象")

    groups = [data]
    while groups:
        group = groups.pop()
        groups.extend(value for value in group.values() if isinstance(value, dict))
        fields = ("api_key", "header") if group is data.get("search") else ("api_key",)
        for field in fields:
            encoding = str(group.pop(f"{field}_encoding", "") or "").strip()
            if not encoding:
                continue
            if encoding != "base64":
                raise ValueError(f"{field}_encoding 只支持 base64")
            value = str(group.get(field) or "")
            if value:
                try:
                    group[field] = base64.b64decode(value, validate=True).decode("utf-8")
                except (binascii.Error, UnicodeDecodeError) as exc:
                    raise ValueError(f"{field} 不是合法的 Base64") from exc
    if not isinstance(data.get("output"), dict):
        data["output"] = {}
    data["output"].setdefault("stream", False)
    data["output"].setdefault("segmented", False)
    return data


def stream_output_enabled(settings: dict[str, Any] | None) -> bool:
    output = (settings or {}).get("output")
    return isinstance(output, dict) and output.get("stream") is True


def segmented_reply_enabled(settings: dict[str, Any] | None) -> bool:
    """旧角色缺少 output.segmented 时默认关闭。"""
    output = (settings or {}).get("output")
    return isinstance(output, dict) and output.get("segmented") is True


class CharacterRegistry:
    """全局角色注册表。

    负责维护“角色英文名 -> Character 对象”的唯一映射。整个程序共享
    同一个字典，API 蓝图、创建流程和查询流程都通过这里访问角色。

    Attributes:
        characters: 类属性字典，键是角色英文名，值是 Character 对象。
            启动时由 load_all() 填充，创建角色后由 add() 增加。
    """

    # 类属性：英文名 -> Character 对象。所有实例和调用方共享这一份字典。
    characters: dict[str, Character] = {}

    @classmethod
    def load_all(cls) -> dict[str, Character]:
        """扫描 characters 目录，恢复所有角色并原地更新类属性字典。

        每个子文件夹名就是角色英文名；读取文件夹内的 description.json，
        用其中的资料创建 Character 对象。如果存在 settings.json，还会
        重建对应的模型对象。文件损坏、缺少目录或英文名非法的角色会被
        跳过，不会中断整个启动流程。

        Args:
            无。目录位置由 backend.llms.llms_main.CHARACTERS_DIR（角色目录）决定。

        Returns:
            CharacterRegistry.characters，即“英文名 -> Character”的字典。
            返回的是类属性本身，不是副本。

        Side Effects:
            - 清空并重新填充 cls.characters；
            - 有合法 settings.json 时，恢复角色的模型对象；
            - 为角色补建 history/original 和 history/digest，并尝试从
              original.json 恢复最后一次总结边界之后的 messages；
            - 配置缺失、损坏或模型构造失败时，该角色仍然加载，但
              llm 为 None；
            - 跳过异常角色或配置时会打印警告。
        """
        loaded: dict[str, Character] = {}

        if CHARACTERS_DIR.is_dir():  # 角色目录
            for character_dir in sorted(
                CHARACTERS_DIR.iterdir(), key=lambda path: path.name.casefold()  # 角色目录
            ):
                if not character_dir.is_dir():
                    continue

                english_name = character_dir.name
                if not ENGLISH_NAME_PATTERN.fullmatch(english_name):  # 英文名格式正则
                    print(f"[SoulHaven] 跳过非法角色目录：{english_name}")
                    continue
                if english_name.upper() in WINDOWS_RESERVED_NAMES:  # Windows 保留名称
                    print(
                        "[SoulHaven] 跳过 Windows 保留角色目录："
                        f"{english_name}"
                    )
                    continue

                description_path = character_dir / DESCRIPTION_FILENAME  # 角色描述文件名
                if not description_path.is_file():
                    print(
                        "[SoulHaven] 跳过缺少 "
                        f"{DESCRIPTION_FILENAME} 的角色：{english_name}"  # 角色描述文件名
                    )
                    continue

                try:
                    data = json.loads(
                        description_path.read_text(encoding="utf-8")
                    )
                    if not isinstance(data, dict):
                        raise ValueError("description.json 顶层必须是对象")

                    name = _clean_text(data.get("name"))
                    base_info = _clean_text(data.get("base_info"))
                    if not name:
                        raise ValueError("缺少 name")
                    if not base_info:
                        raise ValueError("缺少 base_info")

                    # 图片迁移失败不影响角色及其聊天记录的恢复。
                    try:
                        migrate_character_images(english_name)
                    except (OSError, ValueError) as exc:
                        print(f"[SoulHaven] 角色图片目录迁移失败 {english_name}：{exc}")

                    # settings.json 是可选的；旧角色没有它时继续加载，
                    # 只是 llm 为 None，无法直接聊天。
                    settings = None
                    try:
                        settings = load_settings(english_name)
                    except (
                        OSError,
                        json.JSONDecodeError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        print(
                            "[SoulHaven] 角色配置读取失败 "
                            f"{english_name}：{exc}"
                        )

                    # 配置合法时重建模型；模型构造失败也不影响角色资料加载。
                    llm = None
                    if settings:
                        try:
                            llm = build_llm(settings)
                        except Exception as exc:
                            print(
                                "[SoulHaven] 角色模型恢复失败 "
                                f"{english_name}：{exc}"
                            )

                    em_llm = None
                    embedding = (settings or {}).get("embedding")
                    if isinstance(embedding, dict) and embedding.get("enabled", False):
                        try:
                            em_llm = EmLLM(build_embeddings(embedding))
                        except Exception:
                            # 不回显异常详情，避免服务商异常包含密钥。
                            print(f"[SoulHaven] 角色 Embedding 恢复失败 {english_name}，保留普通聊天")

                    character = Character(
                        llm=llm,
                        name=name,
                        english_name=english_name,
                        gender=data.get("gender"),
                        base_info=base_info,
                        brief=data.get("brief"),
                        age=data.get("age"),
                        height=data.get("height"),
                        weight=data.get("weight"),
                        hometown=data.get("hometown"),
                        current_location=data.get("current_location"),
                        initial_relationship=data.get("initial_relationship"),
                        dialogue_examples=data.get("dialogue_examples"),
                        speaking_style=data.get("speaking_style"),
                        personality_traits=data.get("personality_traits"),
                        opening_line=data.get("opening_line"),
                        em_llm=em_llm,
                        search_settings=(settings or {}).get("search"),
                        stream_output=stream_output_enabled(settings),
                        segmented_reply=segmented_reply_enabled(settings),
                        world_id=data.get("world_id") or "reality",
                    )

                    # 旧角色没有归档时补建；有 original.json 时恢复最后一次
                    # 总结边界之后的上下文。
                    try:
                        HistoryMemory.initialize_character_history(character)
                        HistoryMemory.load_messages(character)
                    except Exception as exc:
                        print(
                            "[SoulHaven] 角色历史恢复失败 "
                            f"{english_name}：{exc}"
                        )

                    loaded[english_name] = character
                    from backend.character.records import folders
                    folders(CHARACTERS_DIR, english_name)
                except (
                    OSError,
                    json.JSONDecodeError,
                    TypeError,
                    ValueError,
                ) as exc:
                    print(
                        "[SoulHaven] 跳过无法读取的角色 "
                        f"{english_name}：{exc}"
                    )

        cls.characters.clear()
        cls.characters.update(loaded)
        return cls.characters

    @classmethod
    def get_character(cls, english_name: str) -> Character | None:
        """按英文名查询一个角色。

        Args:
            english_name: 角色英文名，也是字典键和文件夹名。

        Returns:
            找到时返回 Character 对象；不存在时返回 None。
        """
        return cls.characters.get(english_name)

    @classmethod
    def add(cls, character: Character) -> None:
        """把一个新角色加入内存字典，不扫描目录。

        该方法用于 create_character 创建成功后的注册。它不会重新加载
        其他角色，因此不会覆盖已有角色的模型对象和聊天记忆。

        Args:
            character: 已经创建并写入 JSON 的 Character 对象。

        Returns:
            None。如果英文名已存在，会覆盖旧对象。
        """
        cls.characters[character.english_name] = character


def create_character(
    llm: Any,
    name: str,
    english_name: str,
    gender: str,
    base_info: str,
    age: str | None = None,
    height: str | None = None,
    weight: str | None = None,
    hometown: str | None = None,
    current_location: str | None = None,
    initial_relationship: str | None = None,
    dialogue_examples: str | None = None,
    speaking_style: str | None = None,
    personality_traits: str | None = None,
    opening_line: str | None = None,
    settings: dict[str, Any] | None = None,
    embedding_settings: dict[str, Any] | None = None,
    em_llm: Any = None,
    image_data: bytes | None = None,
    emotion_images: dict[str, bytes] | None = None,
    brief: str | None = None,
    world_id: str = "reality",
    emotion_videos: dict[str, bytes] | None = None,
) -> Character:
    """创建角色、写入 JSON，并注册到 CharacterRegistry。

    Args:
        llm: LangChain ChatModel 对象，用于该角色后续聊天。
        name: 角色中文名，必填。
        english_name: 角色英文名，必填；同时作为文件夹名和字典键。
        gender: 角色性别，用户创建角色时必填。
        base_info: 角色基本描述，必填。
        brief: 列表展示用简介；旧调用可以不传。
        age: 年龄，字符串，可为 None。
        height: 身高，字符串，可为 None。
        weight: 体重，字符串，可为 None。
        hometown: 家乡，字符串，可为 None。
        current_location: 当前所在地，字符串，可为 None。
        initial_relationship: 与用户的初始关系，字符串，可为 None。
        dialogue_examples: 对话示例，字符串，可为 None。
        speaking_style: 说话风格，字符串，可为 None。
        personality_traits: 重要性格特点，字符串，可为 None。
        opening_line: 开场白，可为 None；为空时使用默认开场白。
        settings: 运行配置字典，可包含 search；不为 None 时写入 settings.json。API
            创建角色时必须传入，否则重启后无法恢复模型。
        em_llm: 可选的已构建 EmLLM 对象，传给 Character 并绑定到其属性。
        embedding_settings: Embedding 配置字典。provider 和 model 都非空
            时，表示用户启用了记忆模型，会在角色目录下初始化 ChromaDB
            的 digest 和 original 两个集合。
        image_data: 可选平静形象图，静态图转换为 PNG，GIF 保留动画。
        emotion_images: 情绪名到 PNG/JPEG/GIF 内容的字典；
            图片不写入角色配置，不传入任何模型。
        emotion_videos: 情绪名到 MP4 内容的字典；对应图片作为预览帧。

    Returns:
        新建的 Character 对象。该对象已经写入 description.json，可选地写入
        settings.json，建立 history 归档目录并写入开场白；配置了 Embedding
        时还会建立 ChromaDB 记忆库，最后加入 CharacterRegistry.characters。

    Raises:
        ValueError: 必填字段为空、英文名格式非法、英文名是 Windows
            保留名称，或对应角色文件夹已经存在。
        OSError: 创建文件夹、写入 description.json、settings.json、历史
            归档文件或 ChromaDB 记忆库失败。
        RuntimeError: 配置了 Embedding，但当前环境没有安装 chromadb。
    """
    name = str(name).strip()
    english_name = str(english_name).strip()
    gender = str(gender).strip()
    base_info = str(base_info).strip()

    if not name:
        raise ValueError("角色名字不能为空")
    if not english_name:
        raise ValueError("角色英文名不能为空")
    if not ENGLISH_NAME_PATTERN.fullmatch(english_name):  # 英文名格式正则
        raise ValueError(
            "角色英文名只能包含英文字母、数字、下划线和短横线，且必须以字母开头"
        )
    if english_name.upper() in WINDOWS_RESERVED_NAMES:  # Windows 保留名称
        raise ValueError("角色英文名不能使用 Windows 保留名称")
    if not gender:
        raise ValueError("角色性别不能为空")
    if not base_info:
        raise ValueError("角色基本描述不能为空")

    images_to_save = dict(emotion_images or {})
    if set(images_to_save) - EMOTIONS or (image_data is not None and "calm" in images_to_save):
        raise ValueError("角色形象图情绪无效或重复")
    if image_data is not None:
        images_to_save["calm"] = image_data

    if (
        em_llm is None
        and isinstance(embedding_settings, dict)
        and embedding_settings.get("enabled", True)
        and str(embedding_settings.get("provider") or "").strip()
        and str(embedding_settings.get("model") or "").strip()
    ):
        em_llm = EmLLM(build_embeddings(embedding_settings))

    character = Character(
        llm=llm,
        name=name,
        english_name=english_name,
        gender=gender,
        base_info=base_info,
        brief=brief,
        age=age,
        height=height,
        weight=weight,
        hometown=hometown,
        current_location=current_location,
        initial_relationship=initial_relationship,
        dialogue_examples=dialogue_examples,
        speaking_style=speaking_style,
        personality_traits=personality_traits,
        opening_line=opening_line,
        em_llm=em_llm,
        search_settings=(settings or {}).get("search"),
        stream_output=stream_output_enabled(settings),
        segmented_reply=segmented_reply_enabled(settings),
        world_id=world_id,
    )
    character_dir = CHARACTERS_DIR / english_name  # 角色目录
    save_character(character)

    try:
        # 图片先保存，避免图片失败时已经初始化记忆库。
        from backend.character.state import save_state
        save_state(CHARACTERS_DIR, english_name, character.state)
        from backend.character.records import folders
        folders(CHARACTERS_DIR, english_name)
        for emotion, image_bytes in images_to_save.items():
            save_character_image(english_name, prepare_character_image(image_bytes), emotion)
        for emotion, video_bytes in (emotion_videos or {}).items():
            if emotion not in images_to_save or emotion not in EMOTIONS:
                raise ValueError("视频缺少对应的角色预览图")
            image_path = get_character_image_path(english_name, emotion)
            video_path = image_path.with_suffix(".mp4")
            if video_path.resolve() != video_path:
                raise ValueError("角色视频路径非法")
            video_path.write_bytes(video_bytes)
        if settings is not None or embedding_settings is not None:
            saved_settings = dict(settings or {})
            if embedding_settings is not None:
                embedding = dict(embedding_settings)
                embedding.setdefault("enabled", True)
                saved_settings["embedding"] = embedding
            save_settings(english_name, saved_settings)
        HistoryMemory.initialize_character_history(character)

        # 所有新角色都有 world 集合；没有记忆模型时保持空集合。
        from backend.memory.chromadb_init import init_world_collection
        init_world_collection(character_dir)
        from backend.memory.world import rebuild_world_for_character
        rebuild_world_for_character(character)

        # 只有用户同时填写了 Embedding 提供商和模型才建立向量记忆库；
        # 没有配置记忆模型的角色保持原来的纯文本总结记忆方式。
        if isinstance(embedding_settings, dict) and embedding_settings.get("enabled", True):
            embedding_provider = str(
                embedding_settings.get("provider") or ""
            ).strip()
            embedding_model = str(
                embedding_settings.get("model") or ""
            ).strip()
            if embedding_provider and embedding_model:
                init_chromadb(character_dir)
    except Exception:
        # description.json 已写入但图片、配置、历史归档或 ChromaDB 初始化失败，
        # 删除整个角色目录，避免留下“角色存在但记忆库缺失”的半成品。
        shutil.rmtree(character_dir, ignore_errors=True)
        raise

    CharacterRegistry.add(character)
    return character
