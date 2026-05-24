
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional

import numpy as np
from scipy.optimize import brentq

from pvlib import pvsystem, temperature


def _as_float(value) -> float:
    """Convert pvlib / numpy scalar outputs to a plain Python float."""
    return float(np.asarray(value).squeeze())


@dataclass
class OperatingPoint:
    irradiance: float
    temp_air: float
    temp_cell: float
    duty: float
    voltage: float
    current: float
    power: float
    v_out: float
    i_out: float
    p_mp_ideal: float
    v_mp_ideal: float
    i_mp_ideal: float
    v_oc: float
    i_sc: float
    rin: float


class PVModel:
    """
    PV module model built on pvlib's CEC module database and De Soto single-diode model.
    """

    def __init__(self, module_keyword: Optional[str] = None):
        self.module_db = pvsystem.retrieve_sam("CECMod")
        self.module_name = self._select_module(module_keyword)
        self.module = self.module_db[self.module_name]

        required = ["alpha_sc", "a_ref", "I_L_ref", "I_o_ref", "R_sh_ref", "R_s"]
        missing = [k for k in required if k not in self.module.index]
        if missing:
            raise KeyError(f"Missing expected module keys: {missing}")

        print(f"\nSelected PV module: {self.module_name}")
        print("Key module parameters:")
        for key in required:
            print(f"  {key:10s} = {self.module[key]}")

    def _select_module(self, module_keyword: Optional[str]) -> str:
        cols = list(self.module_db.columns)
        if module_keyword:
            matches = [c for c in cols if module_keyword.lower() in c.lower()]
            if matches:
                return matches[0]

        preferred_keywords = [
            "Canadian",
            "Trina",
            "Jinko",
            "SunPower",
            "LG",
            "Panasonic",
            "REC",
        ]
        for kw in preferred_keywords:
            matches = [c for c in cols if kw.lower() in c.lower()]
            if matches:
                return matches[0]

        return cols[0]

    def cell_temperature(
        self,
        irradiance_wm2: float,
        temp_air_c: float,
        wind_speed_mps: float = 1.0,
    ) -> float:
        """
        Cell temperature model. Faiman is simple, practical, and built into pvlib.
        """
        t_cell = temperature.faiman(
            irradiance_wm2,
            temp_air_c,
            wind_speed=wind_speed_mps,
        )
        return _as_float(t_cell)

    def diode_parameters(
        self,
        effective_irradiance_wm2: float,
        temp_cell_c: float,
    ) -> Tuple[float, float, float, float, float]:
        """
        De Soto single-diode parameters.
        """
        return pvsystem.calcparams_desoto(
            effective_irradiance_wm2,
            temp_cell_c,
            self.module["alpha_sc"],
            self.module["a_ref"],
            self.module["I_L_ref"],
            self.module["I_o_ref"],
            self.module["R_sh_ref"],
            self.module["R_s"],
        )

    def ideal_mpp(
        self,
        irradiance_wm2: float,
        temp_cell_c: float,
    ) -> Dict[str, float]:
        """
        Returns the ideal MPP at the given weather conditions.
        """
        IL, I0, Rs, Rsh, nNsVth = self.diode_parameters(irradiance_wm2, temp_cell_c)
        result = pvsystem.singlediode(IL, I0, Rs, Rsh, nNsVth)

        return {
            "i_sc": _as_float(result["i_sc"]),
            "v_oc": _as_float(result["v_oc"]),
            "i_mp": _as_float(result["i_mp"]),
            "v_mp": _as_float(result["v_mp"]),
            "p_mp": _as_float(result["p_mp"]),
        }

    def iv_curve(
        self,
        irradiance_wm2: float,
        temp_cell_c: float,
        num_points: int = 250,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, float]]:
        """
        Returns voltage, current, power, and the ideal MPP dictionary.
        """
        IL, I0, Rs, Rsh, nNsVth = self.diode_parameters(irradiance_wm2, temp_cell_c)
        mpp = self.ideal_mpp(irradiance_wm2, temp_cell_c)
        voc = max(mpp["v_oc"], 1e-6)
        voltage = np.linspace(0.0, voc, num_points)
        current = pvsystem.i_from_v(voltage, IL, I0, Rs, Rsh, nNsVth)
        current = np.asarray(current, dtype=float)
        power = voltage * current
        return voltage, current, power, mpp

    @staticmethod
    def equivalent_input_resistance(load_resistance_ohm: float, duty: float) -> float:
        """
        Ideal boost converter input resistance: Rin = Rload * (1 - D)^2
        """
        duty = float(np.clip(duty, 0.02, 0.98))
        return load_resistance_ohm * (1.0 - duty) ** 2

    def operating_point_for_duty(
        self,
        irradiance_wm2: float,
        temp_cell_c: float,
        duty: float,
        load_resistance_ohm: float,
    ) -> OperatingPoint:
        """
        Solve PV operating point by intersecting the PV I-V curve with the boost-converter load line.
        """
        IL, I0, Rs, Rsh, nNsVth = self.diode_parameters(irradiance_wm2, temp_cell_c)
        ideal = self.ideal_mpp(irradiance_wm2, temp_cell_c)
        rin = self.equivalent_input_resistance(load_resistance_ohm, duty)

        def f(v):
            i_pv = _as_float(pvsystem.i_from_v(v, IL, I0, Rs, Rsh, nNsVth))
            return i_pv - (v / rin)

        v_max = max(ideal["v_oc"] * 0.999, 1e-6)
        try:
            v_pv = brentq(f, 1e-6, v_max, maxiter=200)
        except ValueError:
            # Fallback if the bracket ever fails for a weird parameter set.
            grid = np.linspace(0.0, v_max, 400)
            vals = np.array([abs(f(v)) for v in grid])
            v_pv = float(grid[int(np.argmin(vals))])

        i_pv = _as_float(pvsystem.i_from_v(v_pv, IL, I0, Rs, Rsh, nNsVth))
        p_pv = v_pv * i_pv

        # Ideal boost converter voltage relation
        duty = float(np.clip(duty, 0.02, 0.98))
        v_out = v_pv / max(1.0 - duty, 1e-6)
        i_out = v_out / load_resistance_ohm

        return OperatingPoint(
            irradiance=irradiance_wm2,
            temp_air=np.nan,
            temp_cell=temp_cell_c,
            duty=duty,
            voltage=v_pv,
            current=i_pv,
            power=p_pv,
            v_out=v_out,
            i_out=i_out,
            p_mp_ideal=ideal["p_mp"],
            v_mp_ideal=ideal["v_mp"],
            i_mp_ideal=ideal["i_mp"],
            v_oc=ideal["v_oc"],
            i_sc=ideal["i_sc"],
            rin=rin,
        )
