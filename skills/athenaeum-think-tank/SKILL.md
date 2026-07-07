---
name: athenaeum-think-tank
description: Guide Codex or Claude agents using ATHENAEUM/thinktank as an interactive OpenCode-like CLI for provider/model setup, auto/API/CLI runtimes, effort/IQ aliases, planner previews, goals, and expert-panel deliberation. Use when configuring or operating ATHENAEUM think-tank runs, creating thinktank.toml, choosing OpenAI-compatible Responses settings, selecting IQ-style effort, explaining commands, or composing safe public thinker lenses/personas without hidden chain-of-thought.
---

# ATHENAEUM Think Tank

Use ATHENAEUM as an orchestration CLI, not as a single prompt. Prefer concrete `thinktank` commands, local config, planner previews, and evidence-grounded panel runs.

Command note: prefer `python3 -m athenaeum` from a checkout because it works without installing the console script. Use `thinktank` after installing editable mode with `python3 -m pip install -e .` on Python 3.12 or newer.

Install note: this source folder is the canonical skill. To expose it to Codex or Claude Code, run [scripts/install_skill.py](scripts/install_skill.py) with `--target codex` for project `.agents/skills`, `--target codex-user` for `~/.agents/skills`, `--target claude-project` for project `.claude/skills`, or `--target claude-user`; add `--symlink` to avoid duplicate copies.

## Workflow

1. Inspect local capabilities before advising commands: use `python3 -m athenaeum --help`, `python3 -m athenaeum doctor`, `python3 -m athenaeum providers list`, and `python3 -m athenaeum runtimes list`. If `thinktank` is on `PATH`, the same arguments work with `thinktank`.
2. Configure providers in `thinktank.toml` when live model access is needed. Read [references/config.md](references/config.md) for the preferred OpenAI-compatible Responses shape and `features.goals`; read [references/provider-runtime.md](references/provider-runtime.md) for runtime selection and Codex/Claude usage.
3. Choose runtime deliberately:
   - `auto` for default behavior: provider-backed `api` when a live non-stub provider is available, otherwise deterministic `minimal`.
   - `minimal` for deterministic local smoke tests and offline previews.
   - `api` for explicit ModelGateway/provider-backed runs.
   - `opencode`, `codex`, `claude`, `gemini`, or `agy` when delegating to an external CLI runtime.
4. Treat IQ/effort as the main quality knob. Use `--iq 140`, `--effort iq-high`, interactive `/iq`, or `/effort`; `/iq` and `/effort` open the slider in interactive mode. For single-provider smoke checks, prefer `high` or lower; `vhigh`, `max`, and `ultra` require at least two available non-stub providers.
5. Keep provider reasoning controls advanced. `--reasoning-effort` and `/reasoning` still exist for OpenAI/Anthropic/Gemini tuning, but default setup should steer users to IQ/effort. Read [references/iq-effort.md](references/iq-effort.md). Do not describe IQ aliases as literal model IQ.
6. Preview before expensive runs with `--dry-run`, `--json --dry-run`, or interactive `/plan`.
7. Track user intent with goals when enabled: `/goal <objective>`, `/settings`, `/goal complete`, and resume commands when applicable.
8. Use public thinker lenses only as critique-diversity styles. Read [references/thinker-lenses.md](references/thinker-lenses.md) and [references/panel-presets.md](references/panel-presets.md) before building an expert panel. Prefer named presets such as `--panel risk`, `--panel foundations`, or `--panel iq-ultra` when they fit.

## Command Patterns

```bash
python3 -m athenaeum setup --provider OpenAI --model gpt-5.5 --review-model gpt-5.5 --model-reasoning xhigh --base-url https://openapi.junliai.org --network enabled --disable-storage --goals --out thinktank.toml --force
python3 -m athenaeum doctor
python3 -m athenaeum providers list
python3 -m athenaeum thinkers presets
python3 -m athenaeum interactive
python3 -m athenaeum --config thinktank.toml --runtime auto --iq 140 --dry-run "Should we ship this policy?"
python3 -m athenaeum --runtime api --effort iq-vhigh --panel risk "What are the failure modes?"
```

Installed console equivalent:

```bash
thinktank doctor
thinktank providers list
thinktank --json --dry-run --minimal --effort iq-high --reasoning-effort max "Audit reusable skill readiness"
```

Skill install examples:

