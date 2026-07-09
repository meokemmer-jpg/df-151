import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import csv
import importlib
import json
from datetime import date

m151 = importlib.import_module("151")


def _write_rent_roll(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["unit_id", "monthly_rent", "occupied", "operating_expense"])
        writer.writeheader()
        writer.writerows(rows)


def _independent_totals(rows):
    occupied_rows = [row for row in rows if row["occupied"] == "occupied"]
    total_units = len(rows)
    occupied_units = len(occupied_rows)
    scheduled_rent = sum(float(row["monthly_rent"]) for row in rows)
    rental_income = sum(float(row["monthly_rent"]) for row in occupied_rows)
    expenses = sum(float(row["operating_expense"]) for row in rows)
    return {
        "total_units": float(total_units),
        "occupied_units": float(occupied_units),
        "scheduled_rent": scheduled_rent,
        "rental_income": rental_income,
        "operating_expenses": expenses,
        "vacancy_rate": (total_units - occupied_units) / total_units,
        "noi": rental_income - expenses,
    }


def test_df151_metrics_are_computed_from_real_csv_and_discriminate_counter_input(tmp_path):
    productive_rows = [
        {"unit_id": "A", "monthly_rent": "1400", "occupied": "occupied", "operating_expense": "250"},
        {"unit_id": "B", "monthly_rent": "1600", "occupied": "occupied", "operating_expense": "300"},
        {"unit_id": "C", "monthly_rent": "1200", "occupied": "vacant", "operating_expense": "200"},
    ]
    adversarial_rows = [dict(row, occupied="vacant") for row in productive_rows]

    productive_csv = tmp_path / "productive-rent-roll.csv"
    adversarial_csv = tmp_path / "adversarial-rent-roll.csv"
    _write_rent_roll(productive_csv, productive_rows)
    _write_rent_roll(adversarial_csv, adversarial_rows)

    productive_report = m151.build_report_from_csv(productive_csv, as_of=date(2026, 7, 9))
    adversarial_report = m151.build_report_from_csv(adversarial_csv, as_of=date(2026, 7, 9))

    productive_expected = _independent_totals(productive_rows)
    adversarial_expected = _independent_totals(adversarial_rows)

    assert productive_report["mission"] == "df-151"
    assert productive_report["metrics"]["rental_income"] == productive_expected["rental_income"]
    assert productive_report["metrics"]["noi"] == productive_expected["noi"]
    assert productive_report["metrics"]["vacancy_rate"] == productive_expected["vacancy_rate"]

    assert adversarial_report["metrics"]["rental_income"] == adversarial_expected["rental_income"]
    assert adversarial_report["metrics"]["noi"] == adversarial_expected["noi"]
    assert adversarial_report["metrics"]["vacancy_rate"] == adversarial_expected["vacancy_rate"]

    assert productive_report["metrics"] != adversarial_report["metrics"]
    assert productive_report["metrics"]["rental_income"] > adversarial_report["metrics"]["rental_income"]
    assert productive_report["metrics"]["noi"] > adversarial_report["metrics"]["noi"]
    assert productive_report["metrics"]["vacancy_rate"] < adversarial_report["metrics"]["vacancy_rate"]


def test_df151_writes_real_json_report_file(tmp_path):
    rows = [
        {"unit_id": "A", "monthly_rent": "900", "occupied": "occupied", "operating_expense": "100"},
        {"unit_id": "B", "monthly_rent": "1100", "occupied": "vacant", "operating_expense": "150"},
    ]
    csv_path = tmp_path / "rent-roll.csv"
    _write_rent_roll(csv_path, rows)

    units = m151.load_units_from_csv(csv_path)
    output_path = m151.write_report(units, report_dir=tmp_path / "reports", as_of=date(2026, 7, 9))

    assert output_path.exists()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted == m151.build_report(units, as_of=date(2026, 7, 9))


def test_df151_rejects_invalid_real_input_file(tmp_path):
    csv_path = tmp_path / "invalid-rent-roll.csv"
    _write_rent_roll(csv_path, [
        {"unit_id": "A", "monthly_rent": "-1", "occupied": "occupied", "operating_expense": "100"},
    ])

    try:
        m151.load_units_from_csv(csv_path)
    except ValueError as exc:
        assert "monthly_rent" in str(exc)
    else:
        raise AssertionError("negative rent from CSV must be rejected")
