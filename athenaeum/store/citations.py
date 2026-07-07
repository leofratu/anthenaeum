from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from athenaeum.schemas import CitationRef, SourceNote, utc_now


class CitationDB:
    def __init__(self, path: Path = Path(".thinktank") / "citations.sqlite3"):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                  id TEXT PRIMARY KEY,
                  canonical_key TEXT UNIQUE NOT NULL,
                  url TEXT,
                  title TEXT NOT NULL,
                  source_type TEXT NOT NULL,
                  first_seen_at TEXT NOT NULL,
                  last_retrieved_at TEXT NOT NULL,
                  reliability TEXT,
                  metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_citations (
                  run_id TEXT NOT NULL,
                  citation_id TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  claim_id TEXT,
                  node_id TEXT,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY(run_id, citation_id)
                )
                """
            )

    def upsert_citation(self, citation: CitationRef) -> str:
        key = _canonical_key(citation)
        source_id = citation.id or hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET
                  last_retrieved_at = excluded.last_retrieved_at,
                  title = excluded.title
                """,
                (source_id, key, citation.url, citation.title, citation.source_type, utc_now(), citation.retrieved_at, None, "{}"),
            )
            row = conn.execute("SELECT id FROM sources WHERE canonical_key = ?", (key,)).fetchone()
            return str(row["id"])

    def link_run(self, run_id: str, citation: CitationRef, claim_id: str | None = None, node_id: str | None = None) -> None:
        source_id = self.upsert_citation(citation)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO run_citations VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, citation.id, source_id, claim_id, node_id, utc_now()),
            )

    def list_sources(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM sources ORDER BY title")]


def _canonical_key(citation: CitationRef | SourceNote) -> str:
    if getattr(citation, "url", None):
        parsed = urlparse(str(citation.url))
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))
    return f"{getattr(citation, 'source_type', 'source')}:{getattr(citation, 'title', '').strip().lower()}"
