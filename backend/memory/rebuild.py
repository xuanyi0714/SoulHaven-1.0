"""使用原始历史重建已有集合；源文件只读，不重新创建数据库。"""

import json
import math
import re
from pathlib import Path

from backend.memory import chromadb_init
from backend.memory.sum_up_history import HistoryMemory

_HEADING = re.compile(r"^# \d{4}-\d{2}-\d{2} \d{2}:\d{2}记忆总结摘要[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
BATCH_SIZE = 32


def split_digest(text):
    starts, offset, fence = [], 0, None
    for line in text.splitlines(keepends=True):
        clean = line.rstrip('\r\n')
        marker = _FENCE.match(clean)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif marker:
            fence = marker[1]
        elif _HEADING.fullmatch(clean):
            starts.append(offset)
        offset += len(line)
    if text.strip() and (not starts or text[:starts[0]].strip()):
        raise ValueError("摘要文件格式无法识别，未执行重建")
    return [text[start:(starts[i+1] if i+1 < len(starts) else len(text))].rstrip() + "\n"
            for i, start in enumerate(starts)]


def split_original(records, opening_line):
    result, pending = [], None
    for index, item in enumerate(records):
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant') or not isinstance(item.get('content'), str):
            raise ValueError("原始记录格式无效，未执行重建")
        if item.get('is_summary'):
            if pending is not None:
                raise ValueError("总结前存在未完成的对话，未执行重建")
            continue
        if not item['content'].strip():
            raise ValueError("原始记录存在空消息，未执行重建")
        if item['role'] == 'user':
            if pending is not None:
                raise ValueError("原始记录存在连续用户消息，未执行重建")
            pending = item
        elif pending is not None:
            result.append(HistoryMemory._format_messages([pending, item]))
            pending = None
        elif index != 0 or item['content'].strip() != str(opening_line or '').strip():
            result.append(HistoryMemory._format_messages([item]))
    if pending is not None:
        raise ValueError("原始记录存在未完成的对话，未执行重建")
    return result


def _clear(collection):
    while True:
        ids = collection.get(limit=1000, include=[])['ids']
        if not ids:
            break
        collection.delete(ids=ids)


def _restore(collection, snapshot):
    for i, identifier in enumerate(snapshot['ids']):
        kwargs = {'ids': [identifier], 'embeddings': [[float(x) for x in snapshot['embeddings'][i]]]}
        if snapshot['documents'][i] is not None:
            kwargs['documents'] = [snapshot['documents'][i]]
        if snapshot['metadatas'][i] is not None:
            kwargs['metadatas'] = [snapshot['metadatas'][i]]
        collection.upsert(**kwargs)


def rebuild_memory(character):
    """锁定角色，先校验和嵌入，再重建 digest/original；失败尝试恢复原集合。"""
    from backend.chat.get_character import load_settings
    from backend.llms import llms_main
    with character.operation_lock:
        settings = load_settings(character.english_name) or {}
        embedding = settings.get('embedding') or {}
        if not isinstance(embedding, dict) or not embedding.get('enabled') or character.em_llm is None:
            raise ValueError('该角色未启用或无法使用记忆模型')
        folder = chromadb_init.get_chroma_client_dir(character.english_name)
        if folder.is_symlink() or folder.resolve().parent != chromadb_init.DATABASE_DIR.resolve() or not folder.is_dir() or not (folder / 'chroma.sqlite3').is_file():
            raise ValueError('角色记忆库不存在，无法重建')
        original_md, original_json, digest_path = HistoryMemory._get_paths(character.english_name)
        role_dir = (llms_main.CHARACTERS_DIR / character.english_name).resolve()
        if role_dir.parent != llms_main.CHARACTERS_DIR.resolve() or not digest_path.is_file() or digest_path.is_symlink() or not digest_path.resolve().is_relative_to(role_dir):
            raise ValueError('角色摘要文件不存在或路径无效，无法安全重建')
        for path in (original_md, original_json):
            if path.is_symlink() or (path.exists() and not path.resolve().is_relative_to(role_dir)):
                raise ValueError('原始记录路径无效，无法安全重建')
        if not original_json.is_file() and not original_md.is_file():
            raise ValueError('原始记录不存在，无法安全重建')
        try:
            records = [json.loads(line) for line in original_json.read_text(encoding='utf-8').splitlines() if line.strip()] if original_json.is_file() else []
            digest_chunks = split_digest(digest_path.read_text(encoding='utf-8'))
        except (UnicodeError, json.JSONDecodeError, OSError) as exc:
            raise ValueError('历史文件读取失败，未执行重建') from exc
        split_original(records, character.opening_line)
        # Avoid silently losing Markdown-only history when a JSON archive is partial.
        if original_md.is_file():
            from backend.api.history import read_markdown_messages, complete_display_history
            md = read_markdown_messages(original_md)
            structured = [r for r in records if not r.get('is_summary')]
            if md is None:
                try:
                    if original_md.read_text(encoding='utf-8').strip():
                        raise ValueError('原始 Markdown 无法解析，未执行重建')
                except (OSError, UnicodeError) as exc:
                    raise ValueError('原始 Markdown 无法读取，未执行重建') from exc
            if md and len(md) > len(structured):
                merged = complete_display_history(structured, md)
                if len(merged) != len(md):
                    raise ValueError('原始 JSON 与 Markdown 不一致，无法安全重建')
                records = merged
        chunks = {'original': split_original(records, character.opening_line), 'digest': digest_chunks}
        import chromadb
        client = chromadb.PersistentClient(path=str(folder))
        collections = {name: client.get_collection(name, embedding_function=None) for name in ('digest', 'original')}
        snapshots = {name: col.get(include=['embeddings', 'documents', 'metadatas']) for name, col in collections.items()}
        for snapshot in snapshots.values():
            if snapshot['ids'] and any(snapshot.get(key) is None or len(snapshot[key]) != len(snapshot['ids']) for key in ('embeddings', 'documents', 'metadatas')):
                raise RuntimeError('无法读取完整的原有记忆，未执行重建')
        vectors = {}
        for name, docs in chunks.items():
            vectors[name] = []
            for start in range(0, len(docs), BATCH_SIZE):
                batch = docs[start:start+BATCH_SIZE]
                try:
                    values = character.em_llm.invoke(batch)
                except Exception as exc:
                    raise RuntimeError('记忆模型调用失败，未执行重建') from exc
                try:
                    valid = len(values) == len(batch) and all(len(v) > 0 and all(math.isfinite(float(x)) for x in v) for v in values)
                except (TypeError, ValueError, OverflowError):
                    valid = False
                if not valid:
                    raise ValueError('记忆模型返回无效向量，未执行重建')
                vectors[name].extend(values)
            old = snapshots[name]['embeddings']
            if old is not None and len(old) and vectors[name] and len(old[0]) != len(vectors[name][0]):
                raise ValueError('记忆模型向量维度与已有集合不一致，未执行重建')
        all_vectors = vectors['digest'] + vectors['original']
        if all_vectors and any(len(v) != len(all_vectors[0]) for v in all_vectors):
            raise ValueError('记忆模型返回的向量维度不一致，未执行重建')
        try:
            for col in collections.values():
                _clear(col)
            for name, col in collections.items():
                for start in range(0, len(chunks[name]), BATCH_SIZE):
                    docs = chunks[name][start:start+BATCH_SIZE]
                    prefix = 'd' if name == 'digest' else 'o'
                    col.add(ids=[f'{prefix}{i+1}' for i in range(start,start+len(docs))], documents=docs, embeddings=vectors[name][start:start+len(docs)])
        except Exception as exc:
            try:
                for col in collections.values(): _clear(col)
                for name, col in collections.items(): _restore(col, snapshots[name])
            except Exception as restore_error:
                print(f'[SoulHaven] 记忆库恢复失败：{type(restore_error).__name__}')
                raise RuntimeError('重建失败且原记忆库恢复未完成；原始聊天和摘要文件仍保留，请检查后重试') from restore_error
            raise RuntimeError('记忆库重建失败，已恢复原有向量；原始聊天和摘要文件仍保留') from exc
        return {'digest_count': len(chunks['digest']), 'original_count': len(chunks['original'])}
