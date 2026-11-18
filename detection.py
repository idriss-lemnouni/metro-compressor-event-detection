"""Tune alert episodes on a prior month and evaluate documented failures."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from statistics import median

from telemetry import Bucket, WINDOW

FLOORS = (0.05, 0.05, 0.05, 0.05, 0.25, 0.05, 0.05)
CALIBRATION_START = datetime(2020, 3, 1)
TEST_START = datetime(2020, 4, 1)
DETECTORS = ("pressure", "regime_robust")
QUANTILES = (0.90, 0.95, 0.97, 0.98, 0.99, 0.995, 0.999, 1.0)


@dataclass(frozen=True)
class Incident:
    code: str
    start: datetime
    end: datetime


INCIDENTS = tuple(
    Incident(code, datetime.fromisoformat(start), datetime.fromisoformat(end))
    for code, start, end in (
        ("UCI-01", "2020-04-18 00:00", "2020-04-18 23:59"),
        ("UCI-02", "2020-05-29 23:30", "2020-05-30 06:00"),
        ("UCI-03", "2020-06-05 10:00", "2020-06-07 14:30"),
        ("UCI-04", "2020-07-15 14:30", "2020-07-15 19:00"),
    )
)


def profiles(training: list[Bucket]) -> dict:
    by_mode = defaultdict(list)
    for row in training:
        by_mode[row.mode].append(row.features)
    output = {}
    for mode, features in by_mode.items():
        if len(features) < 100:
            raise ValueError(f"Need at least 100 training windows for mode {mode!r}")
        columns = list(zip(*features))
        center = tuple(median(values) for values in columns)
        spread = tuple(
            max(floor, 1.4826 * median(abs(value - midpoint) for value in values))
            for midpoint, values, floor in zip(center, columns, FLOORS)
        )
        output[mode] = (center, spread)
    return output


def scores(buckets, profile, detector):
    if detector == "pressure":
        return [-row.pressure for row in buckets]
    output = []
    for row in buckets:
        if row.mode not in profile:
            raise ValueError(f"Unavailable training mode: {row.mode}")
        center, spread = profile[row.mode]
        output.append(math.sqrt(
            sum(((value - location) / scale) ** 2
                for value, location, scale in zip(row.features, center, spread)) / len(center)
        ))
    return output


def episodes(buckets, values, threshold, minimum=3, cooldown=timedelta(minutes=30)):
    alerts = []
    streak = 0
    previous = None
    for row, score in zip(buckets, values, strict=True):
        if previous is not None and row.time - previous != WINDOW:
            streak = 0
        previous = row.time
        streak = streak + 1 if score > threshold else 0
        if streak == minimum and (not alerts or row.time - alerts[-1] >= cooldown):
            alerts.append(row.time)
    return alerts


def sample_days(buckets):
    return len(buckets) * WINDOW.total_seconds() / 86400


def calibrate(buckets, values, budget):
    ordered = sorted(values)
    for quantile in QUANTILES:
        threshold = ordered[math.ceil(quantile * len(ordered)) - 1]
        alerts = episodes(buckets, values, threshold)
        rate = len(alerts) / sample_days(buckets)
        if rate <= budget:
            return {"threshold": threshold, "quantile": quantile,
                    "alert_count": len(alerts), "alerts_per_scorable_day": rate}
    raise ValueError("No calibration threshold met the budget")


def incident_report(buckets, alerts, incidents=INCIDENTS, lead=timedelta(hours=6)):
    matches = {incident.code: [] for incident in incidents}
    unmatched = []
    for alert in alerts:
        match = next((event for event in incidents if event.start - lead <= alert <= event.end), None)
        if match is None:
            unmatched.append(alert)
        else:
            matches[match.code].append(alert)
    outcomes = []
    for incident in incidents:
        in_scope_rows = sum(incident.start - lead <= row.time <= incident.end for row in buckets)
        hit = matches[incident.code][0] if matches[incident.code] else None
        outcomes.append({
            "id": incident.code,
            "start": incident.start.isoformat(),
            "end": incident.end.isoformat(),
            "scored_windows": in_scope_rows,
            "first_alert": hit.isoformat() if hit else None,
            "lead_minutes": (incident.start - hit).total_seconds() / 60 if hit else None,
            "alerts_in_window": len(matches[incident.code]),
        })
    observed = sum(row["scored_windows"] > 0 for row in outcomes)
    hit_count = sum(row["first_alert"] is not None for row in outcomes)
    return {
        "alert_count": len(alerts), "unmatched_alerts": len(unmatched),
        "unmatched_alerts_per_scorable_day": len(unmatched) / sample_days(buckets),
        "reported_incidents": len(incidents), "observable_incidents": observed,
        "matched_incidents": hit_count, "incident_recall": hit_count / observed if observed else None,
        "before_start": sum(row["lead_minutes"] is not None and row["lead_minutes"] > 0 for row in outcomes),
        "outcomes": outcomes,
    }


def run_experiment(buckets, budget):
    training = [row for row in buckets if row.time < CALIBRATION_START]
    calibration = [row for row in buckets if CALIBRATION_START <= row.time < TEST_START]
    test = [row for row in buckets if row.time >= TEST_START]
    if not (training and calibration and test):
        raise ValueError("February training, March calibration and April–August test are required")
    profile = profiles(training)
    estimates = {}
    alerts = {}
    for detector in DETECTORS:
        tuned = calibrate(calibration, scores(calibration, profile, detector), budget)
        trigger = episodes(test, scores(test, profile, detector), tuned["threshold"])
        estimates[detector] = {"calibration": tuned, "test": incident_report(test, trigger)}
        alerts[detector] = trigger
    counts = {
        name: {"rows": len(values), "scorable_days": sample_days(values),
               "modes": dict(Counter(row.mode for row in values))}
        for name, values in (("fit", training), ("calibration", calibration), ("test", test))
    }
    return counts, estimates, alerts
