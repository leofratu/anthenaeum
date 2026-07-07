# ATHENAEUM Config Reference

Use this shape for `thinktank.toml` when the user wants a portable live-provider setup. Keep API keys in environment variables, not in the file.

Generate it from the CLI:

```bash
python3 -m athenaeum setup --provider OpenAI --model gpt-5.5 --review-model gpt-5.5 --model-reasoning xhigh --base-url https://openapi.junliai.org --network enabled --disable-storage --goals --out thinktank.toml --force
```

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
# requires_openai_auth uses OPENAI_API_KEY from the environment.

[features]
goals = true
```

Operational notes:

- With no config and a supported env key, `--runtime auto` can select provider-backed `api`; without a live provider it falls back to `minimal`.
- Supported provider kinds are `stub`, `openai`, `openai-compatible`, `anthropic`, and `google`.
- Zero-config environment defaults are available for every matching env key among `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GOOGLE_API_KEY` when no explicit `[providers]` table is present.
- `model_provider` may match the provider key (`openai`) or display name (`OpenAI`).
- `requires_openai_auth = true` maps the provider to `OPENAI_API_KEY`.
- `wire_api = "responses"` selects the OpenAI-compatible Responses wire format.
- `model` routes `reasoner`, `fast`, and `long-context`; `review_model` routes `cheap-judge`.
- `model_reasoning_effort` sets the default provider reasoning profile. Treat it as an advanced provider override; normal users should steer quality with `--iq`, `--effort`, or the interactive `/iq` slider.
- `features.goals = true` records goal support in portable config. Current interactive builds expose `/goal` commands directly.
- Validate with `thinktank doctor` and `thinktank providers list` before running a costly session.

## Direct Gateway Config

Use direct `[providers]` and `[routes]` when the setup needs multiple providers, custom model routing, prices, or provider-specific reasoning overrides.

```toml
[routes]
reasoner = ["openai/gpt-5.5", "anthropic/claude-fable-5"]
fast = ["openai/gpt-5.5-mini"]
long-context = ["anthropic/claude-fable-5"]
cheap-judge = ["google/gemini-3-flash"]

[providers.openai]
kind = "openai-compatible"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
key_env = "OPENAI_API_KEY"
models = ["gpt-5.5", "gpt-5.5-mini"]
disable_response_storage = true

[providers.openai.prices."*"]
input = 0.0
output = 0.0

[providers.openai.reasoning_overrides.xhigh]
effort = "high"

[providers.anthropic]
kind = "anthropic"
key_env = "ANTHROPIC_API_KEY"
models = ["claude-fable-5", "claude-haiku-4-5"]

[providers.google]
kind = "google"
key_env = "GOOGLE_API_KEY"
models = ["gemini-3-pro", "gemini-3-flash"]
```

For `vhigh`, `max`, or `ultra` effort, configure at least two available non-stub providers so the S9 sanity check can confirm provider diversity. Use `iq-high` for single-provider smoke examples.
