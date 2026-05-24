# Solar PV MPPT Simulation in Python

A research-oriented photovoltaic Maximum Power Point Tracking (MPPT) simulation built in Python using `pvlib`, `NumPy`, `SciPy`, `Pandas`, and `Matplotlib`.

This project compares **Perturb & Observe (P&O)** and **Incremental Conductance (IncCond)** under dynamic irradiance conditions using a PV model and an averaged boost converter model.

---

## Project Goal

The goal of this project is to simulate a solar PV system that continuously tracks the maximum power point under changing environmental conditions.

---

## Features

- PV modeling using `pvlib`
- Averaged DC-DC boost converter model
- MPPT implementation using:
  - Perturb & Observe
  - Incremental Conductance
- Dynamic irradiance test scenarios
- Optional temperature variation
- Automatic graph generation
- Performance comparison between algorithms
- Export of results and summary metrics

---

## Algorithms Implemented

### 1. Perturb & Observe (P&O)
A classic MPPT method that perturbs the operating point and observes the power change.

### 2. Incremental Conductance
A more accurate MPPT method based on the condition:

\[
\frac{dP}{dV} = 0
\]

at the maximum power point.

---

## Why This Project Matters

Solar PV systems rarely operate at ideal conditions. Sunlight and temperature keep changing, so the operating point must be adjusted continuously to extract maximum power.

This project demonstrates:
- algorithmic control,
- power electronics modeling,
- simulation-based engineering design,
- engineering data analysis,
- reproducible technical documentation.

---

## Tech Stack

- Python 3
- `pvlib`
- `NumPy`
- `SciPy`
- `Pandas`
- `Matplotlib`
- VSCode

---

## Repository Structure

```text
mppt_project/
│
├── src/
│   ├── pv_model.py
│   ├── boost_converter.py
│   ├── mppt_po.py
│   ├── mppt_inccond.py
│   ├── simulate.py
│   └── plots.py
│
├── results/
│   ├── figures/
│   ├── data/
│   └── summary_table.csv
│
├── docs/
│   └── summary.md
│
├── requirements.txt
└── README.md
