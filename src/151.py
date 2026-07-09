from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Optional


@dataclass(frozen=True)
class UnitRecord:
    monthly_rent: float
    occupied: bool = True
    operating_expense: float = 0.0
    unit_id: str = ""


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "occupied"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "vacant"}:
        return False
    raise ValueError(f"cannot parse occupied value: {value!r}")


def _parse_money(value: object, field_name: str) -> float:
    try:
        amount = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(amount):
        raise ValueError(f"{field_name} must be finite")
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return amount


def unit_from_mapping(row: Mapping[str, object]) -> UnitRecord:
    if "monthly_rent" not in row or row["monthly_rent"] in (None, ""):
        raise ValueError("monthly_rent is required")
    return UnitRecord(
        monthly_rent=_parse_money(row["monthly_rent"], "monthly_rent"),
        occupied=_parse_bool(row.get("occupied", True)),
        operating_expense=_parse_money(row.get("operating_expense", 0.0), "operating_expense"),
        unit_id=str(row.get("unit_id", "")).strip(),
    )


def load_units_from_csv(path: str | Path) -> list[UnitRecord]:
    source = Path(path)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV header is required")
        units = [unit_from_mapping(row) for row in reader]
    if not units:
        raise ValueError("at least one unit is required")
    return units


def calculate_real_estate_income_metrics(units: Iterable[UnitRecord]) -> dict[str, float]:
    unit_list = list(units)
    if not unit_list:
        raise ValueError("at least one unit is required")

    for unit in unit_list:
        _parse_money(unit.monthly_rent, "monthly_rent")
        _parse_money(unit.operating_expense, "operating_expense")

    total_units = len(unit_list)
    occupied_units = sum(1 for unit in unit_list if unit.occupied)
    scheduled_rent = sum(unit.monthly_rent for unit in unit_list)
    rental_income = sum(unit.monthly_rent for unit in unit_list if unit.occupied)
    operating_expenses = sum(unit.operating_expense for unit in unit_list)
    vacancy_rate = (total_units - occupied_units) / total_units
    collection_loss = scheduled_rent - rental_income
    noi = rental_income - operating_expenses
    average_rent_per_occupied_unit = rental_income / occupied_units if occupied_units else 0.0

    return {
        "total_units": float(total_units),
        "occupied_units": float(occupied_units),
        "scheduled_rent": round(scheduled_rent, 2),
        "rental_income": round(rental_income, 2),
        "operating_expenses": round(operating_expenses, 2),
        "vacancy_rate": round(vacancy_rate, 4),
        "collection_loss": round(collection_loss, 2),
        "average_rent_per_occupied_unit": round(average_rent_per_occupied_unit, 2),
        "noi": round(noi, 2),
    }


def build_report(units: Iterable[UnitRecord], as_of: Optional[date] = None) -> dict[str, object]:
    report_date = as_of or date.today()
    metrics = calculate_real_estate_income_metrics(units)
    return {
        "mission": "df-151",
        "date": report_date.isoformat(),
        "metrics": metrics,
        "auto_rent_adjustment": False,
    }


def build_report_from_csv(path: str | Path, as_of: Optional[date] = None) -> dict[str, object]:
    return build_report(load_units_from_csv(path), as_of=as_of)


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
