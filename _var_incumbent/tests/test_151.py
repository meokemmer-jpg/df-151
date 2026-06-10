import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib

m151 = importlib.import_module("151")
UnitRecord = m151.UnitRecord
build_report = m151.build_report
calculate_real_estate_income_metrics = m151.calculate_real_estate_income_metrics
write_report = m151.write_report


def test_real_estate_income_metrics_and_report_file(tmp_path):
    units = [
        UnitRecord(monthly_rent=1200.0, occupied=True),
        UnitRecord(monthly_rent=1300.0, occupied=False),
        UnitRecord(monthly_rent=1500.0, occupied=True),
        UnitRecord(monthly_rent=1000.0, occupied=False),
    ]

    metrics = calculate_real_estate_income_metrics(units)

    assert metrics["rental_income"] == 2700.0
    assert metrics["vacancy_rate"] == 0.5
    assert metrics["noi"] == 2700.0

    report = build_report(units)
    assert report["mission"] == "DF-151 KPM-Real-Estate-Income"
    assert report["auto_rent_adjustment"] is False
    assert report["metrics"] == metrics

    output_path = write_report(units, report_dir=tmp_path, as_of=None)
    assert output_path.exists()
    assert output_path.name.startswith("df-151-")
    assert output_path.suffix == ".json"


def test_empty_units_raise_value_error():
    try:
        calculate_real_estate_income_metrics([])
    except ValueError as exc:
        assert "at least one unit" in str(exc)
    else:
        raise AssertionError("ValueError was not raised for empty unit list")

