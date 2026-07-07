# IQ-Style Effort Presets

Use "IQ" as a user-friendly control for breadth, budget, and adversarial review depth. Do not claim the model has literal IQ.

| User phrasing | ATHENAEUM effort | Typical use |
|---|---|---|
| `iq-low`, `iq100`, `iq110` | `low` | fast checks, smoke tests, small questions |
| `iq-medium`, `iq120` | `medium` | balanced everyday research |
| `iq-high`, `iq130`, `iq140` | `high` | default serious report |
| `iq-vhigh`, `iq-very-high`, `iq150` | `vhigh` | high-stakes review with broader court |
| `iq-max`, `iq160`, `iq-160` | `max` | expensive deep audit, tournament-style review |
| `iq-ultra`, `iq180`, `iq-180` | `ultra` | adversarial exhaustive pass with replication/red-team panels |

Recommended pairing:

```bash
python3 -m athenaeum --runtime auto --effort iq-high "Question"
python3 -m athenaeum --runtime auto --iq 140 "Question"
python3 -m athenaeum --runtime api --effort iq-vhigh --panel risk "Question"
python3 -m athenaeum --runtime codex --effort iq-max --panel iq-max --dry-run "Question"
```

`vhigh`, `max`, and `ultra` require at least two available non-stub providers for sanity checks. Use `iq-high` for single-provider smoke runs or before the second provider is configured.

Interactive equivalents:

```text
/iq
/iq 140
/network enabled
/save-config thinktank.toml
/plan <question>
```

Provider reasoning controls are advanced. Use `/help advanced` and `/reasoning` only when the user explicitly wants to tune provider-specific thinking budgets.

When a user asks to "change effort to IQ settings", keep both terms visible: "IQ setting `iq-high` maps to effort `high`." This preserves CLI compatibility and avoids implying psychometric measurement.
