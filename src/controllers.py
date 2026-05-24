
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def _clip_duty(duty: float, duty_min: float, duty_max: float) -> float:
    return float(np.clip(duty, duty_min, duty_max))


@dataclass
class ControllerState:
    duty_command: float
    duty_min: float
    duty_max: float


class PerturbObserve:
    """
    Classic P&O MPPT.
    For a boost converter: lower duty -> higher PV voltage, higher duty -> lower PV voltage.
    """

    def __init__(
        self,
        duty_init: float = 0.50,
        step_size: float = 0.004,
        duty_min: float = 0.05,
        duty_max: float = 0.90,
    ):
        self.step_size = step_size
        self.duty_min = duty_min
        self.duty_max = duty_max
        self.duty = _clip_duty(duty_init, duty_min, duty_max)

        self.prev_power: Optional[float] = None
        self.direction = 1  # +1 means increase duty, -1 means decrease duty

    def reset(self, duty_init: float = 0.50) -> None:
        self.duty = _clip_duty(duty_init, self.duty_min, self.duty_max)
        self.prev_power = None
        self.direction = 1

    def update(self, voltage: float, current: float) -> float:
        power = voltage * current

        if self.prev_power is None:
            self.prev_power = power
            return self.duty

        if power < self.prev_power:
            self.direction *= -1

        self.duty = _clip_duty(
            self.duty + self.direction * self.step_size,
            self.duty_min,
            self.duty_max,
        )
        self.prev_power = power
        return self.duty


class IncrementalConductance:
    """
    Incremental Conductance MPPT.

    For a boost converter:
      - need higher PV voltage  => decrease duty
      - need lower PV voltage   => increase duty
    """

    def __init__(
        self,
        duty_init: float = 0.50,
        step_size: float = 0.003,
        duty_min: float = 0.05,
        duty_max: float = 0.90,
        tolerance: float = 1e-4,
    ):
        self.step_size = step_size
        self.duty_min = duty_min
        self.duty_max = duty_max
        self.tolerance = tolerance
        self.duty = _clip_duty(duty_init, duty_min, duty_max)

        self.prev_voltage: Optional[float] = None
        self.prev_current: Optional[float] = None

    def reset(self, duty_init: float = 0.50) -> None:
        self.duty = _clip_duty(duty_init, self.duty_min, self.duty_max)
        self.prev_voltage = None
        self.prev_current = None

    def update(self, voltage: float, current: float) -> float:
        if self.prev_voltage is None or self.prev_current is None:
            self.prev_voltage = voltage
            self.prev_current = current
            return self.duty

        dV = voltage - self.prev_voltage
        dI = current - self.prev_current

        if abs(dV) < 1e-9:
            # At constant voltage, determine whether we are left or right of MPP.
            if dI > 0:
                # Left of MPP -> increase PV voltage -> decrease duty
                self.duty -= self.step_size
            elif dI < 0:
                # Right of MPP -> decrease PV voltage -> increase duty
                self.duty += self.step_size
        else:
            incremental_cond = dI / dV
            instantaneous_cond = -current / max(voltage, 1e-9)
            error = incremental_cond - instantaneous_cond

            if abs(error) <= self.tolerance:
                # At MPP: hold duty
                pass
            elif error > 0:
                # Left of MPP -> increase PV voltage -> decrease duty
                self.duty -= self.step_size
            else:
                # Right of MPP -> decrease PV voltage -> increase duty
                self.duty += self.step_size

        self.duty = _clip_duty(self.duty, self.duty_min, self.duty_max)
        self.prev_voltage = voltage
        self.prev_current = current
        return self.duty
