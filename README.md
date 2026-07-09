<h1 align="center">ATHENAEUM</h1>

<p align="center">
  <strong>Interactive AI think tank orchestration from your terminal.</strong>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12%2B-blue">
  <img alt="CLI Typer" src="https://img.shields.io/badge/CLI-Typer-2f6fdd">
  <img alt="UI Rich" src="https://img.shields.io/badge/UI-Rich-7b61ff">
  <img alt="Tests 190" src="https://img.shields.io/badge/tests-190%20passing-brightgreen">
  <img alt="Status prototype" src="https://img.shields.io/badge/status-active%20prototype-orange">
</p>

<p align="center">
  Ask a hard question, preview the workflow, route work across providers or agent CLIs,
  and get inspectable reports instead of one-shot answers.
</p>

```text
Question
  -> Planner
  -> Research
  -> Debate
  -> Draft
  -> Verify
  -> Reviewer Court
  -> Revise
  -> Report + Artifacts
```

## At A Glance

| What It Is | Primary Command | Offline? | Live Providers? | Main Outputs |
|---|---|---:|---:|---|
| Interactive think-tank CLI | `python3 -m athenaeum interactive` | Yes | Yes | Plans, reports, saved config |
| Workflow compiler | `python3 -m athenaeum --dry-run "Question"` | Yes | Yes | Checked execution graph |
| IQ / effort selector | `python3 -m athenaeum effort --select` | Yes | Yes | Effort tier for run shape |
| Provider gateway | `python3 -m athenaeum providers list` | Stub only | Yes | Route/provider health |
| External CLI runtime bridge | `python3 -m athenaeum runtimes list` | Depends | Depends | OpenCode/Codex/Claude/Gemini/AGY execution |
| Codex/Claude skill bundle | `skills/athenaeum-think-tank/` | Yes | Yes | Agent operating instructions |

| Current Status | Notes |
|---|---|
| Prototype | Broad local engine and working CLI runtime spine. |
| Offline mode | `minimal` runtime is deterministic and works without API keys. |
| Live providers | Require API keys and `thinktank.toml`. |
| Test suite | `190` tests currently pass locally. |
| Python | Requires Python `3.12+`. |

## Workflow Shape

| Stage | Purpose | Typical Artifact |
|---|---|---|
| Planner | Rates complexity, chooses loops, estimates budget | `plan.json` |
| Research | Collects background and candidate evidence | `research.json` |
| Debate | Compares competing positions | `debate.json`, `debate_transcript.jsonl` |
| Draft | Produces the candidate answer/report | `draft.initial.md`, `draft.initial.json` |
| Verify | Checks load-bearing claims | `verify.json`, `claims.jsonl` |
| Reviewer Court | Audits argument quality, audience fit, hedging, objections | `court.json` |
| Revise | Applies critique and tightens the report | `revise.json`, `report.revised.md` |
| Emit | Writes final user-facing output and run metadata | `report.md`, `manifest.json`, `ledger.json` |

## Choose Your Path

| I Want To... | Start Here | Then Use |
|---|---|---|
| Try it without keys | `python3 -m athenaeum --minimal --dry-run "Should we ship?"` | Inspect the compiled plan. |
| Use the polished terminal flow | `python3 -m athenaeum interactive` | `/setup`, `/iq`, `/plan`, `/run`. |
| Configure a live provider | `python3 -m athenaeum setup ...` | Save `thinktank.toml`, export API key. |
| Delegate to an agent CLI | `python3 -m athenaeum --runtime codex "Question"` | Swap `codex` for `opencode`, `claude`, `gemini`, or `agy`. |
| Review a draft | `python3 -m athenaeum review draft.md` | Read `review.md` and `review.md.json`. |
| Install the agent skill | `python3 skills/athenaeum-think-tank/scripts/install_skill.py --target codex --symlink` | Use from Codex or Claude Code. |

## Install

| Step | Command |
|---|---|
| Clone | `git clone https://github.com/leofratu/think-tank.git` |
| Enter repo | `cd think-tank` |
| Install editable | `python3 -m pip install -e ".[dev]"` |
| Source checkout command | `python3 -m athenaeum --help` |
| Installed console command | `thinktank --help` |

Requirements:

| Requirement | Needed For |
|---|---|
| Python `3.12+` | Package and CLI. |
| `OPENAI_API_KEY` | OpenAI-compatible and OpenAI provider runs. |
| `ANTHROPIC_API_KEY` | Anthropic provider runs. |
| `GOOGLE_API_KEY` | Google provider runs. |
| `opencode`, `codex`, `claude`, `gemini`, `agy` | Matching external CLI runtimes. |

## Quick Start

| Step | Command | Expected Result |
|---:|---|---|
| 1 | `git clone https://github.com/leofratu/think-tank.git` | Local checkout. |
| 2 | `cd think-tank` | Enter project. |
| 3 | `python3 -m pip install -e ".[dev]"` | Editable install with tests. |
| 4 | `python3 -m athenaeum doctor` | Runtime/provider diagnostics. |
| 5 | `python3 -m athenaeum --minimal --dry-run "Should we ship this policy?"` | Offline compiled workflow preview. |
| 6 | `python3 -m athenaeum interactive` | Open setup-first terminal UI. |

After editable install, replace `python3 -m athenaeum` with `thinktank`.

```bash
thinktank --minimal --dry-run "Should we ship this policy?"
```

## Interactive CLI

The interactive shell is the intended front door. It keeps setup, IQ/effort, planning,
and execution in one terminal session.

```bash
python3 -m athenaeum interactive
```

Setup commands:

| Command | Result |
|---|---|
| `/setup` | Shows current provider/model/runtime/IQ state. |
| `/provider OpenAI` | Sets the active provider name. |
| `/model gpt-5.5` | Sets the primary model. |
| `/review-model gpt-5.5` | Sets the judge/review model. |
| `/base-url https://openapi.junliai.org` | Sets OpenAI-compatible base URL. |
| `/runtime auto` | Uses API when available, otherwise minimal. |
| `/network on` | Records enabled network access. |
| `/storage no-response-storage` | Records no-response-storage preference. |
| `/save-config thinktank.toml` | Writes a reusable config file. |

Run commands:

| Command | Result |
|---|---|
| `/iq` | Opens the animated IQ/effort slider. |
| `/iq 140` | Maps numeric IQ alias to effort. |
| `/plan What would fail?` | Compiles the workflow only. |
| `/run What would fail?` | Runs with current settings. |
| `/doctor` | Checks runtime/provider environment. |
| `/settings` | Shows compact current state. |
| `/help advanced` | Shows lower-level provider reasoning controls. |

Example session:

```text
/setup
/iq
/provider OpenAI
/model gpt-5.5
/review-model gpt-5.5
/base-url https://openapi.junliai.org
/runtime auto
/save-config thinktank.toml
/plan What would make this launch fail?
/run What would make this launch fail?
```

## Configure A Live Provider

Generate the OpenAI-compatible config:

```bash
python3 -m athenaeum setup \
  --provider OpenAI \
  --model gpt-5.5 \
  --review-model gpt-5.5 \
  --model-reasoning xhigh \
  --base-url https://openapi.junliai.org \
  --network enabled \
  --disable-storage \
  --goals \
  --out thinktank.toml \
  --force
```

| Config Field | Example | Meaning |
|---|---|---|
| `model_provider` | `OpenAI` | Active provider key/display name. |
| `model` | `gpt-5.5` | Primary generation model. |
| `review_model` | `gpt-5.5` | Judge/review model. |
| `model_reasoning_effort` | `xhigh` | Advanced provider reasoning override. |
| `disable_response_storage` | `true` | Requests no response storage where supported. |
| `network_access` | `enabled` | Records intended network mode. |
| `wire_api` | `responses` | Uses OpenAI-compatible Responses shape. |
| `requires_openai_auth` | `true` | Reads `OPENAI_API_KEY` from the environment. |
| `features.goals` | `true` | Enables portable goal support. |

Provider setup matrix:

| Provider Family | Config Key | Env Var | Wire/API Notes |
|---|---|---|---|
| OpenAI-compatible Responses | `kind = "openai-compatible"` or `[model_providers.OpenAI]` | `OPENAI_API_KEY` | `wire_api = "responses"` for Responses-style payloads. |
| OpenAI | `kind = "openai"` | `OPENAI_API_KEY` | Native OpenAI-compatible adapter. |
| Anthropic | `kind = "anthropic"` | `ANTHROPIC_API_KEY` | Uses Anthropic thinking budget mapping for reasoning controls. |
| Google | `kind = "google"` | `GOOGLE_API_KEY` | Uses Gemini thinking budget mapping. |
| Stub | `kind = "stub"` | None | Deterministic local placeholder for offline smoke tests. |

Set the key:

```bash
export OPENAI_API_KEY="..."
```

Preview before running:

```bash
python3 -m athenaeum --config thinktank.toml --runtime auto --iq 140 --dry-run "Should we ship?"
```

Run when the plan looks right:

```bash
python3 -m athenaeum --config thinktank.toml --runtime auto --iq 140 "Should we ship?"
```

## IQ / Effort

IQ is a friendly name for workflow breadth, budget, and review depth. It is not a
literal model IQ claim.

| Alias | Effort | Best For | Provider Diversity | Cost / Risk |
|---|---|---|---|---|
| `iq100`, `iq-low` | `low` | Smoke tests and tiny questions | 1 provider ok | Lowest |
| `iq120`, `iq-medium` | `medium` | Everyday research | 1 provider ok | Low |
| `iq140`, `iq-high` | `high` | Default serious reports | 1 provider ok | Moderate |
| `iq150`, `iq-vhigh` | `vhigh` | Important decisions | 2 non-stub providers expected | High |
| `iq160`, `iq-max` | `max` | Deep audits | 2 non-stub providers expected | Very high |
| `iq180`, `iq-ultra` | `ultra` | Exhaustive adversarial passes | 2 non-stub providers expected | Highest |

| Command | Use |
|---|---|
| `python3 -m athenaeum effort --select` | Open the keyboard slider. |
| `python3 -m athenaeum effort --list` | Print effort levels as a table. |
| `python3 -m athenaeum --iq 140 --dry-run "Question"` | Use numeric IQ alias. |
| `python3 -m athenaeum --effort iq-max --dry-run "Question"` | Use named IQ alias. |

High tiers (`vhigh`, `max`, `ultra`) expect at least two available non-stub providers
for live runs. The S9 sanity check enforces provider diversity for expensive work.

## Runtime Matrix

| Runtime | Requires | Best For | Fallback Behavior |
|---|---|---|---|
| `auto` | Optional config/key | Default use | Chooses `api` when live provider is available, otherwise `minimal`. |
| `minimal` | Nothing external | Offline smoke tests | No fallback needed. |
| `api` | Provider config and keys | Live provider runs | Fails sanity if required provider is missing. |
| `opencode` | `opencode` binary | OpenCode project tasks | Reports runtime unavailable. |
| `codex` | `codex` binary | Codex CLI code tasks | Reports runtime unavailable. |
| `claude` | `claude` binary | Claude CLI review/writing | Reports runtime unavailable. |
| `gemini` | `gemini` binary | Gemini CLI tasks | Reports runtime unavailable. |
| `agy` | `agy` binary | AGY CLI tasks | Reports runtime unavailable. |

Inspect runtime availability:

```bash
python3 -m athenaeum doctor
python3 -m athenaeum runtimes list
```

Run one external CLI through ATHENAEUM's JSON result contract:

```bash
python3 -m athenaeum runtimes run opencode "Summarize this repository" --out report.md
```

Runtime commands can be overridden in `thinktank.toml`:

```toml
[runtimes.agy]
command = "agy run --json --workspace {workspace} {prompt_file}"
version_args = ["--version"]
```

## Workflow Modes

| Mode | Command | Use Case | Writes |
|---|---|---|---|
| Ask / deliberate | `python3 -m athenaeum "Question"` | Full answer synthesis | `report.md`, `runs/<id>/` |
| Evolve | `python3 -m athenaeum evolve "A product thesis"` | Idea search | `evolve.md`, `evolve.md.json` |
| Review | `python3 -m athenaeum review draft.md` | Markdown draft critique | `review.md`, `review.md.json` |
| Science | `python3 -m athenaeum science "Hypothesis" --dry-run` | Experiment planning | Preview or `science.md` |
| Watch | `python3 -m athenaeum watch "Track this topic" --daily-budget 3 --for 14d` | Long-running session setup | Session state |
| Daemon | `python3 -m athenaeum daemon run --once` | Consume queued wakes | Updated session state |

## Command Map

| Category | Commands |
|---|---|
| Setup | `setup`, `config init`, `config example`, `providers list`, `providers init` |
| Run | `ask`, bare question, `interactive`, `--dry-run`, `--json` |
| Modes | `evolve`, `review`, `science`, `watch` |
| Runtimes | `doctor`, `runtimes list`, `runtimes run` |
| State | `resume`, `sessions`, `daemon` |
| Design surfaces | `schemas`, `workflows`, `thinkers`, `personas`, `effort`, `reasoning` |

| Goal | Command |
|---|---|
| Show all top-level commands | `python3 -m athenaeum --help` |
| Create example config | `python3 -m athenaeum config init --out thinktank.toml` |
| Preview JSON | `python3 -m athenaeum --json --dry-run "Question"` |
| Force offline mode | `python3 -m athenaeum --minimal --dry-run "Question"` |
| List thinker presets | `python3 -m athenaeum thinkers presets` |
| Use a risk panel | `python3 -m athenaeum --panel risk --dry-run "Question"` |
| Resume a run | `python3 -m athenaeum resume <run-id>` |

## Artifacts

Runs are designed to be inspectable.

| Path | Created By | Contains | Git Ignored? |
|---|---|---|---:|
| `report.md` | Normal runs | Human-readable final report | Yes |
| `runs/<id>/artifacts/plan.json` | Planner | Exact compiled workflow | Yes |
| `runs/<id>/artifacts/*.json` | Loop stages | Research, debate, verify, court, revise outputs | Yes |
| `runs/<id>/journal.jsonl` | Runs | Hash-chained event journal | Yes |
| `runs/<id>/ledger.json` | Runs | Cost/budget ledger | Yes |
| `evolve.md.json` | `evolve` | Structured idea archive | Not by default |
| `review.md.json` | `review` | Structured review results | Not by default |
| `science.md.json` | `science` | Structured experiment plan | Not by default |
| `.thinktank/*.sqlite3` | Sessions/citations | Local SQLite state | Yes |

Generated artifacts are ignored by git so the repository stays source-only.

## Architecture

| Layer | Path | Responsibility |
|---|---|---|
| CLI | `athenaeum/cli.py` | Typer app, setup, interactive shell, JSON output. |
| Planner | `athenaeum/planner.py` | Deterministic pre-run decisions. |
| Workflow | `athenaeum/workflow.py` | Compiled graph and budget estimates. |
| Sanity | `athenaeum/sanity.py` | S1-S9 plan/environment checks. |
| Gateway | `athenaeum/gateway/` | Provider routing, adapters, transport, budget ledger. |
| Runtime | `athenaeum/runtime/` | Minimal, API, and external CLI runtimes. |
| Loops | `athenaeum/loops/` | Research, debate, verify, court, revise, evolve, review, science. |
| Store | `athenaeum/store/` | Citations, claims, sessions. |
| Skill | `skills/athenaeum-think-tank/` | Portable Codex/Claude operating guide. |

## Agent Skill

| Target | Command |
|---|---|
| Codex project | `python3 skills/athenaeum-think-tank/scripts/install_skill.py --target codex --symlink` |
| Codex user | `python3 skills/athenaeum-think-tank/scripts/install_skill.py --target codex-user --symlink` |
| Claude project | `python3 skills/athenaeum-think-tank/scripts/install_skill.py --target claude-project --symlink` |
| Claude user | `python3 skills/athenaeum-think-tank/scripts/install_skill.py --target claude-user` |

The skill teaches agents how to operate ATHENAEUM through commands and config files,
choose IQ/effort settings, use planner previews, and compose safe public thinker panels
without exposing hidden chain-of-thought.

## Development

| Task | Command |
|---|---|
| Run tests | `python3 -m pytest -q` |
| Show CLI help | `python3 -m athenaeum --help` |
| Check runtimes/providers | `python3 -m athenaeum doctor` |
| List providers | `python3 -m athenaeum providers list` |
| Smoke dry-run | `python3 -m athenaeum --json --dry-run --minimal --effort iq-high "Audit reusable skill readiness"` |
| Validate skill | `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" skills/athenaeum-think-tank` |

## Docs

| Document | Audience | What It Covers |
|---|---|---|
| [Technical specification](docs/specs/2026-07-07-think-tank-spec.md) | Maintainers | Full system design and workflow architecture. |
| [CLI visual design notes](docs/specs/2026-07-07-cli-visual-design.md) | CLI/UI contributors | Terminal interface and interaction goals. |
| [Research citations](docs/specs/2026-07-07-research-citations.md) | Researchers | Papers and systems behind the design. |
| [Skill config reference](skills/athenaeum-think-tank/references/config.md) | Agent users | `thinktank.toml` shape and provider notes. |
| [Skill IQ/effort reference](skills/athenaeum-think-tank/references/iq-effort.md) | Agent users | IQ aliases and effort tiers. |
| [Skill provider/runtime reference](skills/athenaeum-think-tank/references/provider-runtime.md) | Agent users | Runtime and provider setup guidance. |

## Safety Notes

| Rule | Why |
|---|---|
| Use `--dry-run` first | It catches plan, budget, provider, and diversity issues before a costly run. |
| Keep keys in env vars | `thinktank.toml` should not contain secrets. |
| Treat thinker panels as lenses | They are critique styles, not impersonation. |
| Prefer IQ/effort for normal use | Provider reasoning controls are advanced overrides. |
| Do not commit generated state | `runs/`, `.thinktank/`, and `report.md` are local outputs. |
