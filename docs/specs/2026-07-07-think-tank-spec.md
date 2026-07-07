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
