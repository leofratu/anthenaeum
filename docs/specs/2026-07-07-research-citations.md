# ATHENAEUM — Annotated Research Bibliography

Companion to `2026-07-07-think-tank-spec.md`. Each entry: what it showed, and what
ATHENAEUM takes from it.

## Multi-agent debate & communication topology

- **Du, Li, Torralba, Tenenbaum, Mordatch (2023). "Improving Factuality and Reasoning
  in Language Models through Multiagent Debate."** arXiv:2305.14325. Multiple LLM
  instances proposing and critiquing over rounds improves factuality and reasoning vs
  single models. → Foundation of the Debate Loop (§5.1).
- **Liu et al. (2023). "Dynamic LLM-Agent Network (DyLAN)."** arXiv:2310.02170.
  Dynamic agent-team topology with agent-importance scoring beats fixed teams;
  low-value agents pruned mid-task. → Moderator pruning of converged debaters.
- **Zhuge et al. (2024). "GPTSwarm: Language Agents as Optimizable Graphs."**
  arXiv:2402.16823. Agent swarms as computational graphs with optimizable edges;
  sparse communication competitive with dense. → Sparse debate topology default.
- **Smit et al. (2024). "Should we be going MAD?"** arXiv:2311.17371. Critical
  re-evaluation: debate gains depend heavily on answer heterogeneity; homogeneous
  agents converge to shared errors. → Provider-diversity pinning (§3.2) and the
  degeneracy guard.

## Reflection & self-improvement

- **Shinn et al. (2023). "Reflexion: Language Agents with Verbal Reinforcement
  Learning."** arXiv:2303.11366. Verbal self-feedback stored in episodic memory
  improves later attempts without weight updates. → Cross-run lesson memory (§5.2).
- **Madaan et al. (2023). "Self-Refine."** arXiv:2303.17651. Iterative
  feedback-and-revise with the same model improves outputs ~20% avg across tasks;
  gains plateau after few rounds. → Intra-run revision loop with plateau convergence.
- **Gou et al. (2023). "CRITIC: LLMs Can Self-Correct with Tool-Interactive
  Critiquing."** arXiv:2305.11738. Self-correction is unreliable without external
  tools/verifiers — tool-grounded critique works. → Reviewers get tool access;
  verify loop is tool-grounded, never introspective.
- **Huang et al. (2023). "Large Language Models Cannot Self-Correct Reasoning Yet."**
  arXiv:2310.01798. Negative result: intrinsic self-correction often degrades
  accuracy. → ATHENAEUM never relies on unassisted self-critique; all revision is
  driven by external structured verdicts (Court) or ledger evidence.

## Evolutionary / open-ended loops

- **Romera-Paredes et al. (2024). "FunSearch: Mathematical discoveries from program
  search with LLMs."** Nature 625. LLM-proposes + evaluator-scores + island
  population = new mathematical results. → LLM-propose/code-evaluate split; the
  evolve loop's fitness is computed by the Court, not by the proposer.
- **Novikov et al. (2025). "AlphaEvolve: A coding agent for scientific and
  algorithmic discovery."** DeepMind. Evolutionary archive + strong/fast model mix +
  automated evaluation discovered SOTA algorithms. → Strong-model operators on
  archive elites, fast-model bulk mutation (§5.3 operator/capability mapping).
- **Zhang, Hu, Lu, Lange, Clune (2025). "Darwin Gödel Machine."** arXiv:2505.22954.
  Archive of *all* interesting variants (not just best) enables open-ended
  self-improvement; stepping stones matter. → MAP-Elites archive keeps diverse
  elites; parents sampled uniformly over cells.
- **Mouret & Clune (2015). "Illuminating search spaces by mapping elites."**
  arXiv:1504.04909. MAP-Elites quality-diversity algorithm. → The archive grid over
  (novelty, risk posture, time horizon) — the spec's core novel transfer to arguments.

## Autonomous research systems

- **Shao et al. (2024). "Assisting in Writing Wikipedia-like Articles From Scratch
  with Large Language Models (STORM)."** arXiv:2402.14207. Perspective-guided
  question asking + simulated expert conversations produce better outlines/articles
  than direct generation. → Research loop's perspective→question→sweep design (§5.5).
- **Schmidgall et al. (2025). "Agent Laboratory."** arXiv:2501.04227. Full
  literature→experiment→report pipeline with human checkpoints; cost ~2.5% of prior
  autonomous pipelines. → Science loop stage gates (methods approval before spend).
- **Yamada et al. (2025). "The AI Scientist-v2."** Sakana AI. Agentic tree search
  over experiments; first fully AI-generated workshop-accepted paper; also
  demonstrated reviewer-gaming risks. → Separate experimenter/analyst agents; court
  review with methods checklist.
- **Gottweis et al. (2025). "Towards an AI co-scientist."** Google. Generate-debate-
  evolve with Elo tournaments over hypotheses; validated wet-lab findings. →
  Tournament scaling strategy (§5.7); debate-as-ranking inside evolve.

## Verification, judging, review

- **Verga et al. (2024). "Replacing Judges with Juries (PoLL)."** arXiv:2404.18796.
  Panels of small diverse judges outperform one large judge at 1/7 the cost, with
  less intra-model bias. → All fusion/judging uses small-model panels (§7.6).
- **Zheng et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena."**
  arXiv:2306.05685. Position/verbosity/self-preference biases; order-swap and
  rubric mitigations. → S6 judge separation, order swapping, length-normalized rubrics.
- **Jin et al. (2024). "AgentReview: Exploring Peer Review Dynamics with LLM
  Agents."** arXiv:2406.12708. Simulated review dynamics; reviewer biases dominate
  outcome variance. → Structured verdict schema + Chief Justice cross-examination
  instead of free-form review text.
- **Irving, Christiano, Amodei (2018). "AI Safety via Debate."** arXiv:1805.00899,
  plus Khan et al. (2024) arXiv:2402.06782 showing debate helps weaker judges
  supervise stronger debaters. → Refutation-framed skeptics in the verify loop.

## Argumentation & audience

- **Toulmin (1958). *The Uses of Argument*.** Claim/grounds/warrant/backing/
  qualifier/rebuttal decomposition. → Argument Auditor's parse target (§7.1).
- **Walton, Reed, Macagno (2008). *Argumentation Schemes*.** Scheme-specific
  critical questions. → The auditor's per-scheme question banks.
- **Zheng, Pei, Jurgens (2023). "When 'A Helpful Assistant' Is Not Really Helpful:
  Personas in System Prompts."** arXiv:2311.10054. Persona prompts do not
  systematically improve performance. → §7.4 honesty clause: personas are diversity
  generators, outcome-blind fused, never authority.
- **Wang et al. (2024). "Unleashing the Emergent Cognitive Synergy in LLMs (Solo
  Performance Prompting)."** arXiv:2307.05300. Multi-persona self-collaboration
  helps on knowledge-intensive tasks (in strong models). → Why the panel exists at
  all; combined with the negative result above, why it is judged blind.

## Test-time compute

- **Snell et al. (2024). "Scaling LLM Test-Time Compute Optimally can be More
  Effective than Scaling Model Parameters."** arXiv:2408.03314. Compute-optimal
  test-time strategies beat parameter scaling per FLOP; strategy should depend on
  difficulty. → §5.7 per-node scaling policies and the degradation ladder.
- **Wang et al. (2022). "Self-Consistency Improves Chain of Thought Reasoning."**
  arXiv:2203.11171. Majority voting over sampled reasoning paths. → The
  `self_consistency` strategy for classification-shaped nodes.

## Engineering substrate (repos studied)

- **stanford-oval/storm** — perspective-guided research pipeline structure.
- **assafelovic/gpt-researcher** — planner/executor split, parallel source digestion.
- **SakanaAI/AI-Scientist** — experiment sandbox conventions, reviewer prompts.
- **BerriAI/litellm** — provider normalization patterns for the ModelGateway (we
  reimplement the thin slice we need; no framework dependency).
- **openai/codex**, **google-gemini/gemini-cli**, **anthropics/claude-code** — headless
  JSON output modes used by the CLI Runtime adapters (§4.2).
