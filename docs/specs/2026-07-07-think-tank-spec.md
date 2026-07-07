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
