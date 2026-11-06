"""SoulHaven API 路由。

接口统一放在 /api 下：
- GET  /api/characters                              获取角色列表
- POST /api/characters                              创建角色
- GET  /api/characters/<english_name>/images/<emotion>.png 读取角色情绪形象图
- GET  /api/characters/<english_name>/messages      获取角色对话历史
- POST /api/characters/<english_name>/summarize     手动总结并压缩历史
- POST /api/characters/<english_name>/continue      无用户输入时继续接话
- POST /api/characters/<english_name>/clear         精确确认后清空聊天与记忆
- POST /api/chat                                    发送消息
- POST /api/characters/<english_name>/true-state    确认后查看已保存的真实状态
- GET/POST /api/characters/<english_name>/inner-voices 读取或生成结构化心声

角色对象由 CharacterRegistry 持有，字典键是角色英文名。
创建角色时，create_character 会把资料写入 characters/<英文名>/description.json，
把模型配置写入 settings.json，并直接注册到 CharacterRegistry 中。
"""

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.formparser import FormDataParser

from backend.api.history import read_markdown_messages, complete_display_history
from backend.chat.create_world import create_world, load_world, list_worlds, normalize_world, WORLD_ROOT, WORLD_LOCK
from backend.memory.world import rebuild_all_worlds
from PIL import Image, ImageOps, UnidentifiedImageError
import uuid

from backend.chat.get_character import (
    MAX_CHARACTER_IMAGE_BYTES,
    create_character,
    get_character_image_path,
    prepare_character_image,
    save_settings,
)
from backend.chat.outputs import EMOTIONS, normalize_emotion
from backend.chat.run import chat, continue_say
from backend.api.streaming import register_streaming_routes
from backend.memory.delete import delete_memory, CONFIRMATION_TEXT
from backend.llms.factory import build_llm
from backend.llms import llms_main
from backend.llms.llms_main import Character
from backend.memory.sum_up_history import HistoryMemory
from backend.tools.web_search import CustomSearchConfig

# 永久 user 记录带发送时间前缀，返回给前端展示时去掉。
_TIME_PREFIX_PATTERN = re.compile(r"^\*\*\*该信息发送时间：[^\n]*\*\*\*\n?")  # 时间前缀正则

# 创建角色时允许缺省的高级字段。缺省或空字符串会被转成 None。
OPTIONAL_DESCRIPTION_FIELDS = (  # 可选角色描述字段
    "age",
    "height",
    "weight",
    "hometown",
    "current_location",
    "initial_relationship",
    "dialogue_examples",
    "speaking_style",
    "personality_traits",
)


class _CharacterUploadParser(FormDataParser):
    """有请求体上限的上传使用内存，避免 Werkzeug 写用户 TEMP 目录。"""

    def __init__(self, **kwargs):
        kwargs["stream_factory"] = lambda **_: BytesIO()
        super().__init__(**kwargs)


def json_error(message: str, status_code: int):
    """统一生成 JSON 错误响应。

    Args:
        message: 返回给前端的错误说明。
        status_code: HTTP 状态码，例如 400、404、409、500。

    Returns:
        Flask 响应对象，内容为 {"error": message}。
    """
    return jsonify({"error": message}), status_code


def optional_text(data: dict[str, Any], key: str) -> str | None:
    """读取请求中的可选字符串字段。

    Args:
        data: 已解析的 JSON 请求字典。
        key: 要读取的字段名，例如 "age"。

    Returns:
        去掉首尾空白后的字符串；字段不存在、为 None 或为空字符串时，
        返回 None。
    """
    value = data.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def character_to_dict(character: Character) -> dict[str, Any]:
    """把 Character 对象转换成前端可用的公开字典。

    Args:
        character: 要转换的 Character 对象。

    Returns:
        包含英文名、中文名、性别、基本描述、高级字段和开场白的字典。
        不包含 llm、messages、API Key 等内部信息。
    """
    return {
        "english_name": character.english_name,
        "name": character.name,
        "gender": character.gender,
        "base_info": character.base_info,
        "brief": character.brief,
        "age": character.age,
        "height": character.height,
        "weight": character.weight,
        "hometown": character.hometown,
        "current_location": character.current_location,
        "initial_relationship": character.initial_relationship,
        "dialogue_examples": character.dialogue_examples,
        "speaking_style": character.speaking_style,
        "personality_traits": character.personality_traits,
        "opening_line": character.opening_line,
        "world_id": character.world_id,
        "stream_output": character.stream_output,
        "segmented_reply": character.segmented_reply,
    }


def create_api_blueprint(characters: dict[str, Any]) -> Blueprint:
    """创建 API 蓝图，并让所有路由共享同一个角色字典。

    Args:
        characters: “角色英文名 -> Character 对象”的字典。通常传入
            CharacterRegistry.characters，保证创建和查询使用同一份数据。

    Returns:
        配置好 /api 前缀和全部路由的 Flask Blueprint。
    """
    api = Blueprint("api", __name__, url_prefix="/api")
    register_streaming_routes(api, characters, json_error)

    def world_payload():
        if request.mimetype == "multipart/form-data":
            request.max_content_length = 2 * MAX_CHARACTER_IMAGE_BYTES + 1024 * 1024
            request.max_form_memory_size = None
            request.max_form_parts = 3
            request.form_data_parser_class = _CharacterUploadParser
            data = json.loads(request.form.get("data", ""))
            image = request.files.get("cover")
        else:
            data = request.get_json(silent=True)
            image = None
        world = normalize_world(data)
        cover = None
        if image and image.filename:
            raw = image.stream.read(10 * 1024 * 1024 + 1)
            if len(raw) > 10 * 1024 * 1024:
                raise ValueError("世界背景图片不能超过 10MB")
            if Path(image.filename).suffix.lower() == ".mp4":
                if len(raw) < 16 or raw[4:8] != b"ftyp":
                    raise ValueError("请选择有效的 MP4 视频")
                poster = request.files.get("cover_poster")
                if not poster:
                    raise ValueError("视频缺少预览图，请重新选择")
                cover = (prepare_character_image(poster.stream.read(MAX_CHARACTER_IMAGE_BYTES + 1)), raw)
            elif raw[:6] in (b"GIF87a", b"GIF89a"):
                cover = (prepare_character_image(raw), None)
            else:
                try:
                    with Image.open(BytesIO(raw)) as source:
                        if source.format not in {"PNG", "JPEG", "WEBP"} or source.width * source.height > 25_000_000:
                            raise ValueError("图片须为 PNG、JPEG、WebP 或 GIF，且不超过 2500 万像素")
                        source.load()
                        output = BytesIO()
                        ImageOps.exif_transpose(source).convert("RGB").save(output, format="PNG")
                        cover = (output.getvalue(), None)
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                    raise ValueError("世界背景图片无法读取") from exc
        return world, cover

    def public_world(world):
        identifier = world["id"]
        result = dict(world)
        result["cover_url"] = f"/api/worlds/{identifier}/cover"
        return result

    def save_world_cover(world_id, data):
        if data is None:
            return
        folder = WORLD_ROOT / world_id
        folder.mkdir(parents=True, exist_ok=True)
        image, video = data
        suffix = ".gif" if image[:6] in (b"GIF87a", b"GIF89a") else ".png"
        target = folder / ("background" + suffix)
        temp = folder / f".cover-{uuid.uuid4().hex}.tmp"
        video_temp = folder / f".cover-{uuid.uuid4().hex}.tmp"
        paths = [folder / ("background" + ext) for ext in (".png", ".gif", ".mp4")]
        previous = {path: path.read_bytes() if path.is_file() else None for path in paths}
        try:
            temp.write_bytes(image)
            if video is not None:
                video_temp.write_bytes(video)
            temp.replace(target)
            if video is not None:
                video_temp.replace(folder / "background.mp4")
            else:
                (folder / "background.mp4").unlink(missing_ok=True)
            (folder / ("background.gif" if suffix == ".png" else "background.png")).unlink(missing_ok=True)
        except OSError:
            for path, old in previous.items():
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    rollback = folder / f".cover-{uuid.uuid4().hex}.tmp"
                    try:
                        rollback.write_bytes(old)
                        rollback.replace(path)
                    finally:
                        rollback.unlink(missing_ok=True)
            raise
        finally:
            temp.unlink(missing_ok=True)
            video_temp.unlink(missing_ok=True)

    @api.get("/worlds")
    def worlds_list():
        try:
            return jsonify({"worlds": [public_world(w) for w in list_worlds()]})
        except (OSError, ValueError, json.JSONDecodeError):
            return json_error("世界观列表读取失败", 500)

    @api.get("/worlds/<world_id>")
    def world_get(world_id):
        try:
            return jsonify(public_world(load_world(world_id)))
        except (ValueError, OSError, json.JSONDecodeError):
            return json_error("世界观不存在或无法读取", 404)

    @api.get("/worlds/<world_id>/cover")
    def world_cover(world_id):
        try:
            load_world(world_id)
            target = WORLD_ROOT / world_id / "background.png"
            if not target.is_file():
                target = WORLD_ROOT / world_id / "background.gif"
            if not target.is_file():
                name = {"reality": "world_reality.png", "jianghu": "world_ink.png", "vampire": "world_vampire.png", "space": "world_space.png"}.get(world_id, "world_jianghu.png")
                target = Path(__file__).resolve().parents[2] / "web" / "pictures" / name
            return send_file(target, mimetype="image/gif" if target.suffix == ".gif" else "image/png", conditional=True)
        except (ValueError, OSError):
            return json_error("世界背景不存在", 404)

    @api.get("/worlds/<world_id>/video")
    def world_video(world_id):
        try:
            load_world(world_id)
            path = WORLD_ROOT / world_id / "background.mp4"
            if path.resolve() != path or not path.is_file():
                return json_error("世界背景视频不存在", 404)
            response = send_file(path, mimetype="video/mp4", conditional=True)
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        except (ValueError, OSError):
            return json_error("世界背景视频不存在", 404)

    @api.post("/worlds")
    def world_create():
        try:
            data, cover = world_payload()
            world = create_world(data)
            try:
                save_world_cover(world["id"], cover)
            except OSError:
                result = public_world(world)
                result["warning"] = "世界观已创建，但背景图保存失败，可重新编辑上传。"
                return jsonify(result), 201
            return jsonify(public_world(world)), 201
        except RequestEntityTooLarge:
            return json_error("背景文件或预览图过大", 413)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return json_error(str(exc), 400)
        except Exception:
            return json_error("世界观创建失败", 500)

    @api.put("/worlds/<world_id>")
    def world_update(world_id):
        try:
            load_world(world_id)
            data, cover = world_payload()
            with WORLD_LOCK:
                root = llms_main.CHARACTERS_DIR
                if root.is_dir():
                    missing = [p.name for p in root.iterdir() if p.is_dir() and (p / "description.json").is_file() and p.name not in characters]
                    if missing:
                        return json_error("有角色未能加载，无法同步全部世界观记忆库，请先检查角色加载情况。", 409)
                skipped = rebuild_all_worlds(list(characters.values()), world_id, data)
            warning = ""
            try:
                save_world_cover(world_id, cover)
            except OSError:
                warning = "世界观已保存，但背景图保存失败，请重新编辑上传。"
            return jsonify({"world": public_world(load_world(world_id)), "without_embedding": skipped, "warning": warning})
        except RequestEntityTooLarge:
            return json_error("背景文件或预览图过大", 413)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return json_error(str(exc), 400)
        except RuntimeError as exc:
            return json_error(str(exc), 500)
        except Exception:
            return json_error("世界观保存失败；请检查记忆模型后重试", 500)

    @api.get("/characters")
    def list_characters():
        """获取当前注册表中的全部角色。

        Args:
            无。角色来源是闭包中的 characters 字典。

        Returns:
            Flask JSON 响应：{"characters": [角色公开字段, ...]}。
        """
        return jsonify(
            {
                "characters": [
                    character_to_dict(character)
                    for character in characters.values()
                ]
            }
        )

    @api.route("/characters/<english_name>", methods=["GET", "PUT"])
    def character_description(english_name: str):
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        if request.method == "PUT":
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return json_error("角色资料必须是 JSON 对象", 400)
            try:
                llms_main.update_character_description(character, data)
            except ValueError as exc:
                return json_error(str(exc), 400)
            except OSError:
                return json_error("角色资料保存失败，请检查文件权限", 500)
            return jsonify({"description": data})
        try:
            root = llms_main.CHARACTERS_DIR.resolve()
            directory = (root / english_name).resolve()
            path = directory / llms_main.DESCRIPTION_FILENAME
            if directory.parent != root or path.is_symlink():
                raise ValueError("角色路径无效")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("角色资料格式错误")
            return jsonify({"description": data})
        except (OSError, ValueError):
            return json_error("无法读取角色资料", 404)

    @api.post("/characters")
    def create_character_api():
        """创建角色、写入角色文件，并注册到内存字典。

        Args:
            无显式参数。请求体为 JSON 对象，或 multipart/form-data 的
            data JSON 字符串与可选 image（平静）及 image_<情绪> 文件；
            每个 PNG/JPEG/GIF/MP4 最大 10MB，MP4 需附带预览图。包含 name、english_name、
            gender、base_info、provider、model，以及可选的 opening_line、
            高级字段、temperature、api_key、base_url。还支持可选的
            embedding_enabled、embedding_provider、embedding_model、
            embedding_api_key、embedding_base_url 和
            embedding_probabilistic_forgetting；启用并填写模型与
            提供商时，会初始化该角色的 ChromaDB 记忆库。智能搜索字段为
            search_enabled、search_provider、search_api_key、search_base_url、search_header。

        Returns:
            成功时返回 201 和 {"message": ..., "character": 角色公开字段}；
            参数错误返回 400，英文名重复返回 409，模型或写文件失败
            返回 500。
        """
        image_data = None
        emotion_images = {}
        emotion_videos = {}
        if request.mimetype == "multipart/form-data":
            # 每个情绪最多一张，限制总请求体和字段数量。
            request.max_content_length = (MAX_CHARACTER_IMAGE_BYTES * 2) * len(EMOTIONS) + 1024 * 1024
            request.max_form_parts = len(EMOTIONS) * 2 + 1
            request.form_data_parser_class = _CharacterUploadParser
            try:
                data = json.loads(request.form.get("data", ""))
                allowed_fields = {"image"} | {f"image_{emotion}" for emotion in EMOTIONS}
                poster_fields = {field + "_poster" for field in allowed_fields}
                if (set(request.files) - allowed_fields - poster_fields
                        or any(len(request.files.getlist(key)) != 1 for key in request.files)
                        or ("image" in request.files and "image_calm" in request.files)):
                    return json_error("角色形象图字段无效或情绪重复", 400)
                for field, uploaded in request.files.items():
                    if field in poster_fields:
                        continue
                    if not uploaded.filename:
                        continue
                    if Path(uploaded.filename).suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".mp4"}:
                        return json_error("角色形象仅支持 PNG / JPG / JPEG / GIF / MP4", 400)
                    content = uploaded.stream.read(MAX_CHARACTER_IMAGE_BYTES + 1)
                    if len(content) > MAX_CHARACTER_IMAGE_BYTES:
                        return json_error("每张角色形象图不能超过 10MB", 413)
                    if Path(uploaded.filename).suffix.lower() == ".mp4":
                        if len(content) < 16 or content[4:8] != b"ftyp":
                            return json_error("请选择有效的 MP4 视频", 400)
                        poster = request.files.get(field + "_poster")
                        if not poster:
                            return json_error("视频缺少预览图，请重新选择", 400)
                        emotion = "calm" if field == "image" else field.removeprefix("image_")
                        emotion_videos[emotion] = content
                        content = poster.stream.read(MAX_CHARACTER_IMAGE_BYTES + 1)
                    if field == "image":
                        image_data = content
                    else:
                        emotion_images[field.removeprefix("image_")] = content
            except RequestEntityTooLarge:
                return json_error("上传内容过大：每张图片不能超过 10MB，角色资料不能超过 500KB", 413)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return json_error("data 字段必须是合法的 JSON 对象", 400)
        else:
            data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("请求体必须是 JSON 对象", 400)

        name = str(data.get("name") or "").strip()
        english_name = str(data.get("english_name") or "").strip()
        gender = str(data.get("gender") or "").strip()
        base_info = str(data.get("base_info") or "").strip()
        world_id = data.get("world_id", "reality")
        if not isinstance(world_id, str):
            return json_error("请选择有效的世界观", 400)
        try:
            load_world(world_id)
        except (ValueError, OSError, json.JSONDecodeError):
            return json_error("选择的世界观不存在", 400)

        if not name:
            return json_error("角色名字不能为空", 400)
        if not english_name:
            return json_error("角色英文名不能为空", 400)
        if not gender:
            return json_error("角色性别不能为空", 400)
        if not base_info:
            return json_error("角色基本描述不能为空", 400)
        # 新表单要求简介；旧客户端没有此字段时保持兼容。
        if "brief" in data and (not isinstance(data["brief"], str) or not data["brief"].strip()):
            return json_error("角色简介不能为空", 400)
        brief = data["brief"].strip() if "brief" in data else None
        if brief and len(brief) > 500:
            return json_error("角色简介不能超过 500 字", 400)

        # Windows 文件夹名不区分大小写，这里也按不区分大小写检查重复。
        if any(
            existing_name.casefold() == english_name.casefold()
            for existing_name in characters
        ):
            return json_error("角色英文名已存在", 409)

        raw_temperature = data.get("temperature", 0.8)
        try:
            temperature = float(raw_temperature)
        except (TypeError, ValueError):
            return json_error("temperature 必须是数字", 400)
        if not 0 <= temperature <= 2:
            return json_error("temperature 必须在 0 到 2 之间", 400)

        optional_values = {
            field: optional_text(data, field)
            for field in OPTIONAL_DESCRIPTION_FIELDS  # 可选角色描述字段
        }

        stream_output = data.get("stream_output", False)
        if not isinstance(stream_output, bool):
            return json_error("stream_output 必须是布尔值", 400)

        # 模型配置会写入 settings.json，后续启动时用它恢复模型对象。
        settings = {
            "provider": str(data.get("provider") or "").strip().lower(),
            "model": str(data.get("model") or "").strip(),
            "temperature": temperature,
            "output": {"stream": stream_output},
            "api_key": str(data.get("api_key") or "").strip(),
            "base_url": str(data.get("base_url") or "").strip(),
        }

        search_enabled = data.get("search_enabled", False)
        if not isinstance(search_enabled, bool):
            return json_error("search_enabled 必须是布尔值", 400)
        if search_enabled:
            search_provider = data.get("search_provider")
            if search_provider not in ("deepseek", "custom"):
                return json_error("请选择 DeepSeek 或自定义智能搜索", 400)
            search_key = data.get("search_api_key")
            if not isinstance(search_key, str) or not search_key.strip():
                return json_error("请填写智能搜索 API Key", 400)
            search_key = search_key.strip()
            search_settings = {"enabled": True, "provider": search_provider, "api_key": search_key}
            if search_provider == "deepseek":
                if any(not 33 <= ord(char) <= 126 for char in search_key):
                    return json_error("DeepSeek 搜索 API Key 格式无效", 400)
            else:
                raw_base_url = data.get("search_base_url")
                raw_header = data.get("search_header")
                if raw_header is not None and not isinstance(raw_header, str):
                    return json_error("自定义请求头必须是 JSON 文本", 400)
                search_settings["base_url"] = raw_base_url.strip() if isinstance(raw_base_url, str) else ""
                search_settings["header"] = (raw_header or "").strip()
                try:
                    CustomSearchConfig.from_settings(search_settings)
                except ValueError as exc:
                    return json_error(str(exc), 400)
            settings["search"] = search_settings

        # Embedding 是可选的：只有启用且同时填写提供商和模型时，才初始化
        # ChromaDB。没有配置时完全不创建数据库，继续使用原来的总结记忆。
        raw_embedding_enabled = data.get("embedding_enabled", True)
        if not isinstance(raw_embedding_enabled, bool):
            return json_error("embedding_enabled 必须是布尔值", 400)
        probabilistic_forgetting = data.get("embedding_probabilistic_forgetting", False)
        if not isinstance(probabilistic_forgetting, bool):
            return json_error("embedding_probabilistic_forgetting 必须是布尔值", 400)

        embedding_provider = str(
            data.get("embedding_provider") or ""
        ).strip().lower()
        embedding_model = str(data.get("embedding_model") or "").strip()
        embedding_settings = None
        if (
            raw_embedding_enabled
            and embedding_provider
            and embedding_model
        ):
            embedding_settings = {
                "provider": embedding_provider,
                "model": embedding_model,
                "probabilistic_forgetting": probabilistic_forgetting,
                "api_key": str(
                    data.get("embedding_api_key") or ""
                ).strip(),
                "base_url": str(
                    data.get("embedding_base_url") or ""
                ).strip(),
            }

        try:
            llm = build_llm(settings)
            with WORLD_LOCK:
                character = create_character(
                    llm=llm,
                    name=name,
                    english_name=english_name,
                    gender=gender,
                    base_info=base_info,
                    world_id=world_id,
                    brief=brief,
                    opening_line=optional_text(data, "opening_line"),
                    settings=settings,
                    embedding_settings=embedding_settings,
                    image_data=image_data,
                    emotion_images=emotion_images,
                    emotion_videos=emotion_videos,
                    **optional_values,
                )
        except ValueError as exc:
            message = str(exc)
            status_code = 409 if message == "角色英文名已存在" else 400
            return json_error(message, status_code)
        except Exception as exc:
            return json_error("创建角色失败，请检查模型配置并重试", 500)

        return (
            jsonify(
                {
                    "message": "角色创建成功",
                    "character": character_to_dict(character),
                }
            ),
            201,
        )

    @api.get("/characters/<english_name>/images/<emotion>.png")
    def character_image(english_name: str, emotion: str):
        """只公开已注册角色的白名单情绪图片，不开放其他角色文件。"""
        if english_name not in characters:
            return json_error("角色图片不存在", 404)
        try:
            image_path = get_character_image_path(english_name, emotion)
            if not image_path.is_file():
                return json_error("角色图片不存在", 404)
            response = send_file(image_path, mimetype="image/gif" if image_path.suffix == ".gif" else "image/png", conditional=True)
        except (ValueError, OSError):
            return json_error("角色图片不存在或无法读取", 404)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @api.get("/characters/<english_name>/images/<emotion>/video")
    def character_video(english_name: str, emotion: str):
        if english_name not in characters:
            return json_error("角色视频不存在", 404)
        try:
            path = get_character_image_path(english_name, emotion).with_suffix(".mp4")
            if path.resolve() != path or not path.is_file():
                return json_error("角色视频不存在", 404)
            response = send_file(path, mimetype="video/mp4", conditional=True)
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
        except (ValueError, OSError):
            return json_error("角色视频不存在", 404)

    @api.get("/characters/<english_name>/image/calm.png")
    def legacy_character_image(english_name: str):
        """兼容旧版调用平静形象的地址。"""
        return character_image(english_name, "calm")

    @api.get("/characters/<path:english_name>/messages")
    def list_messages(english_name: str):
        """获取角色的聊天历史。

        Args:
            english_name: URL 路径中的角色英文名。

        Returns:
            成功时返回 messages、has_more、next_before；默认最近 100 条，
            limit 最大 100，before 为加载更早记录的游标。
            优先从 original.json 读取完整记录，过滤 is_summary 的总结
            user，保留总结前的所有前端记录；JSON 不可用时读取 original.md，
            JSON 仅含部分轮次且可与 Markdown 对齐时补齐更早记录；
            两种归档均不可用时回退到内存消息。
            只包含 user 和 assistant 消息，并去掉 user 消息前的发送时间
            前缀；assistant 消息有思考内容时会附带 reasoning_content；
            角色不存在时返回 404。
        """
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在，请先创建角色", 404)

        try:
            limit = int(request.args.get("limit", "100"))
            before = request.args.get("before")
            before = int(before) if before is not None else None
            if not 1 <= limit <= 100 or (before is not None and before < 0):
                raise ValueError
        except ValueError:
            return json_error("limit 必须为 1–100，before 必须为非负整数", 400)

        messages = []
        # 与聊天/总结共用角色锁，避免读到总结重置过程中的半截消息列表。
        with character.operation_lock:
            # 前端展示完整原始聊天记录；总结 user 只用于模型上下文，不展示。
            display_messages = HistoryMemory.load_display_messages(character)
            markdown_path, _, _ = HistoryMemory._get_paths(character.english_name)
            root = llms_main.CHARACTERS_DIR.resolve()
            character_dir = (root / character.english_name).resolve()
            if character_dir.parent == root and markdown_path.resolve().is_relative_to(character_dir):
                display_messages = complete_display_history(display_messages, read_markdown_messages(markdown_path))
            if display_messages is None:
                # Empty originals are the persistent result of an explicit clear.
                json_path = HistoryMemory._get_paths(character.english_name)[1]
                if (character_dir.parent == root and markdown_path.resolve().is_relative_to(character_dir)
                    and json_path.resolve().is_relative_to(character_dir)
                    and markdown_path.is_file() and json_path.is_file()
                    and markdown_path.stat().st_size == 0 and json_path.stat().st_size == 0):
                    display_messages = []
                else:
                    display_messages = character.messages

            for message in display_messages:
                role = message.get("role")
                if role not in ("user", "assistant"):
                    continue
                if message.get("is_summary"):
                    continue

                content = str(message.get("content") or "")
                if role == "user":
                    content = _TIME_PREFIX_PATTERN.sub(  # 时间前缀正则
                        "", content, count=1
                    )

                if not content:
                    continue

                message_data = {"role": role, "content": content}
                if role == "assistant":
                    reasoning_content = message.get("reasoning_content")
                    if (
                        isinstance(reasoning_content, str)
                        and reasoning_content.strip()
                    ):
                        message_data["reasoning_content"] = reasoning_content
                messages.append(message_data)

        if before is not None and before > len(messages):
            return json_error("历史记录已变化，请重新打开角色", 409)
        end = len(messages) if before is None else before
        start = max(0, end - limit)
        response = jsonify({"messages": messages[start:end], "has_more": start > 0,
                            "next_before": start if start > 0 else None})
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.post("/characters/<english_name>/clear")
    def clear_character_history(english_name: str):
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get("confirmation") != CONFIRMATION_TEXT:
            return json_error("请输入完整确认文字：" + CONFIRMATION_TEXT, 400)
        try:
            delete_memory(character, data["confirmation"])
        except ValueError as exc:
            return json_error(str(exc), 400)
        except Exception:
            return json_error("清空未全部完成，请检查文件和数据库后重试", 500)
        return jsonify({"message": "已清空聊天记录与记忆，保留开场白", "messages": [{"role": "assistant", "content": character.opening_line}]})

    @api.post("/characters/<english_name>/rebuild-memory")
    def rebuild_character_memory(english_name):
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get('confirmed') is not True:
            return json_error('请确认重建记忆库', 400)
        from backend.memory.rebuild import rebuild_memory
        try:
            counts = rebuild_memory(character)
        except ValueError as exc:
            return json_error(str(exc), 400)
        except RuntimeError as exc:
            # Only our own controlled messages are safe to show; provider errors may contain keys.
            message = str(exc)
            if message.startswith('记忆库重建失败') or message.startswith('重建失败且原记忆库'):
                return json_error(message, 500)
            return json_error('记忆库重建失败，请检查模型与记忆库；聊天和摘要文件已保留', 500)
        except Exception:
            return json_error('记忆库重建失败，请检查模型与记忆库；聊天和摘要文件已保留', 500)
        return jsonify({'message': '记忆库已重建', **counts})

    @api.post("/characters/<english_name>/continue")
    def continue_character(english_name: str):
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("请求体必须是 JSON 对象", 400)
        recognition = data.get("recognition_time", True)
        thinking = data.get("deep_thinking", True)
        if not isinstance(recognition, bool) or not isinstance(thinking, bool):
            return json_error("对话开关必须是布尔值", 400)
        if character.llm is None:
            return json_error("该角色尚未配置模型", 400)
        try:
            result = continue_say(character, recognition, thinking)
        except OSError:
            return json_error("续说归档失败，请重试", 500)
        except Exception:
            return json_error("角色续说失败，请稍后重试", 502)
        response = {"content": result.get("content", ""), "the_choice_of_emotion": normalize_emotion(result.get("the_choice_of_emotion"))}
        if result.get("reasoning_content"):
            response["reasoning_content"] = result["reasoning_content"]
        return jsonify(response)

    @api.post("/characters/<path:english_name>/summarize")
    def summarize_history(english_name: str):
        """手动总结角色历史，压缩上下文并追加 summary user。

        Args:
            english_name: URL 路径中的角色英文名。

        Returns:
            成功时返回 {"message": "历史总结完成", "summary": 摘要}。
            角色不存在返回 404；角色没有模型或没有可总结内容返回 400；
            模型调用失败返回 502；文件写入失败返回 500。
        """
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在，请先创建角色", 404)
        if character.llm is None:
            return json_error("该角色尚未配置模型，无法总结历史", 400)

        try:
            # 同一角色的总结与聊天必须串行；否则总结重置 messages 时可能
            # 覆盖掉刚发送的一轮对话。
            with character.operation_lock:
                summary = HistoryMemory.sum_up_history(
                    character.messages,
                    character,
                )
        except ValueError as exc:
            return json_error(str(exc), 400)
        except OSError as exc:
            return json_error(f"历史归档写入失败：{exc}", 500)
        except Exception as exc:
            return json_error(f"历史总结失败：{exc}", 502)

        return jsonify(
            {
                "message": "历史总结完成",
                "summary": summary,
            }
        )

    @api.put("/characters/<english_name>/reply-settings")
    def update_reply_settings(english_name):
        """按角色保存分段开关，合并 output，保留其他配置与密钥编码。"""
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not isinstance(data.get("segmented_reply"), bool):
            return json_error("segmented_reply 必须是布尔值", 400)
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        try:
            with character.operation_lock:
                save_settings(english_name, {"output": {"segmented": data["segmented_reply"]}})
                character.segmented_reply = data["segmented_reply"]
        except (OSError, ValueError, TypeError):
            return json_error("分段回复设置保存失败，请重试", 500)
        return jsonify({"segmented_reply": character.segmented_reply})

    @api.post("/chat")
    def chat_api():
        """发送一条用户消息，只返回模型回复。

        Args:
            无显式参数。请求体必须是 JSON 对象，包含 english_name 和
            message，可选 recognition_time（默认 True）和 deep_thinking
            （默认 True），以及 segmented_reply（省略沿用角色设置）。

        Returns:
            成功时返回 {"content": 模型回复}，有思考内容时附带
            reasoning_content；分段模式另含 segments 数组。参数错误、角色不存在、角色没有模型配置时
            返回 400 或 404；模型调用失败返回 502。
        """
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("请求体必须是 JSON 对象", 400)

        english_name = str(data.get("english_name") or "").strip()
        message = data.get("message")
        recognition_time = data.get("recognition_time", True)
        deep_thinking = data.get("deep_thinking", True)
        segmented_reply = data.get("segmented_reply")

        if not english_name:
            return json_error("角色英文名不能为空", 400)
        if not isinstance(message, str) or not message.strip():
            return json_error("message 不能为空", 400)
        if not isinstance(recognition_time, bool):
            return json_error("recognition_time 必须是布尔值", 400)
        if not isinstance(deep_thinking, bool):
            return json_error("deep_thinking 必须是布尔值", 400)
        if "segmented_reply" in data and not isinstance(segmented_reply, bool):
            return json_error("segmented_reply 必须是布尔值", 400)

        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在，请先创建角色", 404)
        if character.llm is None:
            return json_error("该角色尚未配置模型，请重新创建角色或配置模型", 400)

        try:
            # 与总结接口共用同一把角色锁，保证消息列表和归档顺序一致。
            with character.operation_lock:
                result = chat(character, message, recognition_time, deep_thinking, segmented_reply)
        except OSError as exc:
            return json_error(f"历史归档写入失败：{exc}", 500)
        except Exception as exc:
            if character.english_name == "assistant":
                print(
                    "[SoulHaven] 小助手请求失败：请确认 Ollama 已启动，"
                    "并且已安装 qwen3:8b 模型（ollama pull qwen3:8b）。"
                    f"错误：{exc}"
                )
            return json_error(f"模型调用失败：{exc}", 502)

        # content 是聊天正文；reasoning_content 由前端折叠显示。
        response_data = {"content": result.get("content", ""), "the_choice_of_emotion": normalize_emotion(result.get("the_choice_of_emotion"))}
        if "segments" in result:
            response_data["segments"] = result["segments"]
        reasoning_content = result.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            response_data["reasoning_content"] = reasoning_content
        return jsonify(response_data)

    @api.get("/characters/<english_name>/state")
    def character_state(english_name):
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        with character.operation_lock:
            response = jsonify({key: character.state[key] for key in ("external_mood", "external_mood_intensity", "the_choice_of_emotion")})
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.route("/characters/<english_name>/inner-voices", methods=["GET", "POST"])
    def inner_voices(english_name):
        from backend.chat.inner_voice import send_inner_voice
        from backend.character.records import folders, list_records
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        try:
            if request.method == "POST":
                if character.llm is None:
                    return json_error("该角色尚未配置模型", 400)
                name = send_inner_voice(character)
                return jsonify({"message": "心声已发送，请点击查看心声阅读", "id": name})
            with character.operation_lock:
                voices, _ = folders(llms_main.CHARACTERS_DIR, english_name)
                records = list_records(voices)
            response = jsonify({"voices": [{key: item[key] for key in ("id", "created_at", "content", "letter") if key in item} for item in records]})
            response.headers["Cache-Control"] = "no-store"
            return response
        except (ValueError, OSError):
            return json_error("心声生成或记录读取失败，请重试；原有记录已保留", 500)
        except Exception:
            return json_error("心声模型请求失败，请稍后重试", 502)

    @api.post("/characters/<english_name>/true-state")
    def character_true_state(english_name):
        """用户明确接受查看提醒后，返回已保存的真实状态，不生成心声。"""
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get("acknowledged") is not True:
            return json_error("请先确认是否愿意查看角色的真实状态", 400)
        from backend.character.state import persistent_state
        with character.operation_lock:
            response = jsonify({"name": character.name, "state": persistent_state(character.state)})
        response.headers["Cache-Control"] = "no-store"
        return response

    return api
