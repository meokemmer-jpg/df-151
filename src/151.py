from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class UnitRecord:
    monthly_rent: float
    occupied: bool = True


def calculate_real_estate_income_metrics(units: Iterable[UnitRecord]) -> dict[str, float]:
    """
    Compute core monthly real-estate income metrics.

    Metrics:
    - rental_income: sum of rent for occupied units
    - vacancy_rate: vacant units / total units
    - noi: net operating income, equal to rental income here because
      no operating expenses are provided in this mission core

    Auto rent adjustment is intentionally not implemented.
    """
    unit_list = list(units)
    if not unit_list:
        raise ValueError("at least one unit is required")

    for unit in unit_list:
        if unit.monthly_rent < 0:
            raise ValueError("monthly_rent cannot be negative")

    total_units = len(unit_list)
    occupied_units = sum(1 for unit in unit_list if unit.occupied)
    rental_income = sum(unit.monthly_rent for unit in unit_list if unit.occupied)
    vacancy_rate = (total_units - occupied_units) / total_units
    noi = rental_income

    return {
        "rental_income": round(rental_income, 2),
        "vacancy_rate": round(vacancy_rate, 4),
        "noi": round(noi, 2),
    }


def build_report(units: Iterable[UnitRecord], as_of: Optional[date] = None) -> dict[str, object]:
    report_date = as_of or date.today()
    metrics = calculate_real_estate_income_metrics(units)
    return {
        "mission": "DF-151 KPM-Real-Estate-Income",
        "date": report_date.isoformat(),
        "metrics": metrics,
        "auto_rent_adjustment": False,
    }


def write_report(
    units: Iterable[UnitRecord],
    report_dir: str | Path = "reports",
    as_of: Optional[date] = None,
) -> Path:
    report = build_report(units, as_of=as_of)
    target_dir = Path(report_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"df-151-{report['date']}.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path
# [CRUX-MK]
