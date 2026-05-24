# PV MPPT Simulation in Python

This project simulates a photovoltaic panel, an averaged boost converter, and two MPPT controllers:
Perturb & Observe and Incremental Conductance.

## What it generates
- I-V curve at standard test conditions
- P-V curve at standard test conditions
- MPPT tracking under constant, step, and ramp irradiance
- CSV result files
- PNG figures for GitHub / report / LinkedIn

## Folder structure

```text
mppt_project/
├── src/
│   ├── pv_model.py
│   ├── controllers.py
│   └── simulate.py
├── results/
│   ├── figures/
│   └── data/
├── docs/
├── requirements.txt
└── README.md
```

## How to run

1. Create a virtual environment:
```bash
python -m venv .venv
```

2. Activate it:

Windows:
```bash
.venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the simulation:
```bash
python src/simulate.py
```

## Outputs
- Figures: `results/figures/`
- Raw CSV data: `results/data/`
- Summary table: `results/summary_table.csv`
- Markdown summary: `docs/summary.md`
