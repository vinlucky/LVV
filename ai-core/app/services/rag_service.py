import json
import sqlite3
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .chunk_service import chunk_text, detect_language
from ..config import DB_PATH

logger = logging.getLogger(__name__)

_rag_conn = None


def _get_rag_conn() -> sqlite3.Connection:
    global _rag_conn
    if _rag_conn is None:
        _rag_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _rag_conn.row_factory = sqlite3.Row
        _rag_conn.execute("PRAGMA journal_mode=WAL")
        _rag_conn.execute("PRAGMA foreign_keys=ON")
        _init_rag_tables()
    return _rag_conn


def _init_rag_tables():
    conn = _get_rag_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            kb_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'chat',
            language TEXT DEFAULT 'auto',
            source_lang TEXT,
            target_lang TEXT,
            conv_id TEXT,
            description TEXT DEFAULT '',
            doc_count INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL REFERENCES knowledge_bases(kb_id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_format TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            language TEXT DEFAULT 'auto',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS document_chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
            kb_id TEXT NOT NULL REFERENCES knowledge_bases(kb_id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            mode TEXT NOT NULL DEFAULT 'chat',
            language TEXT DEFAULT 'auto',
            source_lang TEXT,
            target_lang TEXT,
            conv_id TEXT,
            metadata TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_documents_kb_id ON documents(kb_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_kb_id ON document_chunks(kb_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_mode ON document_chunks(mode);
        CREATE INDEX IF NOT EXISTS idx_chunks_language ON document_chunks(language);
        CREATE INDEX IF NOT EXISTS idx_chunks_conv_id ON document_chunks(conv_id);
    """)

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                chunk_id UNINDEXED,
                content,
                mode UNINDEXED,
                language UNINDEXED,
                source_lang UNINDEXED,
                target_lang UNINDEXED,
                conv_id UNINDEXED,
                content='document_chunks',
                content_rowid='chunk_id'
            )
        """)
        logger.info("[rag] FTS5 virtual table created/verified")
    except Exception as e:
        logger.warning(f"[rag] FTS5 table creation skipped: {e}")

    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding float[1024]
            )
        """)
        logger.info("[rag] sqlite-vec virtual table created/verified")
    except Exception as e:
        logger.info(f"[rag] sqlite-vec not available (will use BM25 only): {e}")

    conn.commit()


def index_document(file_path: str, filename: str, mode: str = "chat",
                   language: str | None = None, source_lang: str | None = None,
                   target_lang: str | None = None, conv_id: str | None = None) -> dict | None:
    logger.info(f"[rag] Indexing start: filename='{filename}', mode={mode}, conv_id={conv_id}")
    try:
        from .file_service import read_text_file
        content = read_text_file(file_path)
        if not content or not content.strip():
            logger.warning(f"[rag] No text extracted from: {filename}")
            return None

        content_len = len(content)
        logger.info(f"[rag] Read file '{filename}': {content_len} chars")

        if language is None:
            language = detect_language(content)

        kb_id = _get_or_create_kb(mode, language, source_lang, target_lang, conv_id)
        logger.info(f"[rag] Using knowledge base: kb_id={kb_id}")

        conn = _get_rag_conn()
        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "INSERT INTO documents (doc_id, kb_id, filename, file_path, file_format, file_size, status, language, created_at) VALUES (?, ?, ?, ?, ?, ?, 'indexing', ?, ?)",
            (doc_id, kb_id, filename, str(file_path), Path(file_path).suffix.lstrip('.'), Path(file_path).stat().st_size, language, now),
        )

        chunks = chunk_text(
            text=content, filename=filename, mode=mode,
            language=language, source_lang=source_lang,
            target_lang=target_lang, conv_id=conv_id,
        )

        if not chunks:
            logger.warning(f"[rag] No chunks produced for '{filename}', skipping index")
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()
            return None

        logger.info(f"[rag] Inserting {len(chunks)} chunks into database...")
        for chunk in chunks:
            cursor = conn.execute(
                "INSERT INTO document_chunks (doc_id, kb_id, content, chunk_index, mode, language, source_lang, target_lang, conv_id, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc_id, kb_id, chunk["content"], chunk["chunk_index"],
                 chunk["mode"], chunk["language"], chunk.get("source_lang"),
                 chunk.get("target_lang"), chunk.get("conv_id"),
                 json.dumps(chunk.get("metadata", {}), ensure_ascii=False), now),
            )
            chunk_id = cursor.lastrowid
            try:
                conn.execute(
                    "INSERT INTO chunks_fts (chunk_id, content, mode, language, source_lang, target_lang, conv_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (chunk_id, chunk["content"], chunk["mode"], chunk["language"],
                     chunk.get("source_lang") or "", chunk.get("target_lang") or "",
                     chunk.get("conv_id") or ""),
                )
            except Exception as e:
                logger.warning(f"[rag] FTS5 insert failed for chunk {chunk_id}: {e}")

        conn.execute(
            "UPDATE documents SET chunk_count = ?, status = 'indexed' WHERE doc_id = ?",
            (len(chunks), doc_id),
        )
        _update_kb_counts(conn, kb_id)
        conn.commit()

        logger.info(f"[rag] Indexed '{filename}': {len(chunks)} chunks (kb={kb_id}, mode={mode}, lang={language}, conv_id={conv_id})")
        return {"doc_id": doc_id, "kb_id": kb_id, "chunk_count": len(chunks), "language": language}

    except Exception as e:
        logger.error(f"[rag] Failed to index '{filename}': {e}")
        return None


def search(query: str, mode: str = "chat", language: str | None = None,
           source_lang: str | None = None, target_lang: str | None = None,
           conv_id: str | None = None, top_k: int = 20) -> list[dict]:
    conn = _get_rag_conn()
    results = _bm25_search(conn, query, mode, language, source_lang, target_lang, conv_id, top_k)

    if not results:
        logger.info(f"[rag] BM25 returned no results for query='{query[:50]}' in mode={mode}, lang={language}, conv_id={conv_id}")
        return []

    logger.info(f"[rag] BM25 returned {len(results)} results for query='{query[:50]}' (mode={mode}, lang={language}, conv_id={conv_id})")
    return results


def search_with_rerank(query: str, mode: str = "chat", language: str | None = None,
                        source_lang: str | None = None, target_lang: str | None = None,
                        conv_id: str | None = None, top_k: int = 5) -> list[dict]:
    candidates = search(query, mode, language, source_lang, target_lang, conv_id, top_k=20)

    if not candidates:
        return []

    if len(candidates) <= top_k:
        return candidates

    reranked = _llm_rerank(query, candidates, top_k)
    if reranked:
        return reranked

    return candidates[:top_k]


def build_rag_context(query: str, mode: str = "chat", language: str | None = None,
                       source_lang: str | None = None, target_lang: str | None = None,
                       conv_id: str | None = None, top_k: int = 5) -> str | None:
    results = search_with_rerank(query, mode, language, source_lang, target_lang, conv_id, top_k)

    if not results and conv_id:
        logger.info(f"[rag] No results found, checking for unindexed files in conv={conv_id}")
        _index_unindexed_files(conv_id, mode)
        results = search_with_rerank(query, mode, language, source_lang, target_lang, conv_id, top_k)

    if not results:
        return None

    parts = []
    for i, r in enumerate(results):
        meta = json.loads(r.get("metadata", "{}")) if r.get("metadata") else {}
        source = meta.get("filename", r.get("doc_id", ""))
        parts.append(f"[来源: {source}]\n{r['content']}")

    context = "\n\n".join(parts)
    logger.info(f"[rag] Built context with {len(results)} chunks ({len(context)} chars)")
    return context


def _index_unindexed_files(conv_id: str, mode: str):
    from .file_service import read_text_file
    from ..database import get_files_by_conv
    conn = _get_rag_conn()

    conv_files = get_files_by_conv(conv_id)
    if not conv_files:
        logger.info(f"[rag] No files found for conv={conv_id}")
        return

    for f in conv_files:
        file_path = f.get("file_path", "")
        filename = f.get("filename", "")
        if not file_path or not filename:
            continue

        existing = conn.execute(
            "SELECT doc_id FROM documents WHERE file_path = ? AND status = 'indexed'",
            (file_path,),
        ).fetchone()
        if existing:
            continue

        logger.info(f"[rag] Found unindexed file: '{filename}', indexing now...")
        try:
            index_document(
                file_path=file_path, filename=filename,
                mode=mode, conv_id=conv_id,
            )
        except Exception as e:
            logger.warning(f"[rag] Failed to index '{filename}' on-demand: {e}")


def _get_or_create_kb(mode: str, language: str, source_lang: str | None,
                       target_lang: str | None, conv_id: str | None) -> str:
    conn = _get_rag_conn()
    conditions = ["mode = ?"]
    params: list = [mode]

    if language and language != "auto":
        conditions.append("(language = ? OR language = 'auto')")
        params.append(language)

    if source_lang:
        conditions.append("(source_lang = ? OR source_lang IS NULL)")
        params.append(source_lang)

    if target_lang:
        conditions.append("(target_lang = ? OR target_lang IS NULL)")
        params.append(target_lang)

    if conv_id:
        conditions.append("(conv_id = ? OR conv_id IS NULL)")
        params.append(conv_id)

    where = " AND ".join(conditions)
    row = conn.execute(f"SELECT kb_id FROM knowledge_bases WHERE {where} LIMIT 1", params).fetchone()

    if row:
        return row["kb_id"]

    kb_id = str(uuid.uuid4())
    name_parts = [mode]
    if language and language != "auto":
        name_parts.append(language)
    if source_lang:
        name_parts.append(source_lang)
    if target_lang:
        name_parts.append(f"→{target_lang}")
    name = "-".join(name_parts)

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO knowledge_bases (kb_id, name, mode, language, source_lang, target_lang, conv_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kb_id, name, mode, language, source_lang, target_lang, conv_id, now, now),
    )
    conn.commit()
    logger.info(f"[rag] Created knowledge base: {name} (kb_id={kb_id})")
    return kb_id


def _bm25_search(conn: sqlite3.Connection, query: str, mode: str,
                  language: str | None, source_lang: str | None,
                  target_lang: str | None, conv_id: str | None,
                  top_k: int) -> list[dict]:
    try:
        fts_query = _build_fts_query(query)
        if not fts_query:
            return []

        sql = """
            SELECT dc.chunk_id, dc.content, dc.doc_id, dc.kb_id, dc.chunk_index,
                   dc.mode, dc.language, dc.source_lang, dc.target_lang,
                   dc.conv_id, dc.metadata, d.filename,
                   cf.rank as bm25_rank
            FROM chunks_fts cf
            JOIN document_chunks dc ON cf.chunk_id = dc.chunk_id
            JOIN documents d ON dc.doc_id = d.doc_id
            WHERE cf.content MATCH ?
              AND dc.mode = ?
        """
        params: list = [fts_query, mode]

        if language and language != "auto":
            sql += " AND (dc.language = ? OR dc.language = 'auto')"
            params.append(language)

        if source_lang:
            sql += " AND (dc.source_lang = ? OR dc.source_lang IS NULL)"
            params.append(source_lang)

        if target_lang:
            sql += " AND (dc.target_lang = ? OR dc.target_lang IS NULL)"
            params.append(target_lang)

        if conv_id:
            sql += " AND (dc.conv_id = ? OR dc.conv_id IS NULL)"
            params.append(conv_id)

        sql += " ORDER BY cf.rank LIMIT ?"
        params.append(top_k)

        rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            r = dict(row)
            results.append(r)

        return results

    except Exception as e:
        logger.warning(f"[rag] BM25 search failed: {e}")
        return []


def _build_fts_query(query: str) -> str:
    tokens = query.strip().split()
    if not tokens:
        return ""
    escaped = [t.replace('"', '""') for t in tokens if len(t) > 0]
    if not escaped:
        return ""
    return " OR ".join(f'"{t}"' for t in escaped)


def _llm_rerank(query: str, candidates: list[dict], top_k: int) -> list[dict] | None:
    try:
        from .llm_service import chat_completion_with_fallback

        snippets = []
        for i, c in enumerate(candidates[:15]):
            content = c["content"][:300]
            snippets.append(f"[{i + 1}] {content}")

        prompt = f"""请对以下文档片段与查询的相关性打分（1-10分）。

查询：{query}

文档片段：
{chr(10).join(snippets)}

请严格按以下JSON格式返回打分结果，不要输出其他内容：
[{{"index": 1, "score": 9}}, {{"index": 2, "score": 3}}, ...]"""

        result = chat_completion_with_fallback(
            chain_name="critic",
            system_prompt="你是一个文档相关性评估助手。请对文档片段与查询的相关性打分。",
            user_message=prompt,
            temperature=0.1,
        )

        if not result.get("success"):
            return None

        content = result.get("content", "")
        import re
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if not json_match:
            return None

        scores = json.loads(json_match.group())
        indexed = {}
        for s in scores:
            idx = s.get("index", 0) - 1
            if 0 <= idx < len(candidates):
                indexed[idx] = s.get("score", 0)

        sorted_indices = sorted(indexed.keys(), key=lambda i: indexed[i], reverse=True)
        reranked = [candidates[i] for i in sorted_indices[:top_k]]

        logger.info(f"[rag] LLM reranked {len(candidates)} candidates → top {len(reranked)}")
        return reranked

    except Exception as e:
        logger.warning(f"[rag] LLM rerank failed: {e}")
        return None


def _update_kb_counts(conn: sqlite3.Connection, kb_id: str):
    doc_count = conn.execute("SELECT COUNT(*) FROM documents WHERE kb_id = ?", (kb_id,)).fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM document_chunks WHERE kb_id = ?", (kb_id,)).fetchone()[0]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE knowledge_bases SET doc_count = ?, chunk_count = ?, updated_at = ? WHERE kb_id = ?",
        (doc_count, chunk_count, now, kb_id),
    )


def get_kb_stats() -> list[dict]:
    conn = _get_rag_conn()
    rows = conn.execute("SELECT * FROM knowledge_bases ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]
