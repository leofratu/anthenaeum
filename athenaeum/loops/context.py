from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is",
    "it", "of", "on", "or", "should", "that", "the", "this", "to", "we", "what", "when", "with",
}


@dataclass(frozen=True)
class RunContext:
    question: str
    run_id: str
    effort: str
    mode: str
    audience: str | None
    seed: int
    artifact_root: Path

    def stable_id(self, kind: str, *parts: object, length: int = 12) -> str:
        raw = "|".join([kind, str(self.seed), self.question, *[str(part) for part in parts]])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]

    def keywords(self, text: str | None = None, limit: int = 8) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", (text or self.question).lower())
        seen: list[str] = []
        for word in words:
            if word not in STOPWORDS and word not in seen:
                seen.append(word)
            if len(seen) >= limit:
                break
        return seen or ["question", "evidence", "decision"]


def write_json(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding="utf-8")
