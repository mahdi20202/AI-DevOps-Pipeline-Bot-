from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass
class RetrievedChunk:
    source: str
    score: float
    excerpt: str


class LocalRAGService:
    def __init__(self):
        self.settings = get_settings()

    def retrieve(self, query: str, limit: int = 4) -> list[RetrievedChunk]:
        docs_dir = Path(self.settings.rag_docs_path)
        if not docs_dir.exists():
            return []
        tokens = self._tokenize(query)
        scored: list[RetrievedChunk] = []
        for path in docs_dir.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in {'.md', '.txt', '.json', '.yaml', '.yml'}:
                continue
            text = path.read_text(encoding='utf-8', errors='ignore')
            text_tokens = self._tokenize(text)
            if not text_tokens:
                continue
            overlap = len(tokens & text_tokens)
            if overlap == 0:
                continue
            score = overlap / max(1, len(tokens))
            excerpt = self._extract_excerpt(text, tokens)
            scored.append(RetrievedChunk(source=path.name, score=round(score, 2), excerpt=excerpt[:500]))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token.lower() for token in re.findall(r'[A-Za-z0-9_\-]{3,}', text)}

    @staticmethod
    def _extract_excerpt(text: str, tokens: set[str]) -> str:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            lowered = line.lower()
            if any(token in lowered for token in list(tokens)[:12]):
                return line
        return lines[0] if lines else text[:300]
