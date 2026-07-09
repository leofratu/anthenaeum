# Case Study: Grok 4.5 Across Athenaeum Effort Tiers

Generated: `2026-07-09T08:16:51Z`
Provider: **Junli** · Model: **grok-4.5**
Endpoint: `https://openapi.junliai.org/v1`

## Question (complex policy debate)

> Should democratic governments ban the open release of frontier open-weight AI models that demonstrably lower the barrier to bioweapon design assistance, or is continued open release net-positive because defenders, academic labs, and red teams need equal access? Steelman both sides, identify load-bearing empirical claims, name the strongest objection to your conclusion, and give a decision framework a national security council could use.

## Effort ladder (engine shape)

| Effort | Tagline | Debaters | Rounds | Scale | Default budget |
|---|---|---:|---:|---|---:|
| `low` | Faster | 2 | 1 | none | $0.50 |
| `medium` | Balanced | 3 | 2 | best_of_2 | $1.50 |
| `high` | Thorough | 4 | 3 | best_of_3 | $5.00 |
| `vhigh` | Relentless | 5 | 4 | tournament-4 | $12.00 |
| `max` | No stone unturned | 6 | 5 | tournament-8 | $30.00 |
| `ultra` | Adversarial exhaustive | 8 | 7 | tournament-16 | $75.00 |

## Compiled plan differences (dry-run)

| Effort | Nodes | Budget | Est. cost | Debate detail |
|---|---:|---:|---:|---|
| `low` | 6 | $1.25 | $0.62 | 2 debaters x 1 rounds |
| `medium` | 6 | $3.75 | $1.86 | 3 debaters x 2 rounds |
| `high` | 6 | $12.50 | $6.20 | 4 debaters x 3 rounds |
| `vhigh` | 6 | $30.00 | $14.88 | 5 debaters x 4 rounds |
| `max` | 6 | $75.00 | $37.20 | 6 debaters x 5 rounds |
| `ultra` | 6 | $187.50 | $93.00 | 8 debaters x 7 rounds |

## Live Grok 4.5 runs

### By effort (`reasoning=high`)

| Effort | Exit | Duration | Words | Claims | Citations | Output |
|---|---:|---:|---:|---:|---:|---|
| `low` | 0 | 87.79s | 886 | 5 | 2 | `runs/case-study-grok/effort-low.md` |
| `medium` | 1 | 37.68s | 0 | 0 | 0 | `runs/case-study-grok/effort-medium.md` |
| `high` | 1 | 0.38s | 0 | 0 | 0 | `runs/case-study-grok/effort-high.md` |
| `vhigh` | 1 | 0.41s | 0 | 0 | 0 | `runs/case-study-grok/effort-vhigh.md` |
| `max` | 1 | 0.37s | 0 | 0 | 0 | `runs/case-study-grok/effort-max.md` |
| `ultra` | 1 | 0.38s | 0 | 0 | 0 | `runs/case-study-grok/effort-ultra.md` |

### By reasoning effort (`effort=medium`)

| Reasoning | Exit | Duration | Words | Claims | Output |
|---|---:|---:|---:|---:|---|
| `off` | 1 | 0.34s | 0 | 0 | `runs/case-study-grok/reasoning-off.md` |
| `high` | 1 | 0.37s | 0 | 0 | `runs/case-study-grok/reasoning-high.md` |
| `xhigh` | 1 | 0.37s | 0 | 0 | `runs/case-study-grok/reasoning-xhigh.md` |

## Qualitative self-evaluation

- Successful effort runs: `low` (1/6).
- Word counts low→high observed: 886 → 886 (sequence: [886]).
- Claim counts: [5].
- Wall times (s): [87.79].
- **Length trend:** not monotonic — API single-shot may not fully exploit multi-node effort knobs.
- **Architecture caveat:** current `ApiRuntime` is one structured completion; multi-loop debate/court depth is fully exercised only under `minimal`/external CLI runtimes. Effort still modulates budget, planner summary, and prompt effort metadata.
- **Unique extremes:** `ultra` is the adversarial maximum (tournament-16 scale, 8×7 debate shape); `low` is the minimum viable path (2×1 debate, $0.50 budget).
- **Decision for operators:** use `low`/`medium` for cheap drafts; `high` for default think-tank; `vhigh`+ when the question is irreversible policy; treat API-mode outputs as single-judge reports unless you switch to multi-agent CLI runtimes.

## Report previews

### `low` · reasoning `high` · 886 words

> # ATHENAEUM Research Report  ## Question Restatement Should democratic governments ban open release of frontier open-weight AI models that demonstrably lower barriers to bioweapon design assistance, or is continued open release net-positive because defenders, academic labs, and red teams need equal access?  ## Steelman: Ban / Restrict Open Release Proponents argue that once weights are public, capability cannot be recalled. If a model measurably reduces the expertise, time, or resources needed f…

### FAIL `medium` / `high`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort medium · reasoning high · budget $3.75 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `high` / `high`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort high · reasoning high · budget $12.50 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `vhigh` / `high`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort vhigh · reasoning high · budget $30.00 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `max` / `high`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort max · reasoning high · budget $75.00 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `ultra` / `high`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort ultra · reasoning high · budget $187.50 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `medium` / `off`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort medium · reasoning off · budget $3.75 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `medium` / `high`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort medium · reasoning high · budget $3.75 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

### FAIL `medium` / `xhigh`

```
◈ ATHENAEUM                                                v0.1.0 · run d81ead07
────────────────────────────────────────────────────────────────────────────────
Q  Should democratic governments ban the open release of frontier open-weight AI
models that demonstrably lower the barrier to bioweapon design assistance, or is
continued open release net-positive because defenders, academic labs, and red
teams need equal access? Steelman both sides, identify load-bearing empirical
claims, name the strongest objection to your conclusion, and give a decision
framework a national security council could use.
⚙  auto workflow · effort medium · reasoning xhigh · budget $3.75 · runtime api
✓  sanity S1-S9 passed · 4 warnings
✓ api gateway dispatch

```

## Method notes

- Runtime: `api` → single gateway completion validated as `ReportOutput` (not multi-node local conductor).
- Effort still changes **planner budget, debate shape, and prompt effort label** fed into the API task.
- Dry-runs show the full multi-node workflow Athenaeum would compile for each tier.
- Seed fixed at `42` for path stability; model sampling may still vary.
- Secrets never written into this report.

## Artifacts

- Raw metrics: `docs/case-studies/grok45-effort-case-study-raw.json`
- Reports: `runs/case-study-grok/*.md`
