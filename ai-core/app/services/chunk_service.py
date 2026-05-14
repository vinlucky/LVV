import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
HEADING_PATTERNS = [
    re.compile(r'^#{1,6}\s+', re.MULTILINE),
    re.compile(r'^[一二三四五六七八九十]+[、.]\s*', re.MULTILINE),
    re.compile(r'^\d+[.、]\s*\S', re.MULTILINE),
    re.compile(r'^第[一二三四五六七八九十\d]+[章节篇部]\s*', re.MULTILINE),
]


def detect_language(text: str) -> str:
    if not text:
        return "auto"
    sample = text[:2000]
    zh = sum(1 for c in sample if '\u4e00' <= c <= '\u9fff')
    en = sum(1 for c in sample if c.isascii() and c.isalpha())
    ja = sum(1 for c in sample if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
    ko = sum(1 for c in sample if '\uac00' <= c <= '\ud7af')
    total = zh + en + ja + ko
    if total == 0:
        return "auto"
    if zh / total > 0.3:
        return "zh"
    if ja / total > 0.2:
        return "ja"
    if ko / total > 0.2:
        return "ko"
    return "en"


def chunk_text(text: str, filename: str = "", mode: str = "chat",
               language: str | None = None, source_lang: str | None = None,
               target_lang: str | None = None, conv_id: str | None = None) -> list[dict]:
    if not text or not text.strip():
        logger.warning(f"[chunk] Empty content, skipping: '{filename}'")
        return []

    text_len = len(text)
    logger.info(f"[chunk] Starting chunk: filename='{filename}', text_len={text_len}, mode={mode}")

    if language is None:
        language = detect_language(text)
        logger.info(f"[chunk] Detected language: {language}")

    sections = _split_by_headings(text)
    logger.info(f"[chunk] Split into {len(sections)} sections by headings")

    chunks = []
    chunk_index = 0
    for i, section in enumerate(sections):
        if len(section) <= CHUNK_SIZE:
            if section.strip():
                chunks.append(_make_chunk(
                    content=section, chunk_index=chunk_index, filename=filename,
                    mode=mode, language=language, source_lang=source_lang,
                    target_lang=target_lang, conv_id=conv_id,
                ))
                chunk_index += 1
        else:
            sub_chunks = _split_by_size(section)
            logger.info(f"[chunk] Section {i+1} ({len(section)} chars) → {len(sub_chunks)} sub-chunks")
            for sc in sub_chunks:
                chunks.append(_make_chunk(
                    content=sc, chunk_index=chunk_index, filename=filename,
                    mode=mode, language=language, source_lang=source_lang,
                    target_lang=target_lang, conv_id=conv_id,
                ))
                chunk_index += 1

    logger.info(f"[chunk] Done: '{filename}' → {len(chunks)} chunks (lang={language}, mode={mode}, conv_id={conv_id})")
    return chunks


def _split_by_headings(text: str) -> list[str]:
    boundaries = [0]
    for pattern in HEADING_PATTERNS:
        for m in pattern.finditer(text):
            pos = m.start()
            if pos > 0:
                boundaries.append(pos)
    boundaries.append(len(text))
    boundaries = sorted(set(boundaries))

    sections = []
    for i in range(len(boundaries) - 1):
        section = text[boundaries[i]:boundaries[i + 1]].strip()
        if section:
            sections.append(section)

    if not sections:
        sections = [text.strip()] if text.strip() else []

    return sections


def _split_by_size(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            boundary = text.rfind('\n', start + CHUNK_SIZE - CHUNK_OVERLAP, end)
            if boundary == -1:
                boundary = text.rfind('。', start + CHUNK_SIZE - CHUNK_OVERLAP, end)
            if boundary == -1:
                boundary = text.rfind('. ', start + CHUNK_SIZE - CHUNK_OVERLAP, end)
            if boundary > start:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end if end > start else start + CHUNK_SIZE

    return chunks


def _make_chunk(content: str, chunk_index: int, filename: str, mode: str,
                language: str, source_lang: str | None, target_lang: str | None,
                conv_id: str | None) -> dict:
    return {
        "content": content,
        "chunk_index": chunk_index,
        "filename": filename,
        "mode": mode,
        "language": language,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "conv_id": conv_id,
        "metadata": {
            "filename": filename,
            "chunk_index": chunk_index,
        },
    }
