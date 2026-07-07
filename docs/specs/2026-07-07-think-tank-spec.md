# ATHENAEUM — A Multi-Agent AI Think Tank

**Technical Specification v1.0** · 2026-07-07 · Status: Draft for implementation

---

## 0. Abstract

ATHENAEUM is a CLI-driven, provider-agnostic multi-agent deliberation engine. Given a
question, it assembles a heterogeneous fleet of AI agents — backed by raw LLM APIs *and*
full coding-agent harnesses (Claude Code, Codex CLI, Gemini CLI) — that research,
debate, evolve, adversarially verify, and review a position until it survives scrutiny,
then emits a fully cited, audience-tailored report.

Its claim to novelty is the **combination**, which no published system implements:

1. A **quality-diversity evolutionary loop over arguments** (MAP-Elites lineage —
   FunSearch, AlphaEvolve — applied to theses instead of code).
2. A **Toulmin-structured adversarial Reviewer Court** with argument auditing,
   audience modeling, sentiment calibration, thinker-emulation panels, and
   domain-expert review.
3. **Heterogeneous agent runtimes** — API models and external agent CLIs — behind one
   deterministic orchestrator with a compiled, sanity-checked workflow graph.
4. **Epistemic bookkeeping**: every factual claim is ledgered, independently attacked
   by skeptic agents, and carries a visible verification status into the final report.

All loop designs cite their source literature (§10 and the companion bibliography).

## 1. Goals & Non-Goals

### 1.1 Product modes

| Mode | Command | Output |
|---|---|---|
| Deep research report | `thinktank "question"` | Cited, verified report (`report.md`) |
| Idea generation & critique | `thinktank evolve "prompt"` | Ranked archive of diverse, stress-tested ideas |
| Decision / policy analysis | `thinktank ask "..." --mode decide` | Recommendation memo with stakeholder & risk models |
| Autonomous science loop | `thinktank science "hypothesis"` | Experiment logs + write-up from a sandboxed lab |
| Standalone review | `thinktank review draft.md` | Reviewer Court verdicts on an existing document |

### 1.2 Hard requirements

- **R1 — Provider agnostic.** No hard dependency on any single LLM vendor. All model
  access goes through the ModelGateway (§3). Adding a provider is a config entry, not code.
- **R2 — Minimal usage.** `thinktank "question"` with only API keys in the environment
  must produce a complete report. Zero mandatory config files.
- **R3 — Sanity-checked workflows.** No expensive execution before the workflow graph
  passes static validation and (optionally) a stub dry-run (§6).
- **R4 — External CLI runtimes.** Worker agents can be executed by Codex CLI, Gemini
  CLI, Claude Code, or any configurable CLI via the Runtime interface (§4).
- **R5 — Frontier loops.** Debate, reflexion, evolutionary, adversarial-verify,
  research, science, and budget-aware test-time-scaling loops are first-class,
  deterministic engine constructs (§5).
- **R6 — Hyper-advanced review.** Five reviewer classes with structured verdicts and
  bias-mitigated judging (§7).
- **R7 — Budget ceilings.** Every run has a hard cost ceiling; the Ledger meters every
  token across every provider and runtime.
- **R8 — Resumability.** Append-only run journal; any run can be resumed after a crash
  or kill with completed steps served from cache.

### 1.3 Non-goals (v1)

Web UI · model fine-tuning · real-time multi-user collaboration · autonomous
publishing/posting of outputs (reports are written to disk only) · persuasion
optimization against specific individuals (explicitly out of scope for safety; the
Audience Modeler adapts *clarity and register*, not manipulation).

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI (`thinktank`)                                                  │
└───────────────┬─────────────────────────────────────────────────────┘
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR — deterministic asyncio orchestrator                     │
│  ┌───────────────────────┐  ┌─────────────────────────────────────┐ │
│  │ Workflow Compiler     │→ │ Sanity Checker (static + dry-run)   │ │
│  └───────────────────────┘  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ LOOP ENGINE: debate · reflexion · evolve · verify · research    ││
│  │              science · scale (test-time compute policy)         ││
│  └─────────────────────────────────────────────────────────────────┘│
└───────┬──────────────────────────────┬──────────────────────────────┘
        ▼                              ▼
┌──────────────────────┐   ┌──────────────────────────────────────────┐
│  AGENT RUNTIME LAYER │   │  REVIEWER COURT                          │
│  ├─ ApiRuntime ──────┼─┐ │  argument · audience · sentiment ·       │
│  ├─ ClaudeCodeRuntime│ │ │  thinker-panel · domain — → chief justice │
│  ├─ CodexRuntime     │ │ └──────────────────────────────────────────┘
│  ├─ GeminiCliRuntime │ │
│  └─ GenericCliRuntime│ │ ┌──────────────────────────────────────────┐
└──────────────────────┘ └▶│  MODEL GATEWAY (multi-provider router)   │
                           └──────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE SUBSTRATE: episodic memory · claim ledger · citation DB  │
│  LEDGER: cost metering · budget enforcement · OTel traces · journal │
└─────────────────────────────────────────────────────────────────────┘
```

**Language/stack:** Python ≥3.12, `asyncio`, `pydantic` v2 for all schemas, `typer`
for the CLI, `rich` for progress rendering, SQLite (WAL) + JSONL files for storage.
No web server. Package name `athenaeum`, console script `thinktank`.

**Design stance:** control flow is *deterministic code*; intelligence lives inside
node boundaries. Models never decide the workflow shape at runtime — they fill slots
in a compiled graph. This is the inverse of "LLM-as-router" frameworks and is what
makes the Sanity Checker (§6) possible.

## 3. ModelGateway — provider-agnostic model access

### 3.1 Interface

```python
class ModelGateway(Protocol):
    async def complete(self, req: CompletionRequest) -> CompletionResult: ...
    async def complete_json(self, req: CompletionRequest,
                            schema: type[BaseModel],
                            max_repair_attempts: int = 3) -> BaseModel: ...
    def resolve(self, capability: Capability) -> ResolvedModel: ...
    def probe(self) -> list[ProviderHealth]:          # used by `thinktank doctor`
        ...
```

`CompletionRequest` carries: messages, capability tag OR explicit model id, max_tokens,
temperature, seed (where supported), tool definitions, and a `BudgetToken` (§9.3) that
the gateway debits before dispatch — a request without remaining budget raises
`BudgetExceeded` instead of calling any provider.

### 3.2 Capability-based routing

Nodes never name vendor models. They request **capabilities**; `routes.toml` (or
built-in defaults) maps capabilities to ordered fallback chains:

```toml
[routes]
reasoner     = ["anthropic/claude-fable-5", "openai/o4", "google/gemini-3-pro"]
fast         = ["anthropic/claude-haiku-4-5", "openai/gpt-5-mini", "groq/llama-4"]
long-context = ["google/gemini-3-pro", "anthropic/claude-fable-5"]
cheap-judge  = ["openai/gpt-5-mini", "anthropic/claude-haiku-4-5", "mistral/small"]
embedder     = ["openai/text-embedding-4", "voyage/voyage-4"]
```

Routing rules:

- **Fallback:** on 429/5xx/timeout, advance down the chain with jittered exponential
  backoff; the Ledger records which model actually served each call.
- **Diversity pinning:** loop nodes may declare `diversity: provider` — the engine then
  assigns *distinct providers* to sibling agents (debaters, skeptics, judges) to
  decorrelate errors. If fewer providers are configured than siblings, it degrades to
  distinct models, then distinct temperatures, and logs the degradation.
- **Judge/generator separation:** the compiler rejects any graph where a judge node
  resolves to the same model that produced the artifact it judges, unless the node
  sets `allow_self_judge: true` (mitigates self-preference bias in LLM-as-judge).

### 3.3 Provider adapters

Thin adapters normalize each provider to one internal shape: `anthropic`, `openai`
(also covers any OpenAI-compatible endpoint: OpenRouter, Together, Groq, vLLM,
Ollama), `google`. Everything else rides the OpenAI-compatible adapter. Adding a
provider = one `[providers.X]` config block (base_url, key env var, model list, price
table). No SDK dependencies beyond `httpx`.

### 3.4 Structured output portability

`complete_json()` enforces a Pydantic schema across providers that differ in native
JSON-schema support: (1) use native strict/structured mode when the provider offers
it; (2) otherwise inject the schema into the prompt and validate; (3) on validation
failure, send the error back for `max_repair_attempts` repair rounds; (4) final
failure raises `SchemaError`, which the engine treats as a node failure (retryable on
a fallback model). All inter-agent messages ride this path — there is no free-text
inter-agent protocol.

## 4. Agent Runtime Layer

### 4.1 The Runtime interface

A **runtime** is *how* an agent executes; a **capability** is *which brain* it uses.

```python
class Runtime(Protocol):
    name: str
    async def spawn(self, task: AgentTask, ws: Workspace) -> AsyncIterator[AgentEvent]: ...
    def health(self) -> RuntimeHealth      # binary on PATH? version? auth OK?
```

`AgentTask` = {role prompt, input payload, output schema, tool policy, budget token,
deadline}. `AgentEvent` = progress | tool_call | cost_delta | final(AgentResult).
Every runtime must terminate with exactly one `final` event whose payload validates
against the task's output schema.

### 4.2 Implementations

| Runtime | Backing | Invocation | Use for |
|---|---|---|---|
| `ApiRuntime` | ModelGateway directly | in-process tool loop (web_search, fetch, read_file) | cheap/fast nodes: judges, extractors, debater turns |
| `ClaudeCodeRuntime` | Claude Code headless | `claude -p <task> --output-format stream-json --max-turns N` | repo analysis, heavy tool use |
| `CodexRuntime` | OpenAI Codex CLI | `codex exec --json -C <workspace> <task>` | code experiments, science loop |
| `GeminiCliRuntime` | Gemini CLI | `gemini -p <task> --output-format json` | long-context source digestion |
| `GenericCliRuntime` | any CLI | command template from config: `cmd = "mytool run {task_file}"` | future CLIs (Aider, OpenHands, …) |

CLI runtimes share a common subprocess harness: task rendered to a prompt file in an
isolated `Workspace` directory, stdout parsed as a JSON event stream (or tail-JSON for
CLIs without streaming), wall-clock deadline + token-budget kill switch, and a final
"emit your answer as JSON matching this schema into result.json" convention with an
`ApiRuntime` repair pass if the file fails validation. Sandboxing: CLI runtimes run
with the working directory jailed to the Workspace; the science loop additionally
requires the runtime's own sandbox flag (e.g. Codex `--sandbox workspace-write`).

### 4.3 Runtime selection

Defaults per node type live in the workflow templates; overridable per run
(`--runtime codex`) or per node in `thinktank.toml`. The Sanity Checker verifies each
selected runtime's `health()` before execution and rewires to `ApiRuntime` fallback
(with a warning) when a CLI is missing, unless the node is marked `requires: cli`.

## 5. Loop Engine

Loops are declarative node types in the workflow graph. Every loop MUST declare
`max_iterations` **and** a convergence predicate — the compiler rejects loops with
neither (§6.2, rule S7). All loops emit per-iteration journal events for resume.

### 5.1 Debate Loop — `loop: debate`

Basis: Du et al. 2023 (arXiv:2305.14325); sparse/dynamic topologies from DyLAN
(2310.02170) and GPTSwarm (2402.16823).

- N debaters (default 4, `diversity: provider`) receive the question plus the research
  dossier and produce a structured `Position{thesis, toulmin_args[], concessions[]}`.
- Rounds: each debater sees a *sampled subset* (default 2) of opposing positions —
  sparse topology, which the literature shows matches full all-to-all exchange at a
  fraction of the cost. A moderator node computes pairwise stance similarity
  (embedding + rubric) and prunes converged debater pairs into a joint position.
- **Degeneracy guard:** if inter-debater agreement exceeds 0.9 before round 2 (sycophantic
  collapse), the engine injects a contrarian debater prompted to argue the strongest
  minority position.
- Convergence: stance-similarity plateau OR max 5 rounds. Output: surviving positions
  ranked with their strongest unresolved objections (never silently dropped).

### 5.2 Reflexion Loop — `loop: reflexion`

Basis: Reflexion (2303.11366), Self-Refine (2303.17651).

Two scopes: **intra-run** — draft → Reviewer Court verdicts → targeted revision, until
court score plateaus (delta < ε for 2 iterations) or 4 iterations; **cross-run** —
after each run, a reflector distills `Lesson{topic_tags, what_failed, directive}`
records into episodic memory (§8.1). New runs retrieve top-k lessons by topic
similarity and inject them into planner and writer prompts. Lessons carry a decay
half-life so stale directives lose weight.

### 5.3 Evolutionary Loop — `loop: evolve`

Basis: FunSearch (Nature 2023), AlphaEvolve (2025), Darwin Gödel Machine
(2505.22954) archives; MAP-Elites quality-diversity. **Novel transfer: the genome is
an argument, not a program.**

- **Genome:** `Thesis{claim, toulmin_args[], evidence_refs[], assumptions[]}`.
- **Archive (MAP-Elites grid):** behavioral axes = (novelty ∈ conventional…heterodox,
  risk posture ∈ conservative…aggressive, time horizon ∈ near…far). Each cell keeps
  the highest-fitness thesis; diversity is preserved structurally, not by prompt
  begging.
- **Fitness:** composite from the Reviewer Court — evidence strength (argument
  auditor) + verified-claim ratio (claim ledger) + audience fit (audience modeler),
  weights configurable.
- **Operators:** `steelman` (strengthen weakest warrant), `attack-and-repair` (skeptic
  finds the best objection, repairer patches or concedes), `cross-pollinate` (merge
  argument branches of two elite parents), `radicalize` / `moderate` (move along an
  axis — exploration pressure).
- Generation: sample parents from archive (uniform over filled cells — favors
  diversity), apply operators via `fast` models, evaluate via cheap court, admit to
  archive if cell-best. Termination: `--generations G` (default 6) or loop-until-dry:
  2 consecutive generations with no admissions.

### 5.4 Adversarial Verify Loop — `loop: verify`

Basis: LLM-as-judge bias literature; jury/panel evaluation (PoLL, 2404.18796);
debate-for-oversight results showing refutation beats affirmation for error-finding.

1. An extractor decomposes the draft into atomic factual claims → claim ledger rows.
2. Claims are triaged by (load-bearingness × checkability); the budget is spent
   top-down — no silent cap: unchecked claims are marked `unverified`, never implied-true.
3. Per claim, K skeptics (default 3, provider-diverse) are prompted to **refute** it
   with tool access (web search, arXiv, source re-fetch). Default-to-refuted framing
   counters agreement bias.
4. Verdict fusion: ≥⌈K/2⌉ refute → claim removed or rewritten; split → `contested`
   with both sources cited; none → `verified` with citations attached.
5. The writer must re-render the report so every claim's epistemic status is visible
   (verified silently, `[contested]` / `[unverified]` markers inline; summary table in
   an appendix).

### 5.5 Research Loop — `loop: research`

Basis: STORM (2402.14207) and Co-STORM perspective-guided questioning; deep-research
agent patterns; gpt-researcher's planner/executor split.

- **Perspective discovery:** survey agent finds 4–6 stakeholder/disciplinary
  perspectives on the topic.
- **Question generation:** per perspective, a questioner in simulated conversation
  with a topic-expert agent produces concrete research questions (STORM's key trick —
  perspective-grounded questions beat generic decomposition).
- **Multi-modal sweep:** parallel searchers per question × modality: web, arXiv/paper
  search, GitHub repos (code-as-evidence, via a CLI runtime when deep repo reading is
  needed), news. Each source is digested to `SourceNote{url, quotes[], reliability, stance}`.
- **Outline-grounded synthesis:** outline built from perspectives × findings; a
  `long-context` writer drafts section-by-section citing only ledgered SourceNotes —
  the writer cannot introduce uncited facts (extractor cross-checks, §5.4 catches leaks).

### 5.6 Science Loop — `loop: science` (opt-in mode)

Basis: AI Scientist v2 (Sakana 2025), Agent Laboratory (2501.04227), Google AI
co-scientist tournament refinement (2025).

hypothesize (evolve loop over hypotheses, fitness = novelty × testability) →
plan experiment (methods reviewer must approve power/confounds before spend) →
execute (CodexRuntime or ClaudeCodeRuntime in a sandboxed `--sandbox ./lab`
workspace; deterministic seeds; artifacts retained) → analyze (separate agent,
never the experimenter, to avoid motivated reasoning) → write-up → Reviewer Court
with a methods-focused domain reviewer. Hard rails: no network installs beyond an
allowlist, no writes outside the sandbox, wall-clock and cost ceilings per experiment.

### 5.7 Test-Time Scaling Policy — `scale:` block on any node

Basis: compute-optimal test-time scaling (2408.03314); Google co-scientist Elo
tournaments.

Any node may declare `scale: {strategy, n, judge}`: `best_of_n` (n samples → PoLL
panel picks; cheap nodes), `tournament` (single-elim pairwise judging with order
swap; expensive nodes), `self_consistency` (majority over extracted answers;
classification-shaped nodes). The Conductor allocates the scaling budget from the
run's remaining ceiling: scaling is the *first* thing degraded (n reduced, tournament
→ best-of-2) when the Ledger projects overrun, and the degradation is logged to the
report appendix.

### 5.8 Long-Running Loops — `duration:` block on any loop

Loops in §5.1–5.6 are bounded within a single run. A loop may additionally declare a
`duration` block that promotes it to a **long-running loop**: a session that persists
for hours or days, survives process restarts, and accumulates results incrementally.

```yaml
research:
  loop: research
  duration: {mode: continuous, checkpoint_every: 10m, budget_per_day: 3.00,
             wake: [{cron: "0 7 * * *"}, {on: new_sources}], max_age: 14d}
```

Semantics:

- **Checkpointing:** the loop's full state (archive, claim ledger cursor, memory
  writes, iteration counters) is snapshotted to the journal every
  `checkpoint_every` and at every iteration boundary. Recovery is exactly `resume`
  (§8.3) — a long-running loop is *defined* as a loop whose every iteration is
  individually resumable; the compiler rejects a `duration` block on any node whose
  iteration state cannot be journaled (rule S10).
- **Scheduler:** a lightweight daemon (`thinktank daemon`, launchd/systemd unit
  provided) wakes sessions on `cron` expressions or on events: `new_sources` (a
  cheap sweep found material newer than the last checkpoint), `budget_refresh`
  (daily budget re-minted), `manual` (`thinktank poke <session-id>`). Between wakes
  the process exits — no idle token burn, no resident LLM state.
- **Budget over time:** `budget_per_day` mints a fresh daily `BudgetToken`; unspent
  budget does NOT roll over by default (`rollover: true` to allow, capped at 3×
  daily). The Ledger tracks lifetime spend; `max_age` or `budget_lifetime` hard-stops
  the session with a final report.
- **Incremental output:** each wake that changes conclusions re-renders the report
  with a dated changelog section ("what changed since <last checkpoint>: claim X
  moved contested→refuted, new elite thesis in cell (heterodox, near-term)").
  Unchanged wakes append only a heartbeat line to the journal.
- **Drift control:** long-running evolve/research sessions re-run the *verify loop*
  on previously `verified` claims older than `reverify_after` (default 7d) — sources
  rot, papers get retracted. Status downgrades propagate to the argument map and can
  reopen court findings.
- **Sanity checks for long-running mode** (extends §6.2): S10 — every iteration
  journaled/resumable; S11 — daemon installed & schedulable (else abort with the
  launchd/systemd install hint); S12 — `budget_per_day × expected_days ≤
  budget_lifetime`; S13 — wake events resolvable (a `new_sources` wake requires the
  research loop's source queries to be persisted).

CLI surface:

```
thinktank watch "question" --daily-budget 3.00 --for 14d   # start a long-running session
thinktank sessions [list|show|pause|resume|stop <id>]      # manage them
thinktank poke <id>                                        # force a wake now
```

## 6. Workflow Compiler & Sanity Checker

### 6.1 Compilation

CLI mode + flags select a **workflow template** (YAML, shipped in-package; user
templates in `.thinktank/workflows/`). Templates declare nodes, edges, loop blocks,
capabilities, runtimes, schemas, and budget shares. The compiler resolves them into a
frozen `ExecutionGraph` — after compilation nothing about the shape can change at
runtime; only node *contents* are model-generated.
