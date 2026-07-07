# Thinker Panel Presets

Use these as critique-diversity presets. Do not ask for hidden chain-of-thought. Ask for conclusions, assumptions, objections, tests, evidence needed, and concise rationale summaries.

## Presets

| Preset | Lenses | Use |
|---|---|---|
| foundations | `einstein,feynman,popper,turing` | assumptions, mechanisms, falsifiable tests, formal interfaces |
| risk | `kahneman,taleb,popper,franklin` | calibration, tail risk, disconfirmation, evidence quality |
| governance | `ostrom,kahneman,taleb,popper` | incentives, institutions, bias, downside |
| invention | `lovelace,turing,feynman,darwin` | procedures, computability, mechanisms, adaptation |
| science | `franklin,popper,feynman,darwin` | measurement, falsification, mechanism, selection effects |
| executive | `kahneman,ostrom,taleb,einstein` | decision quality, stakeholder fit, risk, simplifying model |
| redteam | `popper,taleb,kahneman,franklin,turing` | adversarial tests, downside, calibration, evidence, interfaces |
| iq-high | `einstein,feynman,kahneman,popper` | balanced high-effort review |
| iq-vhigh | `einstein,feynman,kahneman,popper,taleb,franklin` | broader high-stakes review |
| iq-max | `einstein,feynman,kahneman,popper,taleb,ostrom,turing,franklin` | deep audit |
| iq-ultra | all available lenses | exhaustive adversarial review |

## Prompt Shape

```text
Apply the <preset> public analysis panel.
For each lens, give:
- conclusion
- key assumption
- strongest objection
- falsifier or test
- evidence needed
- confidence
- concise rationale summary

Do not include hidden chain-of-thought or private reasoning traces.
Fuse findings by evidence quality and testability, not by persona prestige.
```

## CLI Examples

```bash
python3 -m athenaeum thinkers presets
python3 -m athenaeum --runtime api --effort iq-high --panel foundations "Question"
python3 -m athenaeum --runtime api --effort iq-vhigh --panel risk "Question"
python3 -m athenaeum --runtime api --effort iq-ultra --panel iq-ultra "Question"
python3 -m athenaeum thinkers panel einstein,kahneman,taleb
python3 -m athenaeum thinkers panel risk
```
