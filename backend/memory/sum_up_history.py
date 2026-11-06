"""历史记录总结与归档。

作用：
1. 在角色创建时建立 history/original 和 history/digest 目录；
2. 把开场白先写入 original.md 和 original.json；
3. 每轮模型成功回复后，把本轮 user 和 assistant 追加到 original 文件；
4. 总结时不再批量归档将被删除的消息，只把摘要写入 digest.md，并单独
   不向 original 文件或 original 集合写入摘要；
5. 启动时从 original.json 找到最后一次总结边界并恢复上下文；
6. 清空原消息列表，只保留 system 和一条摘要 user。

original.json 采用 JSON Lines：每个字典占一行，只追加，不覆盖。
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from backend.llms.llms_main import CHARACTERS_DIR, Character  # 角色目录、角色类


class HistoryMemory:
    """角色历史归档、摘要和启动恢复管理器。

    所有功能都封装为类方法。外部主要通过 initialize_character_history()
    建立归档，通过 sum_up_history() 完成总结，通过 load_messages() 恢复
    上下文。
    """

    HISTORY_DIR_NAME = "history"  # 历史目录名
    ORIGINAL_DIR_NAME = "original"  # 原始记录目录名
    DIGEST_DIR_NAME = "digest"  # 摘要目录名
    ORIGINAL_MD_FILENAME = "original.md"  # 原始 Markdown 文件名
    ORIGINAL_JSON_FILENAME = "original.json"  # 原始 JSON 文件名
    DIGEST_FILENAME = "digest.md"  # 摘要记录文件名
    DIGEST_HEADING_SUFFIX = "记忆总结摘要"  # 摘要标题后缀（前面带日期时间）

    # 总结请求最后追加的 user 指令；明确要求不要总结 system 内容。
    SUMMARY_INSTRUCTION = (  # 总结指令
        "请总结以上对话中发生的事。只总结 user 和 assistant 的聊天内容，"
        "不要总结 system 提示词、角色设定或系统指令。保留关键事件、"
        "人物关系变化、约定和重要细节，用简洁的中文段落输出。"
    )

    @classmethod
    def _get_dirs(cls, english_name: str) -> tuple[Path, Path]:
        """返回角色历史目录下的 original 和 digest 目录。

        Args:
            english_name: 角色英文名，也是角色文件夹名。

        Returns:
            (original 目录, digest 目录)。
        """
        history_dir = CHARACTERS_DIR / english_name / cls.HISTORY_DIR_NAME  # 角色目录 / 历史目录名
        return (
            history_dir / cls.ORIGINAL_DIR_NAME,  # 原始记录目录名
            history_dir / cls.DIGEST_DIR_NAME,  # 摘要目录名
        )

    @classmethod
    def _get_paths(cls, english_name: str) -> tuple[Path, Path, Path]:
        """返回 original.md、original.json 和 digest.md 的路径。

        Args:
            english_name: 角色英文名，也是角色文件夹名。

        Returns:
            (original.md 路径, original.json 路径, digest.md 路径)。
        """
        original_dir, digest_dir = cls._get_dirs(english_name)
        return (
            original_dir / cls.ORIGINAL_MD_FILENAME,  # 原始 Markdown 文件名
            original_dir / cls.ORIGINAL_JSON_FILENAME,  # 原始 JSON 文件名
            digest_dir / cls.DIGEST_FILENAME,  # 摘要记录文件名
        )

    @classmethod
    def _format_messages(cls, messages: list[dict[str, Any]]) -> str:
        """把 user 和 assistant 消息格式化成 Markdown 归档文本。

        Args:
            messages: 角色消息列表，通常来自 Character.messages。system 消息
                会被跳过，其余只保留 user 和 assistant。

        Returns:
            形如 "# user\\n内容\\n# assistant\\n内容\\n" 的文本；没有可写入
            的消息时返回空字符串。
        """
        blocks: list[str] = []

        for message in messages:
            role = message.get("role")
            if role not in ("user", "assistant"):
                continue

            content = str(message.get("content") or "").strip()
            if not content:
                continue

            blocks.append(f"# {role}\n{content}")

        if not blocks:
            return ""

        return "\n".join(blocks) + "\n"

    @classmethod
    def _append_text(cls, path: Path, text: str) -> None:
        """把文本追加到文件，并在已有内容后留一个空行。

        Args:
            path: 要追加的文件路径。
            text: 要写入的文本。

        Returns:
            None。

        Raises:
            OSError: 创建父目录或写入文件失败。
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        needs_separator = path.exists() and path.stat().st_size > 0
        with path.open("a", encoding="utf-8") as target_file:
            if needs_separator:
                target_file.write("\n")
            target_file.write(text)

    @classmethod
    def _append_json_lines(
        cls,
        path: Path,
        messages: list[dict[str, Any]],
    ) -> None:
        """按 JSON Lines 追加消息字典，每个字典一行。

        Args:
            path: original.json 路径。
            messages: 要追加的消息字典列表。

        Returns:
            None。

        Raises:
            OSError: 创建父目录或写入文件失败。
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as target_file:
            for message in messages:
                target_file.write(
                    json.dumps(message, ensure_ascii=False) + "\n"
                )

    @classmethod
    def initialize_character_history(cls, character: Character) -> None:
        """创建角色历史目录，并写入开场白。

        该方法可以重复调用。只有 original.md、original.json 不存在或为空时
        才写入开场白，因此不会破坏已有归档。

        Args:
            character: 要建立历史档案的角色对象。

        Returns:
            None。

        Side Effects:
            - 创建 history/original 和 history/digest；
            - original.md、original.json 为空时写入开场白；
            - digest.md 不存在时创建空文件。
        """
        original_dir, digest_dir = cls._get_dirs(character.english_name)
        original_dir.mkdir(parents=True, exist_ok=True)
        digest_dir.mkdir(parents=True, exist_ok=True)

        original_md_path, original_json_path, digest_path = cls._get_paths(
            character.english_name
        )
        opening_message = {
            "role": "assistant",
            "content": character.opening_line,
        }

        if not original_md_path.exists() or original_md_path.stat().st_size == 0:
            md_text = cls._format_messages([opening_message])
            if md_text:
                cls._append_text(original_md_path, md_text)

        if (
            not original_json_path.exists()
            or original_json_path.stat().st_size == 0
        ):
            cls._append_json_lines(
                original_json_path,
                [opening_message],
            )

        if not digest_path.exists():
            digest_path.touch()

    @classmethod
    def _append_original_messages(
        cls,
        character: Character,
        messages: list[dict[str, Any]],
    ) -> tuple[Path, Path]:
        """把一组 user/assistant 消息追加到 original.md 和 original.json。

        这是原始归档的唯一写入入口；调用方负责保证 messages 是尚未归档的
        新内容，避免重复写入。

        Args:
            character: 当前角色。
            messages: 要追加的 user/assistant 消息列表。

        Returns:
            (original.md 路径, original.json 路径)。

        Raises:
            OSError: 创建目录或写入文件失败。
        """
        cls.initialize_character_history(character)
        original_md_path, original_json_path, _ = cls._get_paths(
            character.english_name
        )

        md_text = cls._format_messages(messages)
        if md_text:
            cls._append_text(original_md_path, md_text)

        cls._append_json_lines(original_json_path, messages)
        return original_md_path, original_json_path

    @classmethod
    def archive_latest_round(cls, character: Character) -> tuple[Path, Path]:
        """把 character.messages 最后两条 user + assistant 写入原始归档。

        每轮模型成功回复后调用一次。只写最后两条，不重复写开场白或历史
        轮次。调用前必须保证最后两条确实是一轮完整的 user -> assistant。
        两个文件归档成功后，如果角色绑定了 em_llm，则将同格式的整轮
        Markdown 作为一个向量写入 original 集合；向量失败不回滚文件。

        Args:
            character: 当前角色，messages 最后两条是本轮对话。

        Returns:
            (original.md 路径, original.json 路径)。

        Raises:
            ValueError: 消息不足两条，或最后两条不是 user + assistant。
            OSError: 创建目录或写入文件失败。
        """
        messages = character.messages
        if len(messages) < 2:
            raise ValueError("没有完整的本轮对话可归档")

        latest_round = messages[-2:]
        roles = [message.get("role") for message in latest_round]
        if roles != ["user", "assistant"]:
            raise ValueError("本轮对话的最后两条必须是 user 和 assistant")

        if not str(latest_round[1].get("content") or "").strip():
            raise ValueError("assistant 回复为空，不能归档本轮对话")

        with character.operation_lock:
            paths = cls._append_original_messages(character, latest_round)
            if character.em_llm is not None:
                # 与 original.md 使用同一个格式化函数；一轮 user + assistant
                # 作为一份文档、一个向量。Chroma 失败不影响已写入的历史。
                from backend.memory.add_in_chromadb import ChromadbAppend

                try:
                    ChromadbAppend.append(character, cls._format_messages(latest_round))
                except Exception as exc:
                    print(f"[SoulHaven] Chroma 追加失败，文本历史已保留：{exc}")
            return paths

    @classmethod
    def _write_digest_history(cls, english_name: str, summary: str) -> str:
        """把本轮摘要追加写入 digest.md。

        Args:
            english_name: 角色英文名。
            summary: 模型生成的摘要文本，不能为空。

        Returns:
            本次写入 digest.md 的完整 Markdown 文本（含时间标题）。

        Raises:
            ValueError: 摘要为空。
            OSError: 创建目录或写入文件失败。
        """
        digest_text = summary.strip()
        if not digest_text:
            raise ValueError("摘要不能为空")

        _, _, digest_path = cls._get_paths(english_name)
        timestamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
        heading = f"# {timestamp}{cls.DIGEST_HEADING_SUFFIX}"
        markdown = f"{heading}\n{digest_text}\n"
        cls._append_text(digest_path, markdown)
        return markdown

    @classmethod
    def _read_original_records(
        cls,
        character: Character,
    ) -> list[dict[str, Any]] | None:
        """读取并校验 original.json 的全部记录。

        Args:
            character: 要读取归档的角色对象。

        Returns:
            全部 user/assistant 记录；文件不存在、为空或读取失败时返回 None。
            读取失败会打印警告。
        """
        _, original_json_path, _ = cls._get_paths(character.english_name)
        if not original_json_path.is_file():
            return None

        try:
            records: list[dict[str, Any]] = []
            for line in original_json_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("original.json 每一行必须是对象")
                role = message.get("role")
                if role not in ("user", "assistant"):
                    raise ValueError("original.json 只允许 user 和 assistant")
                if not isinstance(message.get("content"), str):
                    raise ValueError("original.json 的 content 必须是字符串")
                records.append(message)

            return records or None
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            print(
                "[SoulHaven] 历史归档读取失败 "
                f"{character.english_name}：{exc}"
            )
            return None

    @classmethod
    def load_display_messages(
        cls,
        character: Character,
    ) -> list[dict[str, Any]] | None:
        """读取用于前端展示的原始聊天记录。

        与 load_messages() 的“从 JSON 最后总结标记恢复”不同，本方法返回
        original.json 中的全部轮次，并过滤掉 is_summary 标记的总结消息。
        这样总结只影响模型上下文，不会让前端已有记录消失或显示摘要。

        Args:
            character: 要读取归档的角色对象。

        Returns:
            全部 user/assistant 记录（不含 summary user）；归档不存在或
            读取失败时返回 None，由调用方决定是否回退到内存消息。
        """
        records = cls._read_original_records(character)
        if records is None:
            return None
        return [
            message
            for message in records
            if not message.get("is_summary")
        ]

    @classmethod
    def load_messages(cls, character: Character) -> bool:
        """从 original.json 恢复最后一次归档后的上下文。

        优先从最后一条 is_summary 标记恢复 system + 摘要 + 后续对话。
        旧角色没有标记时兼容连续 user 的总结边界；没有边界时加载全部记录。

        Args:
            character: 要恢复消息的角色对象。

        Returns:
            True 表示已用归档内容替换 character.messages；False 表示文件
            不存在、为空或读取失败，原 messages 保持不变。

        Raises:
            None。读取失败会打印警告并返回 False。
        """
        records = cls._read_original_records(character)
        if not records:
            return False

        # 优先使用最后一条明确的总结标记；总结后立即重启也能恢复。
        for index in range(len(records) - 1, -1, -1):
            if records[index].get("role") == "user" and records[index].get("is_summary"):
                character.messages[:] = [character.messages[0], *records[index:]]
                return True

        start_index = 0
        for index in range(len(records) - 1, 0, -1):
            if (
                records[index].get("role") == "user"
                and records[index - 1].get("role") == "user"
            ):
                start_index = index - 1
                break

        restored = records[start_index:]
        system_message = character.messages[0]
        character.messages[:] = [system_message, *restored]
        return True

    @classmethod
    def sum_up_history(
        cls,
        messages: list[dict[str, Any]],
        character: Character,
    ) -> str:
        """总结对话，归档 digest 与 JSON 总结标记，并用摘要重置角色消息。

        Args:
            messages: 要总结并重置的消息列表，通常直接传 character.messages。
                该列表会被原地修改。
            character: 要总结的 Character 对象。函数使用 character.llm 发送
                总结请求，并使用 character.english_name 定位历史目录。

        Returns:
            模型返回的摘要文本。

        Raises:
            ValueError: 消息列表为空、第一条不是 system 消息、没有可总结的
                对话、角色没有可用模型，或模型返回空摘要。
            OSError: 创建 digest 目录或写入 digest.md / original.json 失败。

        Side Effects:
            - 创建 digest 目录；
            - 向 digest.md 追加带时间标题的摘要；
            - 仅向 original.json 追加带 is_summary 标记的 user；
            - 启用 Embedding 时将带时间标题的摘要写入 digest 集合；
            - 将 messages 原地替换为 [原 system 消息, 摘要 user 消息]。
        """
        if not messages:
            raise ValueError("消息列表不能为空")
        if messages[0].get("role") != "system":
            raise ValueError("消息列表第一条必须是 system 消息")
        if character.llm is None:
            raise ValueError("角色没有可用的模型，无法总结历史")

        # 复制后过滤 system，确保模型看不到、也不会总结系统提示词。
        summary_messages = [
            {
                "role": message.get("role"),
                "content": str(message.get("content") or ""),
            }
            for message in messages
            if message.get("role") in ("user", "assistant")
        ]
        if not summary_messages:
            raise ValueError("没有可总结的 user 或 assistant 消息")

        summary_messages.append(
            {
                "role": "user",
                "content": cls.SUMMARY_INSTRUCTION,  # 总结指令
            }
        )

        # 先拿到摘要；失败时原消息列表保持不变。
        result = character.invoke(summary_messages)
        summary = str(result.get("content") or "").strip()
        if not summary:
            raise ValueError("模型返回了空摘要，未清空历史")

        # 按 system + 开场白/上一条摘要 + N 轮的结构计算本次压缩轮数。
        compressed_rounds = max((len(messages) - 2) // 2, 0)

        # 摘要正文只写 digest 文件和集合；JSON 单独保存 summary user。
        _, digest_dir = cls._get_dirs(character.english_name)
        digest_dir.mkdir(parents=True, exist_ok=True)
        markdown = cls._write_digest_history(character.english_name, summary)

        # summary user 是持久化记忆边界，必须写入 original.json；
        # original.md 和 original 集合只保存真实 user/assistant 对话轮次。
        _, original_json_path, _ = cls._get_paths(character.english_name)
        cls._append_json_lines(
            original_json_path,
            [{"role": "user", "content": summary, "is_summary": True}],
        )

        # 只保留原来的 system 消息，再加入摘要 user 消息。
        system_message = messages[0]
        messages[:] = [
            system_message,
            {
                "role": "user",
                "content": summary,
                "is_summary": True,
            },
        ]

        if character.em_llm is not None:
            try:
                from backend.memory.add_in_chromadb import ChromadbAppend

                ChromadbAppend.append(character, markdown, collection_name="digest")
            except Exception as exc:
                print(f"[SoulHaven] 摘要向量追加失败，digest 文件已保留：{exc}")

        print(
            f"[SoulHaven] {character.name} 本次总结压缩了"
            f"{compressed_rounds}轮对话"
        )
        return summary
