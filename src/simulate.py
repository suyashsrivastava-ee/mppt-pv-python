
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pv_model import PVModel
from controllers import PerturbObserve, IncrementalConductance


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
FIG_DIR = RESULTS_DIR / "figures"
DATA_DIR = RESULTS_DIR / "data"
DOCS_DIR = PROJECT_ROOT / "docs"

LOAD_RESISTANCE_OHM = 18.0
DUTY_INIT = 0.50
DUTY_MIN = 0.05
DUTY_MAX = 0.90

PO_STEP = 0.004
IC_STEP = 0.005

DT = 0.10  # seconds per simulation step
N_STEPS = 500  # 50 s total


class BoostConverter:
    """
    Simple averaged boost-converter dynamics for MPPT-level simulation.
    """
    def __init__(
        self,
        load_resistance_ohm: float,
        duty_init: float = 0.50,
        alpha: float = 0.25,
        duty_min: float = 0.05,
        duty_max: float = 0.90,
    ):
        self.load_resistance_ohm = load_resistance_ohm
        self.duty_actual = duty_init
        self.alpha = alpha
        self.duty_min = duty_min
        self.duty_max = duty_max

    def reset(self, duty_init: float = 0.50) -> None:
        self.duty_actual = float(np.clip(duty_init, self.duty_min, self.duty_max))

    def update(self, duty_command: float) -> float:
        duty_command = float(np.clip(duty_command, self.duty_min, self.duty_max))
        self.duty_actual = self.duty_actual + self.alpha * (duty_command - self.duty_actual)
        self.duty_actual = float(np.clip(self.duty_actual, self.duty_min, self.duty_max))
        return self.duty_actual

    def input_resistance(self, duty: float) -> float:
        duty = float(np.clip(duty, self.duty_min, self.duty_max))
        return self.load_resistance_ohm * (1.0 - duty) ** 2


def ensure_dirs() -> None:
    for d in (RESULTS_DIR, FIG_DIR, DATA_DIR, DOCS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def build_scenario(name: str, n_steps: int = N_STEPS, dt: float = DT) -> Dict[str, np.ndarray]:
    t = np.arange(n_steps) * dt

    if name == "constant":
        irradiance = np.full(n_steps, 1000.0)
        temp_air = np.full(n_steps, 25.0)

    elif name == "step":
        irradiance = np.piecewise(
            t,
            [
                t < 12,
                (t >= 12) & (t < 24),
                (t >= 24) & (t < 36),
                t >= 36,
            ],
            [1000.0, 650.0, 900.0, 500.0],
        )
        temp_air = np.piecewise(
            t,
            [t < 20, (t >= 20) & (t < 36), t >= 36],
            [25.0, 30.0, 34.0],
        )

    elif name == "ramp":
        irradiance = 700.0 + 260.0 * np.sin(2 * np.pi * t / (n_steps * dt)) + 60.0 * np.sin(2 * np.pi * t / 7.0)
        irradiance = np.clip(irradiance, 300.0, 1000.0)
        temp_air = 28.0 + 4.0 * np.sin(2 * np.pi * t / (n_steps * dt) + 0.8)

    else:
        raise ValueError(f"Unknown scenario: {name}")

    return {
        "time_s": t,
        "irradiance": irradiance,
        "temp_air": temp_air,
    }


def run_simulation(
    pv: PVModel,
    algorithm_name: str,
    controller,
    scenario: Dict[str, np.ndarray],
    load_resistance_ohm: float = LOAD_RESISTANCE_OHM,
    dt: float = DT,
) -> pd.DataFrame:
    converter = BoostConverter(
        load_resistance_ohm=load_resistance_ohm,
        duty_init=DUTY_INIT,
        alpha=0.25,
        duty_min=DUTY_MIN,
        duty_max=DUTY_MAX,
    )
    converter.reset(DUTY_INIT)
    controller.reset(DUTY_INIT)

    rows = []
    last_voltage = None
    last_current = None

    time_s = scenario["time_s"]
    irradiance = scenario["irradiance"]
    temp_air = scenario["temp_air"]

    for k in range(len(time_s)):
        g = float(irradiance[k])
        ta = float(temp_air[k])
        tc = pv.cell_temperature(g, ta, wind_speed_mps=1.0)

        if k == 0:
            duty_command = DUTY_INIT
        else:
            duty_command = controller.update(last_voltage, last_current)

        duty_actual = converter.update(duty_command)
        op = pv.operating_point_for_duty(
            irradiance_wm2=g,
            temp_cell_c=tc,
            duty=duty_actual,
            load_resistance_ohm=load_resistance_ohm,
        )

        efficiency = 100.0 * op.power / max(op.p_mp_ideal, 1e-9)
        power_error = op.p_mp_ideal - op.power

        rows.append(
            {
                "time_s": time_s[k],
                "irradiance_wm2": g,
                "temp_air_c": ta,
                "temp_cell_c": tc,
                "algorithm": algorithm_name,
                "duty_command": duty_command,
                "duty_actual": duty_actual,
                "pv_voltage_v": op.voltage,
                "pv_current_a": op.current,
                "pv_power_w": op.power,
                "pv_rin_ohm": op.rin,
                "vout_v": op.v_out,
                "iout_a": op.i_out,
                "p_mp_ideal_w": op.p_mp_ideal,
                "v_mp_ideal_v": op.v_mp_ideal,
                "i_mp_ideal_a": op.i_mp_ideal,
                "tracking_efficiency_pct": efficiency,
                "power_error_w": power_error,
            }
        )

        last_voltage = op.voltage
        last_current = op.current

    df = pd.DataFrame(rows)
    df["algorithm"] = algorithm_name
    return df


def plot_stc_curves(pv: PVModel) -> None:
    tc = pv.cell_temperature(1000.0, 25.0)
    v, i, p, mpp = pv.iv_curve(1000.0, tc, num_points=300)

    fig = plt.figure(figsize=(8, 5))
    plt.plot(v, i)
    plt.xlabel("Voltage (V)")
    plt.ylabel("Current (A)")
    plt.title("I-V Curve at Standard Test Conditions")
    plt.grid(True, alpha=0.3)
    fig.savefig(FIG_DIR / "iv_curve_stc.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig = plt.figure(figsize=(8, 5))
    plt.plot(v, p)
    plt.xlabel("Voltage (V)")
    plt.ylabel("Power (W)")
    plt.title("P-V Curve at Standard Test Conditions")
    plt.grid(True, alpha=0.3)
    fig.savefig(FIG_DIR / "pv_curve_stc.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig = plt.figure(figsize=(8, 5))
    plt.plot([mpp["v_mp"]], [mpp["p_mp"]], marker="o", linestyle="None")
    plt.xlabel("Voltage (V)")
    plt.ylabel("Power (W)")
    plt.title("Maximum Power Point at Standard Test Conditions")
    plt.grid(True, alpha=0.3)
    fig.savefig(FIG_DIR / "mpp_stc.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_scenario_comparison(scenario_name: str, df_po: pd.DataFrame, df_ic: pd.DataFrame, scenario: Dict[str, np.ndarray]) -> None:
    t = scenario["time_s"]

    # Irradiance profile
    fig = plt.figure(figsize=(9, 5))
    plt.plot(t, scenario["irradiance"])
    plt.xlabel("Time (s)")
    plt.ylabel("Irradiance (W/m²)")
    plt.title(f"{scenario_name.title()} Scenario: Irradiance Profile")
    plt.grid(True, alpha=0.3)
    fig.savefig(FIG_DIR / f"{scenario_name}_irradiance.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # PV power
    fig = plt.figure(figsize=(9, 5))
    plt.plot(df_po["time_s"], df_po["pv_power_w"], label="P&O")
    plt.plot(df_ic["time_s"], df_ic["pv_power_w"], label="Incremental Conductance")
    plt.plot(df_po["time_s"], df_po["p_mp_ideal_w"], label="Ideal MPP", linestyle="--")
    plt.xlabel("Time (s)")
    plt.ylabel("Power (W)")
    plt.title(f"{scenario_name.title()} Scenario: PV Power Tracking")
    plt.grid(True, alpha=0.3)
    plt.legend()
    fig.savefig(FIG_DIR / f"{scenario_name}_power_tracking.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # Duty cycle
    fig = plt.figure(figsize=(9, 5))
    plt.plot(df_po["time_s"], df_po["duty_actual"], label="P&O")
    plt.plot(df_ic["time_s"], df_ic["duty_actual"], label="Incremental Conductance")
    plt.xlabel("Time (s)")
    plt.ylabel("Duty Cycle")
    plt.title(f"{scenario_name.title()} Scenario: Duty Cycle")
    plt.grid(True, alpha=0.3)
    plt.legend()
    fig.savefig(FIG_DIR / f"{scenario_name}_duty_cycle.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # Efficiency
    fig = plt.figure(figsize=(9, 5))
    plt.plot(df_po["time_s"], df_po["tracking_efficiency_pct"], label="P&O")
    plt.plot(df_ic["time_s"], df_ic["tracking_efficiency_pct"], label="Incremental Conductance")
    plt.xlabel("Time (s)")
    plt.ylabel("Tracking Efficiency (%)")
    plt.title(f"{scenario_name.title()} Scenario: Tracking Efficiency")
    plt.grid(True, alpha=0.3)
    plt.legend()
    fig.savefig(FIG_DIR / f"{scenario_name}_efficiency.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # PV voltage
    fig = plt.figure(figsize=(9, 5))
    plt.plot(df_po["time_s"], df_po["pv_voltage_v"], label="P&O")
    plt.plot(df_ic["time_s"], df_ic["pv_voltage_v"], label="Incremental Conductance")
    plt.plot(df_po["time_s"], df_po["v_mp_ideal"], label="Ideal Vmp", linestyle="--")
    plt.xlabel("Time (s)")
    plt.ylabel("PV Voltage (V)")
    plt.title(f"{scenario_name.title()} Scenario: PV Voltage")
    plt.grid(True, alpha=0.3)
    plt.legend()
    fig.savefig(FIG_DIR / f"{scenario_name}_pv_voltage.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def summarize(df: pd.DataFrame) -> Dict[str, float]:
    return {
        "avg_efficiency_pct": float(df["tracking_efficiency_pct"].mean()),
        "min_efficiency_pct": float(df["tracking_efficiency_pct"].min()),
        "final_efficiency_pct": float(df["tracking_efficiency_pct"].iloc[-1]),
        "avg_power_w": float(df["pv_power_w"].mean()),
        "avg_ideal_power_w": float(df["p_mp_ideal_w"].mean()),
        "mean_abs_power_error_w": float(df["power_error_w"].abs().mean()),
        "mean_duty": float(df["duty_actual"].mean()),
        "std_duty": float(df["duty_actual"].std(ddof=0)),
    }


def write_summary(summary_rows: list[dict]) -> None:
    df = pd.DataFrame(summary_rows)
    df.to_csv(RESULTS_DIR / "summary_table.csv", index=False)

    # Write a simple markdown-friendly text summary without extra dependencies.
    lines = []
    lines.append("# MPPT Simulation Summary\n")
    lines.append("## Comparison metrics\n")
    lines.append(df.to_string(index=False))
    (DOCS_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def save_raw_results(df: pd.DataFrame, scenario_name: str, algorithm_name: str) -> None:
    filename = f"{scenario_name}_{algorithm_name.lower().replace(' ', '_')}.csv"
    df.to_csv(DATA_DIR / filename, index=False)


def main() -> None:
    ensure_dirs()

    pv = PVModel(module_keyword=None)

    # Static PV curves at STC
    plot_stc_curves(pv)

    scenarios = ["constant", "step", "ramp"]
    summary_rows = []

    for scenario_name in scenarios:
        scenario = build_scenario(scenario_name)

        po_controller = PerturbObserve(
            duty_init=DUTY_INIT,
            step_size=PO_STEP,
            duty_min=DUTY_MIN,
            duty_max=DUTY_MAX,
        )
        ic_controller = IncrementalConductance(
            duty_init=DUTY_INIT,
            step_size=IC_STEP,
            duty_min=DUTY_MIN,
            duty_max=DUTY_MAX,
        )

        df_po = run_simulation(pv, "P&O", po_controller, scenario)
        df_ic = run_simulation(pv, "Incremental Conductance", ic_controller, scenario)

        save_raw_results(df_po, scenario_name, "po")
        save_raw_results(df_ic, scenario_name, "incremental_conductance")

        plot_scenario_comparison(scenario_name, df_po, df_ic, scenario)

        po_summary = summarize(df_po)
        ic_summary = summarize(df_ic)

        summary_rows.append(
            {
                "scenario": scenario_name,
                "algorithm": "P&O",
                **po_summary,
            }
        )
        summary_rows.append(
            {
                "scenario": scenario_name,
                "algorithm": "Incremental Conductance",
                **ic_summary,
            }
        )

    write_summary(summary_rows)

    print("\nSimulation complete.")
    print(f"Figures saved to: {FIG_DIR}")
    print(f"CSV data saved to: {DATA_DIR}")
    print(f"Summary saved to: {RESULTS_DIR / 'summary_table.csv'}")
    print(f"Markdown summary saved to: {DOCS_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
