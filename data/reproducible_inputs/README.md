# Reproducible Dutasteride Inputs

These YAML files are locked inputs for reproducing the dutasteride 2% topical
solution 20 mg reports.

Run directly from the repository root:

```bash
python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_single_locked.yaml --no-fetch
python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_multiple_daily_qd_steady_state_locked.yaml --no-fetch
python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_multiple_weekly_qw_steady_state_locked.yaml --no-fetch
```

Do not edit these files if the goal is report reproduction. Copy to a new file
before changing assumptions.
