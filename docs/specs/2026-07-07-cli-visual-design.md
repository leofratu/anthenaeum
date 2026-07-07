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
