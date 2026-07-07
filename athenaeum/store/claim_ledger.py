from __future__ import annotations

import json
from pathlib import Path

from athenaeum.schemas import ClaimRef, utc_now


class ClaimLedger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, claim: ClaimRef, source_node: str, verdict_reason: str = "") -> None:
        current = self.materialize()
        version = int(current.get(claim.id, {}).get("version", 0)) + 1
        row = {
            "claim": claim.model_dump(mode="json"),
            "claim_id": claim.id,
            "version": version,
            "source_node": source_node,
            "verdict_reason": verdict_reason,
            "updated_at": utc_now(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def materialize(self) -> dict[str, dict]:
        latest: dict[str, dict] = {}
        if not self.path.exists():
            return latest
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            row = json.loads(line)
            latest[str(row["claim_id"])] = row
        return latest

    def write_current(self, path: Path | None = None) -> None:
        target = path or self.path.with_suffix(".current.json")
        target.write_text(json.dumps(self.materialize(), indent=2, sort_keys=True), encoding="utf-8")
