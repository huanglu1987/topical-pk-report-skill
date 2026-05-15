# Minimal Copyable Input

Copy one YAML block below into a local file, then run:

```bash
python3 -m pktool.cli run-report --input your_input.yaml --no-fetch
```

These minimal inputs are for early internal planning. If same-molecule public PK
anchors are not provided, the tool will use model defaults and will mark them as
assumptions, not evidence.

Minimal inputs are not reproducibility inputs. If no half-life or known
formulation PK anchor is provided, the default steady-state window is calculated
from model defaults and may coincidentally be 672 h for daily dosing. That is not
a fixed 28-day rule. For dutasteride 2% 20 mg report reproduction, use the locked
YAML files in `data/reproducible_inputs/`.

The copyable templates default to `n_simulations: 3000` so P95/P5 tail estimates
are less noisy. For quick smoke testing only, you may temporarily reduce it to
`1000`.

## Reproducible Main Analysis

For a new project, minimal YAML is only an onboarding input. Before treating a
run as the main analysis, lock the full analysis package:

- target product facts: dose, frequency, site/area, single or multiple dosing,
  max-use intent, and study purpose.
- primary comparator: one main PK anchor selected by the closest match to
  molecule, route, body site, formulation/use condition, and dosing scenario.
- model assumptions: absorption fraction range, skin absorption rate, depot
  half-life range, lag range, fast absorption setting, variability preset,
  simulation duration, `n_simulations`, and `random_seed`.
- evidence state: manually confirmed public PK evidence, fetch/no-fetch choice,
  `pktool` version, and run-specific input snapshot.

Use single-dose anchors for single-dose targets when available. Use repeated-dose
or max-use anchors for repeated-dose, steady-state, or max-use targets. Less
matched anchors should be background evidence or named sensitivity scenarios,
not silent replacements for the main comparator.

Fast absorption should stay on `auto` unless there is explicit evidence or the
run is intentionally named as a conservative sensitivity analysis.

## Single Dose

```yaml
compound:
  compound_name: "dutasteride"
  # Optional but strongly recommended when available:
  # half_life_h: 840
  # volume_l: 400

product:
  formulation: "solution"
  concentration_percent_w_w: 2.0
  dose_mg_per_application: 20
  applications_per_day: 1

study_design:
  dosing_scenario: "single"
  purpose: "exploratory"
  sampling_purposes: ["exploratory"]
  n_simulations: 3000
  random_seed: 20260515

evidence:
  pubchem: false
  fda: false
  cde: false

report:
  format: "md,xlsx"
```

## Multiple Dose

Do not add `duration_h`, `dosing_duration_h`, or
`product.treatment_duration_h` unless you intentionally want to override the
default steady-state window.

```yaml
compound:
  compound_name: "dutasteride"
  # Optional but strongly recommended when available:
  # half_life_h: 840
  # volume_l: 400

product:
  formulation: "solution"
  concentration_percent_w_w: 2.0
  dose_mg_per_application: 20
  applications_per_day: 1

study_design:
  dosing_scenario: "multiple"
  dosing_frequency: "daily_qd"   # daily_qd, weekly_qw, weekly_biw
  dosing_frequency_scenarios:
    - name: "daily_qd"
      label: "每日一次"
      dosing_interval_h: 24
    - name: "weekly_qw"
      label: "每周一次"
      dosing_interval_h: 168
    - name: "weekly_biw"
      label: "每周两次"
      dosing_interval_h: 84
  purpose: "exploratory"
  sampling_purposes: ["exploratory"]
  n_simulations: 3000
  random_seed: 20260515

evidence:
  pubchem: false
  fda: false
  cde: false

report:
  format: "md,xlsx"
```

## Notes

- To use amount applied instead of active dose, replace `dose_mg_per_application`
  with `daily_amount_g`.
- For multiple-dose runs, `dosing_frequency` is required unless
  `product.dosing_interval_h` is provided.
- For reproducible dutasteride reference reports, use the locked files in
  `data/reproducible_inputs/` instead of these minimal templates.
