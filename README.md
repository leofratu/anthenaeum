# ATHENAEUM — AI Think Tank

A CLI-driven, provider-agnostic multi-agent deliberation engine: pose a question, and
a heterogeneous fleet of AI agents (raw LLM APIs *and* agent CLIs like OpenCode,
Codex CLI, AGY CLI, and Claude CLI) researches, debates, evolves, adversarially
fact-checks, and peer-reviews a position — then emits a cited, audience-tailored
report with visible epistemic status on every claim.

**Status:** implementation in progress with a broad local engine. The CLI runtime
spine is in place for minimal deterministic mode, API gateway mode, OpenCode, Codex,
AGY CLI, Claude CLI, and Gemini CLI. The app now includes typed schemas, dry-run
planning, sanity checks, deterministic local research/debate/verify/court/revise
loops, loop-backed evolve/review/science artifacts, a node-level conductor,
hash-chained journals, resume inspection/continuation, SQLite sessions, live-capable
provider adapters, JSON mode, runtime output repair, and environment diagnostics.

## Minimal usage (target UX)

```bash
python3 -m pip install -e .
thinktank "Should the EU regulate open-weight models?"
# → report.md + runs/<id>/ artifacts, using deterministic minimal mode by default
```

Use a specific external agent CLI when desired:

```bash
thinktank --runtime opencode "Summarize this repository"
thinktank --runtime codex "Design an experiment"
thinktank --runtime agy "Critique this plan"
thinktank --runtime claude "Review this codebase"
```

Preview the compiled workflow without writing a report:

```bash
thinktank --dry-run --runtime codex "Should the EU regulate open-weight models?"
thinktank --json --dry-run "Should the EU regulate open-weight models?"
thinktank --runtime api --iq 140 "Should the EU regulate open-weight models?"
```

Run diagnostics for the supported external CLIs:

```bash
thinktank doctor
thinktank runtimes list
thinktank schemas list
thinktank schemas show report
python3 -m athenaeum effort --select   # keyboard slider; use ←/→ then Enter
python3 -m athenaeum interactive       # use /setup, /iq, /save-config, /plan, /run
thinktank providers list
thinktank providers init --out thinktank.toml
thinktank resume <run-id>
thinktank resume <run-id> --continue
thinktank watch "Track this topic" --daily-budget 3 --for 14d
thinktank daemon run --once
```

Run one external CLI runtime directly through ATHENAEUM's JSON result contract:

```bash
thinktank runtimes run opencode "Summarize this repository" --out report.md
```

Runtime commands can be overridden in `thinktank.toml` when a local CLI uses different
flags:

```toml
[runtimes.agy]
command = "agy run --json --workspace {workspace} {prompt_file}"
version_args = ["--version"]
```

Implemented deterministic local surfaces: `thinktank evolve` (idea search),
`thinktank review draft.md` (reviewer court only), `thinktank science` (sandboxed
experiment plan), `thinktank watch`, `thinktank sessions`, `thinktank daemon`,
`thinktank personas`, `thinktank workflows`, `thinktank schemas`, `thinktank providers`,
`thinktank reasoning`, `thinktank interactive`, `thinktank resume`, `thinktank --dry-run`,
`thinktank --json`, and `thinktank doctor`.

IQ/effort is the main quality control:

```bash
thinktank --iq 140 --dry-run "Should we ship?"
thinktank --effort iq-max --runtime codex "Review this repository"
thinktank interactive               # use /setup, /iq, /runtime, /save-config, /plan, /run
```

Advanced provider reasoning remains available with `--reasoning-effort` or
interactive `/help advanced`, but normal setup should use the IQ/effort slider.

## Documents

- [`docs/specs/2026-07-07-think-tank-spec.md`](docs/specs/2026-07-07-think-tank-spec.md) — full technical specification
- [`docs/specs/2026-07-07-research-citations.md`](docs/specs/2026-07-07-research-citations.md) — annotated bibliography of the papers/systems the design is grounded in

## Key ideas

- **Deterministic orchestration, compiled workflows** — models fill slots in a
  sanity-checked graph; they never improvise the control flow.
- **Frontier loops as engine primitives** — sparse-topology debate, Reflexion memory,
  MAP-Elites evolution over *arguments*, refutation-framed claim verification,
  STORM-style research, budget-aware test-time scaling.
- **Reviewer Court** — Toulmin argument auditing, audience modeling, hedging
  calibration, thinker-emulation panels (outcome-blind), domain-expert review.
- **Provider-agnostic ModelGateway** — capability routing with fallbacks across
  Anthropic / OpenAI / Google / OpenRouter / local, plus judge–generator separation.
