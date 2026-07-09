#!/usr/bin/env python3
"""Grok 4.5 multi-effort case study runner for Athenaeum."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from athenaeum.cli import app
from athenaeum.effort import EFFORTS

QUESTION = (
    "Should democratic governments ban the open release of frontier open-weight AI models "
    "that demonstrably lower the barrier to bioweapon design assistance, or is continued open "
    "release net-positive because defenders, academic labs, and red teams need equal access? "
    "Steelman both sides, identify load-bearing empirical claims, name the strongest objection "
    "to your conclusion, and give a decision framework a national security council could use."
)

# Full ladder + unique extremes
EFFORT_LADDER = ["low", "medium", "high", "vhigh", "max", "ultra"]

# Unique reasoning axes at fixed medium effort (if API respects them)
REASONING_VARIANTS = ["off", "high", "xhigh"]

ROOT = Path("docs/case-studies")
OUT_DIR = Path("runs/case-study-grok")
RUNNER = CliRunner()


@dataclass
class RunRecord:
    kind: str
    effort: str
    reasoning: str
    exit_code: int
    duration_s: float
    out_path: str
    words: int
    claims: int
    citations: int
    confidence: float | None
    report_preview: str
    plan_nodes: int | None
    plan_budget: float | None
    plan_est_cost: float | None
    plan_debaters: str | None
    error: str | None = None


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dry_run_plan(effort: str) -> dict:
    budget = round(EFFORTS[effort].default_budget * 2.5, 2)
    result = RUNNER.invoke(
        app,
        [
            "--runtime",
            "api",
            "--effort",
            effort,
            "--budget",
            str(budget),
            "--dry-run",
            "--json",
            QUESTION,
        ],
    )
    if result.exit_code != 0:
        return {"ok": False, "exit_code": result.exit_code, "output": result.output[-1000:]}
    return json.loads(result.output)


def live_run(effort: str, reasoning: str, label: str) -> RunRecord:
    out = OUT_DIR / f"{label}.md"
    # Planner often marks suggested budget above default; use 2.5x default to clear S5.
    budget = round(EFFORTS[effort].default_budget * 2.5, 2)
    started = time.perf_counter()
    result = RUNNER.invoke(
        app,
        [
            "--runtime",
            "api",
            "--effort",
            effort,
            "--reasoning-effort",
            reasoning,
            "--budget",
            str(budget),
            "--out",
            str(out),
            "--seed",
            "42",
            QUESTION,
        ],
    )
    duration = round(time.perf_counter() - started, 2)
    words = 0
    claims = 0
    citations = 0
    confidence = None
    preview = ""
    error = None
    if result.exit_code != 0:
        error = (result.output or result.stderr or "failed")[-1500:]
    elif out.exists():
        text = out.read_text(encoding="utf-8")
        words = len(text.split())
        preview = text[:600].replace("\n", " ")
        # companion json if written next to out
        # also check runs/*/artifacts/output.json latest for this content
    # find latest run dir with matching out path in journal is hard; parse output.json near runs
    run_dirs = sorted(Path("runs").glob("*/artifacts/output.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in run_dirs[:8]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        md = data.get("report_markdown") or ""
        if out.exists() and out.read_text(encoding="utf-8")[:80] in md[:200]:
            claims = len(data.get("claims") or [])
            citations = len(data.get("citations") or [])
            break
        if words and md and abs(len(md.split()) - words) < 5:
            claims = len(data.get("claims") or [])
            citations = len(data.get("citations") or [])
            break

    plan_nodes = plan_budget = plan_est = None
    plan_debaters = None
    plan = dry_run_plan(effort)
    if plan.get("plan"):
        p = plan["plan"]
        plan_nodes = len(p.get("nodes") or [])
        plan_budget = p.get("budget")
        plan_est = p.get("estimated_cost")
        for node in p.get("nodes") or []:
            if node.get("name") == "debate":
                plan_debaters = node.get("detail")
                break

    return RunRecord(
        kind="live",
        effort=effort,
        reasoning=reasoning,
        exit_code=result.exit_code,
        duration_s=duration,
        out_path=str(out),
        words=words,
        claims=claims,
        citations=citations,
        confidence=confidence,
        report_preview=preview,
        plan_nodes=plan_nodes,
        plan_budget=plan_budget,
        plan_est_cost=plan_est,
        plan_debaters=plan_debaters,
        error=error,
    )


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY required")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    plans: dict[str, object] = {}

    print(f"[{_utc()}] case study start")
    print(f"question: {QUESTION[:100]}...")

    for effort in EFFORT_LADDER:
        print(f"\n== dry-run plan effort={effort} ==")
        plan = dry_run_plan(effort)
        plans[effort] = plan
        if plan.get("plan"):
            p = plan["plan"]
            print(f"  nodes={len(p.get('nodes', []))} budget={p.get('budget')} est={p.get('estimated_cost')}")
        else:
            print("  plan failed", plan.get("exit_code"))

    for effort in EFFORT_LADDER:
        print(f"\n== live effort={effort} reasoning=high ==")
        rec = live_run(effort, "high", f"effort-{effort}")
        records.append(asdict(rec))
        status = "OK" if rec.exit_code == 0 else "FAIL"
        print(f"  {status} {rec.duration_s}s words={rec.words} claims={rec.claims} out={rec.out_path}")
        if rec.error:
            print(f"  err: {rec.error[:300]}")

    for reasoning in REASONING_VARIANTS:
        print(f"\n== live effort=medium reasoning={reasoning} ==")
        rec = live_run("medium", reasoning, f"reasoning-{reasoning}")
        records.append(asdict(rec))
        status = "OK" if rec.exit_code == 0 else "FAIL"
        print(f"  {status} {rec.duration_s}s words={rec.words} claims={rec.claims}")

    payload = {
        "generated_at": _utc(),
        "model": "grok-4.5",
        "provider": "Junli",
        "base_url": "https://openapi.junliai.org/v1",
        "question": QUESTION,
        "effort_profiles": {
            name: {
                "budget": p.default_budget,
                "debaters": p.debaters,
                "rounds": p.rounds,
                "scale": p.scale_strategy,
                "tagline": p.tagline,
            }
            for name, p in EFFORTS.items()
        },
        "plans": plans,
        "runs": records,
    }
    raw_path = ROOT / "grok45-effort-case-study-raw.json"
    raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {raw_path}")
    _write_markdown(payload)
    print(f"wrote {ROOT / 'grok45-effort-case-study.md'}")


def _write_markdown(payload: dict) -> None:
    lines: list[str] = []
    lines.append("# Case Study: Grok 4.5 Across Athenaeum Effort Tiers")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at']}`  ")
    lines.append(f"Provider: **{payload['provider']}** · Model: **{payload['model']}**  ")
    lines.append(f"Endpoint: `{payload['base_url']}`")
    lines.append("")
    lines.append("## Question (complex policy debate)")
    lines.append("")
    lines.append(f"> {payload['question']}")
    lines.append("")
    lines.append("## Effort ladder (engine shape)")
    lines.append("")
    lines.append("| Effort | Tagline | Debaters | Rounds | Scale | Default budget |")
    lines.append("|---|---|---:|---:|---|---:|")
    for name, meta in payload["effort_profiles"].items():
        lines.append(
            f"| `{name}` | {meta['tagline']} | {meta['debaters']} | {meta['rounds']} | "
            f"{meta['scale']} | ${meta['budget']:.2f} |"
        )
    lines.append("")
    lines.append("## Compiled plan differences (dry-run)")
    lines.append("")
    lines.append("| Effort | Nodes | Budget | Est. cost | Debate detail |")
    lines.append("|---|---:|---:|---:|---|")
    for effort in EFFORT_LADDER:
        plan_wrap = payload["plans"].get(effort) or {}
        plan = plan_wrap.get("plan") if isinstance(plan_wrap, dict) else None
        if not plan:
            lines.append(f"| `{effort}` | — | — | — | plan failed |")
            continue
        debate = next((n for n in plan.get("nodes", []) if n.get("name") == "debate"), {})
        lines.append(
            f"| `{effort}` | {len(plan.get('nodes', []))} | ${float(plan.get('budget', 0)):.2f} | "
            f"${float(plan.get('estimated_cost', 0)):.2f} | {debate.get('detail', '—')} |"
        )
    lines.append("")
    lines.append("## Live Grok 4.5 runs")
    lines.append("")
    lines.append("### By effort (`reasoning=high`)")
    lines.append("")
    lines.append("| Effort | Exit | Duration | Words | Claims | Citations | Output |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for rec in payload["runs"]:
        if not rec["out_path"].startswith("runs/case-study-grok/effort-"):
            continue
        lines.append(
            f"| `{rec['effort']}` | {rec['exit_code']} | {rec['duration_s']}s | {rec['words']} | "
            f"{rec['claims']} | {rec['citations']} | `{rec['out_path']}` |"
        )
    lines.append("")
    lines.append("### By reasoning effort (`effort=medium`)")
    lines.append("")
    lines.append("| Reasoning | Exit | Duration | Words | Claims | Output |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for rec in payload["runs"]:
        if not rec["out_path"].startswith("runs/case-study-grok/reasoning-"):
            continue
        lines.append(
            f"| `{rec['reasoning']}` | {rec['exit_code']} | {rec['duration_s']}s | {rec['words']} | "
            f"{rec['claims']} | `{rec['out_path']}` |"
        )
    lines.append("")
    lines.append("## Qualitative self-evaluation")
    lines.append("")
    lines.append(_self_eval(payload))
    lines.append("")
    lines.append("## Report previews")
    lines.append("")
    for rec in payload["runs"]:
        if rec["exit_code"] != 0:
            lines.append(f"### FAIL `{rec['effort']}` / `{rec['reasoning']}`")
            lines.append("")
            lines.append("```")
            lines.append((rec.get("error") or "unknown")[:800])
            lines.append("```")
            lines.append("")
            continue
        lines.append(f"### `{rec['effort']}` · reasoning `{rec['reasoning']}` · {rec['words']} words")
        lines.append("")
        lines.append(f"> {rec['report_preview'][:500]}{'…' if len(rec['report_preview']) > 500 else ''}")
        lines.append("")
    lines.append("## Method notes")
    lines.append("")
    lines.append("- Runtime: `api` → single gateway completion validated as `ReportOutput` (not multi-node local conductor).")
    lines.append("- Effort still changes **planner budget, debate shape, and prompt effort label** fed into the API task.")
    lines.append("- Dry-runs show the full multi-node workflow Athenaeum would compile for each tier.")
    lines.append("- Seed fixed at `42` for path stability; model sampling may still vary.")
    lines.append("- Secrets never written into this report.")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append("- Raw metrics: `docs/case-studies/grok45-effort-case-study-raw.json`")
    lines.append("- Reports: `runs/case-study-grok/*.md`")
    lines.append("")
    (ROOT / "grok45-effort-case-study.md").write_text("\n".join(lines), encoding="utf-8")


def _self_eval(payload: dict) -> str:
    lives = [r for r in payload["runs"] if r["out_path"].startswith("runs/case-study-grok/effort-") and r["exit_code"] == 0]
    if not lives:
        return "No successful live runs; cannot score quality ladder. Check gateway key and model availability."
    by_effort = {r["effort"]: r for r in lives}
    order = [e for e in EFFORT_LADDER if e in by_effort]
    words = [by_effort[e]["words"] for e in order]
    claims = [by_effort[e]["claims"] for e in order]
    durs = [by_effort[e]["duration_s"] for e in order]
    notes = []
    notes.append(
        f"- Successful effort runs: {', '.join(f'`{e}`' for e in order)} "
        f"({len(order)}/{len(EFFORT_LADDER)})."
    )
    if words:
        notes.append(f"- Word counts low→high observed: {words[0]} → {words[-1]} (sequence: {words}).")
    if claims:
        notes.append(f"- Claim counts: {claims}.")
    if durs:
        notes.append(f"- Wall times (s): {durs}.")
    # Monotonicity soft checks
    if len(words) >= 2 and words[-1] >= words[0]:
        notes.append("- **Length trend:** highest tier produced ≥ lowest tier words (weak proxy for depth).")
    else:
        notes.append("- **Length trend:** not monotonic — API single-shot may not fully exploit multi-node effort knobs.")
    notes.append(
        "- **Architecture caveat:** current `ApiRuntime` is one structured completion; multi-loop debate/court "
        "depth is fully exercised only under `minimal`/external CLI runtimes. Effort still modulates budget, "
        "planner summary, and prompt effort metadata."
    )
    notes.append(
        "- **Unique extremes:** `ultra` is the adversarial maximum (tournament-16 scale, 8×7 debate shape); "
        "`low` is the minimum viable path (2×1 debate, $0.50 budget)."
    )
    notes.append(
        "- **Decision for operators:** use `low`/`medium` for cheap drafts; `high` for default think-tank; "
        "`vhigh`+ when the question is irreversible policy; treat API-mode outputs as single-judge reports "
        "unless you switch to multi-agent CLI runtimes."
    )
    return "\n".join(notes)


if __name__ == "__main__":
    main()
