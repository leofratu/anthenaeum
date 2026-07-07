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
