# Provider And Runtime Setup

## Codex/Claude Agent Usage

Use this skill from Codex or Claude as procedural guidance. The agent should operate ATHENAEUM through commands and config files, not by roleplaying the whole think tank in one prompt.

Prefer `python3 -m athenaeum` from a checkout because it works before the console script is installed. Use `thinktank` after installing from the repository with `python3 -m pip install -e .` on Python 3.12 or newer.

To install the skill folder for agents:

```bash
python3 skills/athenaeum-think-tank/scripts/install_skill.py --target codex --symlink
python3 skills/athenaeum-think-tank/scripts/install_skill.py --target codex-user --symlink
python3 skills/athenaeum-think-tank/scripts/install_skill.py --target claude-project --symlink
python3 skills/athenaeum-think-tank/scripts/install_skill.py --target claude-user
```

Codex project installs resolve from `.agents/skills/<skill-name>`; Codex user installs resolve from `~/.agents/skills/<skill-name>`. Claude project installs resolve from `.claude/skills/<skill-name>`; Claude user installs resolve from `~/.claude/skills/<skill-name>`. Codex uses the same `SKILL.md` plus `agents/openai.yaml` UI metadata. Claude users should rely on `SKILL.md` plus `references/`; `agents/openai.yaml` is Codex/OpenAI UI metadata only.

Default runtime behavior:

- `auto`: choose provider-backed `api` when a live non-stub provider is available; otherwise use deterministic `minimal`.
- `minimal`: force offline deterministic smoke tests.
- `api`: force ModelGateway/provider-backed execution.
- `codex`, `claude`, `opencode`, `gemini`, `agy`: use the matching external CLI runtime.

## OpenAI-Compatible Responses Config

Preferred config for the user-requested OpenAI-compatible endpoint:

```toml
model_provider = "OpenAI"
model = "gpt-5.5"
review_model = "gpt-5.5"
model_reasoning_effort = "xhigh"
disable_response_storage = true
network_access = "enabled"
windows_wsl_setup_acknowledged = true

[model_providers.OpenAI]
name = "OpenAI"
base_url = "https://openapi.junliai.org"
wire_api = "responses"
requires_openai_auth = true

[features]
goals = true
```

Set `OPENAI_API_KEY` in the environment. Do not put secrets in `thinktank.toml`.

## Common Commands

```bash
python3 -m athenaeum doctor
python3 -m athenaeum providers list
python3 -m athenaeum interactive
python3 -m athenaeum --config thinktank.toml --runtime auto --json --dry-run "Question"
python3 -m athenaeum --config thinktank.toml --runtime api --effort iq-high "Question"
python3 -m athenaeum --runtime auto --iq 140 --dry-run "Question"
python3 -m athenaeum --runtime codex --effort iq-max --dry-run "Repository question"
python3 -m athenaeum --runtime claude --effort iq-high "Document or code review question"
```

## Safety Checks

- Run `--dry-run` before expensive `iq-vhigh`, `iq-max`, or `iq-ultra` runs.
- Configure at least two available non-stub providers before runs with `iq-vhigh`, `iq-max`, or `iq-ultra`; otherwise S9 rejects the plan for insufficient provider diversity.
- Prefer `review_model` or `cheap-judge` on a separate model/provider when judging generated drafts.
- Use `disable_response_storage = true` when the provider supports it and the user asks for no response storage.
- If `api` fails S2 due to missing keys, use `minimal` only for local smoke tests; do not imply it performed live research.
