"""DF-151 tracker engine for KPM real estate income metrics."""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone


DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-151.lock")
DF_ID = "151"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-151"
    iso_timestamp: str = ""
    source: str = "mock"
    rental_income_eur: float = 0
    opex_eur: float = 0
    net_yield_pct: float = 0
    occupancy_per_property: dict = field(default_factory=dict)
    vacancy_loss_eur: float = 0


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    try:
        age = time.time() - p.stat().st_mtime
    except OSError:
        return False
    return age >= min_age_sec


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    try:
        LOCK_DIR.mkdir(mode=0o700)
        identity = {
            "df_id": DF_ID,
            "pid": os.getpid(),
            "created_at": iso_now(),
            "cwd": str(Path.cwd()),
        }
        (LOCK_DIR / "identity.json").write_text(
            json.dumps(identity, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except FileExistsError:
        try:
            age = time.time() - LOCK_DIR.stat().st_mtime
        except OSError:
            return False
        if age <= stale_after_sec:
            return False
        try:
            for child in LOCK_DIR.iterdir():
                if child.is_file() or child.is_symlink():
                    child.unlink()
            LOCK_DIR.rmdir()
        except OSError:
            return False
        try:
            LOCK_DIR.mkdir(mode=0o700)
            identity = {
                "df_id": DF_ID,
                "pid": os.getpid(),
                "created_at": iso_now(),
                "cwd": str(Path.cwd()),
                "stale_lock_replaced": True,
            }
            (LOCK_DIR / "identity.json").write_text(
                json.dumps(identity, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False
    except OSError:
        return False


def release_lock() -> None:
    try:
        for child in LOCK_DIR.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
        LOCK_DIR.rmdir()
    except FileNotFoundError:
        return
    except OSError:
        return


def k17_pre_action_verification(anchors) -> dict:
    missing = []
    for anchor in anchors:
        if isinstance(anchor, Path):
            exists = anchor.exists()
            label = str(anchor)
        else:
            label = str(anchor)
            exists = bool(label.strip())
        if not exists:
            missing.append(label)

    env_tag = os.environ.get("DF_151_ENV_TAG", "local")
    return {
        "ok": len(missing) == 0,
        "missing_anchors": missing,
        "env_tag": env_tag,
    }


def _is_real_api_enabled() -> bool:
    value = os.environ.get("DF_151_REAL_API_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    return sorted({match.group(0) for match in DECISION_KEYWORDS_REGEX.finditer(str(text))})


def assert_no_decision_keywords(output) -> None:
    if isinstance(output, str):
        text = output
    else:
        text = json.dumps(output, ensure_ascii=False, sort_keys=True)
    hits = scan_output_for_decision_keywords(text)
    if hits:
        raise ValueError("Q_0/K_0 keyword block triggered: " + ", ".join(hits))


def _float_env(name: str, default: float = 0.0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _dict_env(name: str) -> dict:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def collect_tracker_output() -> TrackerOutput:
    out = TrackerOutput()
    out.iso_timestamp = iso_now()

    if _is_real_api_enabled():
        out.source = "env"
        out.rental_income_eur = _float_env("DF_151_RENTAL_INCOME_EUR", 0.0)
        out.opex_eur = _float_env("DF_151_OPEX_EUR", 0.0)
        out.vacancy_loss_eur = _float_env("DF_151_VACANCY_LOSS_EUR", 0.0)
        out.occupancy_per_property = _dict_env("DF_151_OCCUPANCY_PER_PROPERTY")
    else:
        out.source = "mock"
        out.rental_income_eur = 125000.0
        out.opex_eur = 42000.0
        out.vacancy_loss_eur = 8500.0
        out.occupancy_per_property = {
            "hotel_alpha": 0.91,
            "hotel_beta": 0.84,
            "hotel_gamma": 0.88,
        }

    base = out.rental_income_eur - out.vacancy_loss_eur
    out.net_yield_pct = round(((base - out.opex_eur) / base) * 100, 4) if base else 0.0
    return out


def _report_path(now=None) -> Path:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    return DF_DIR / "reports" / f"df-151-{stamp}.json"


def main() -> int:
    if not acquire_lock_with_identity():
        return 3

    try:
        anchors = [DF_DIR, DF_DIR / "reports"]
        pav = k17_pre_action_verification(anchors)
        if not pav["ok"]:
            return 3

        output = collect_tracker_output()
        report = {
            "pav": pav,
            "tracker_output": asdict(output),
        }
        assert_no_decision_keywords(report)

        reports_dir = DF_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = _report_path()
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        sys.stderr.write(f"df-{DF_ID} failed: {exc}\n")
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())