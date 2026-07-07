# ATHENAEUM — CLI Visual Design Spec

Companion to `2026-07-07-think-tank-spec.md`. Defines the terminal UI: the effort
system, every screen, every animation, and the performance budget. Implementation
target: Python `rich` (Live display) + `textual` widgets where interactivity is
needed. All mockups below are normative — build what you see.

## 1. Effort System

### 1.1 Levels

`--effort low|medium|high|vhigh|max|ultra` (default: `high`). `--iq` is an alias
layer over the same profiles: `120=medium`, `140=high`, `150=vhigh`, `160=max`,
`180=ultra`. Effort is ONE knob that scales the whole deliberation. It multiplies
the workflow, it does not change it.

| | low | medium | high | vhigh | max | ultra |
|---|---|---|---|---|---|---|
| IQ aliases | 100/110 | 120 | 130/140 | 150 | 160 | 180 |
| Tagline | Faster | Balanced | Thorough | Relentless | No stone unturned | Adversarial exhaustive |
| Capability bias | fast | fast+reasoner | reasoner | reasoner | reasoner | reasoner |
| Debaters × rounds | 2 × 1 | 3 × 2 | 4 × 3 | 5 × 4 | 6 × 5 | 8 × 7 |
| Skeptics per claim (K) | 1 | 2 | 3 | 4 | 5 | 7 |
| Scale strategy | none | best_of_2 | best_of_3 | tournament-4 | tournament-8 | tournament-16 |
| Court panels | argument | argument, domain | all 5 | all 5 + PoLL cross-exam | all 5 + PoLL + 2nd revision pass | all panels + replication + red team |
| Evolve generations | 2 | 4 | 6 | 8 | 12 | 16 |
| Reflexion iterations | 1 | 2 | 4 | 6 | 8 | 12 |
| Default budget | $0.50 | $1.50 | $5.00 | $12.00 | $30.00 | $75.00 |

Rules: explicit flags always beat effort defaults (`--effort low --generations 6` →
6 generations). `vhigh`, `max`, and `ultra` REQUIRE ≥2 available non-stub providers for diversity
pinning — the Sanity Checker refuses (S9 hard, not degrade) because these tiers'
value is decorrelated error checking. `max` and `ultra` print cost warnings before starting.

### 1.2 Effort slider — `thinktank effort` (and inline before any run with `-i`)

Interactive slider, keyboard-driven, mirrors this exactly:

```
 Effort

            Faster                                              Smarter
            ────────────────────────────────╴╴─────────▲────────────────
            low      medium     high      vhigh       max       ultra
                                                    ┌─────────────────┐
                                                    │ tournament-8 ·  │
                                                    │ 6 debaters ·    │
                                                    │ full court+PoLL │
                                                    └─────────────────┘
      May use excessive tokens and long deliberation. Use for the hardest questions.

 ←/→ to adjust · Enter to confirm · Esc to cancel
```

- Track: single box-drawing line; the segment left of the marker is dim
  (`grey42`), right of it bright (`medium_purple2`). Marker `▲` sits under the track,
  in the tier's accent color.
- Selected tier label is **bold + accent color**; others `grey62`. Under the selected
  label a 1-line (low–high) or boxed 3-line (vhigh/max) capsule summarizes what the
  tier buys.
- One description line below in `grey58`; per-tier copy:
  - low — "Skims. One pass, no debate. For quick orientation."
  - medium — "Balanced. Light debate, key claims checked."
  - high — "Thorough. Full court review, all claims triaged."
  - vhigh — "Relentless. Provider-diverse panels, tournament selection."
  - max — "May use excessive tokens and long deliberation. Use for the hardest questions."
  - ultra — "Adversarial exhaustive. Replication and red-team panels."
- Footer hint line: `←/→ to adjust · Enter to confirm · Esc to cancel` in `grey46`.
- Tier accent colors: low `steel_blue`, medium `cyan3`, high `medium_purple2`,
  vhigh `orchid`, max `orange3`, ultra `gold1` (bold). These accents recur in every screen (§3).

## 2. Screens

### 2.1 Launch header (every run)

```
 ◈ ATHENAEUM                                                 run 7f3a-9c
 ─────────────────────────────────────────────────────────────────────────
 Q  Should the EU regulate open-weight models?
 ⚙  auto workflow · effort high · budget $5.00 · audience policy-makers
 ✓  sanity S1–S9 passed · 3 providers · runtimes: api, claude, codex
```

`◈` logo glyph in the effort accent color. Sanity line appears ONLY after checks
pass; failures render the fix-it table instead and exit.

### 2.2 Live run view — the deliberation tree

One `rich.Live` tree, updated in place (no scroll spam). Node states:
queued `·` (grey) → running <spinner> (accent) → done `✓` (green) / warn `!`
(yellow) / failed `✗` (red, with one-line reason).

```
 ▾ research                                    ✓ 42 sources · $0.61 · 1:12
 ▾ debate    round 3/3                         ⠧ 4 debaters · 2 converged
 │   ├─ economist(gpt-5)        arguing ⠋
 │   ├─ security(claude)        merged → joint-2 ✓
 │   └─ civil-liberties(gemini) arguing ⠙
 ▾ verify    claims 31/54                      ⠧ ✓24 ⚑3 ?4 · $0.38
 · court                                       queued
 · revise                                      queued
 ─────────────────────────────────────────────────────────────────────────
 $1.24 / $5.00 ▐████████░░░░░░░░░░░░▌ 24%          elapsed 3:41 · est 9m
```

Budget bar fills in the effort accent; flips to `orange3` at 80%, `red` at 95%
(watchdog degradation events print one dim line under the bar, never a popup).

### 2.3 Verdict ticker (verify + court phases)

Claims/findings stream as single dim lines under their node, max 3 visible,
oldest fades out (rendered by truncation, cheap):

```
 ▾ court
 │   argument   ⠸ auditing 12 chains
 │     └ ✗ blocker: conclusion §4 rests on contested growth figure
 │   audience   ✓ 2 major · CFO reader loses thread at §3
 │   thinker    ⠼ einstein: running limit-case probe on §2 model
```

### 2.4 Completion card

```
 ─────────────────────────────────────────────────────────────────────────
 ✓ Report ready                                    report.md · 2,840 words
   claims: 47 verified · 3 contested · 2 unverified (marked inline)
   court:  0 blockers · 2 major addressed · score 8.1 → 9.2 over 3 revisions
   cost:   $3.87 of $5.00 · 11:32 · artifacts in runs/7f3a-9c/
```

### 2.5 Dry-run and doctor

`--dry-run`: renders the same tree fully expanded, all nodes `·`, with a per-node
table column set: `runtime · resolved model · est tokens · est $`. Total row bold.
`doctor`: checklist rows, `✓`/`✗` + one fix-it line per failure:

```
 ✓ anthropic key        live (14ms)
 ✗ codex cli            not found — brew install codex, or --runtime api
 ✓ gemini cli           v0.9.4
```

## 3. Animations — one per effort tier

The working-state spinner is the run's visual signature and scales with effort:
higher effort *visibly deliberates harder*. All are frame lists cycled by `rich`;
frame budgets in §4. Each animation uses only its tier's accent color + greys, so a
glance at any running node tells you the effort level.

| Tier | Name | Frames (cycle) | Feel |
|---|---|---|---|
| low | **dot** | `.  `→`.. `→`...` | minimal, 3 fps |
| medium | **braille** | `⠋⠙⠸⠴⠦⠇` | standard worker, 8 fps |
| high | **pulse** | `▁▂▃▅▃▂` rendered as a 5-char wave sliding under the node label | steady heartbeat, 10 fps |
| vhigh | **council** | `◐◓◑◒` × N glyphs, one per live agent, each phase-offset; converged agents freeze to `●` | you can SEE the panel deliberating and converging, 12 fps |
| max | **orbit** | 7-char field `∙ ∘ ○ ◉ ○ ∘ ∙` with the bright core `◉` sweeping left↔right (Larson scanner); on each loop-iteration completion, a 300ms full-width shimmer in `orange3` | relentless sweep; iteration shimmer marks real progress, 15 fps |
| ultra | **redteam** | alternating `◇◆◇` / `◆◇◆` plus replication ticks on completed checks | adversarial exhaustive pass, 18 fps cap |

Phase-transition flourishes (all ≤400ms, all skippable):

- node completes: spinner collapses into `✓` with a single `▸✓` slide-in frame.
- debate convergence: the two debater lines visually merge — one 2-frame `╲╱` join.
- verify verdict lands: claim line flashes its verdict color once (green/yellow/red).
- max-tier run start: the header `◈` plays a 5-frame bloom `·∘○◉◈` — once.

`--no-anim` (or `NO_COLOR`/non-TTY/CI detection) replaces ALL animations with
static state glyphs and disables Live refresh (plain line-per-event logging).

## 4. Performance budget (hard requirements)

The user explicitly requires very high perf at `vhigh`/`max` — exactly when the
most agents stream concurrently. Rules:

- **UI never blocks orchestration.** Rendering runs on its own thread consuming a
  bounded `deque(maxlen=1024)` of `UiEvent`s; orchestrator writes are non-blocking
  (drop-oldest on overflow — the tree is state-rendered, so dropped deltas cannot
  corrupt it, next render reads current state).
- **Frame cap by tier:** refresh ≤ 15 fps even at max; `rich.Live(refresh_per_second)`
  set per tier (3/8/10/12/15). Never render on every event — render on tick.
- **Render cost ceiling:** one full tree render ≤ 8ms at 100 visible nodes on a
  reference M-class laptop; measured in CI with a synthetic 200-agent run. If a
  render exceeds 8ms twice consecutively, the renderer auto-collapses done subtrees
  (keeps last 2) and halves fps — logged, reversible with `R` key.
- **O(visible) rendering:** collapsed/done subtrees render from a cached string;
  only running nodes re-render per tick.
- **Memory:** ticker lines and transcripts stream to the journal, not to the UI
  state; UI holds at most the visible window (no unbounded transcript buffers).
- **Degradation ladder (UI):** >120 live agents → council/orbit animations swap to
  braille automatically; >4 dropped-frame warnings → `--no-anim` mode with a notice.
- Startup to first paint < 150ms (defer provider probes until after header paints).

## 5. Input & keys (live view)

`←/→` adjust effort (only at the pre-run slider) · `p` pause session · `q` graceful
stop (checkpoint + resume hint) · `v` toggle verdict ticker · `c` collapse done ·
`R` restore auto-degraded rendering · `?` key help footer toggle.

## 6. Theming

Default theme "midnight": background-agnostic (never sets bg color), accents per
tier (§1.2), greys for chrome. `thinktank.toml [ui]` allows `theme = "mono"`
(no color, glyphs only) and `accent_override`. All glyphs have ASCII fallbacks
(`✓→ok`, `⚑→!`, `◈→#`, spinners→`|/-\`) selected automatically when the terminal
lacks UTF-8.
