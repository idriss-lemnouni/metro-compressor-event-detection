"""Benchmark compressor alert episodes on the UCI MetroPT-3 archive."""
import argparse
import csv
from html import escape
import json
import math
from pathlib import Path
from zipfile import BadZipFile

from detection import run_experiment
from telemetry import SOURCE, download, read_archive, sha256


def write_report(path, results):
    rows = []
    for name, result in results["detectors"].items():
        score = result["test"]
        rows.append(
            f'<tr><th scope="row">{escape(name.replace("_", " "))}</th>'
            f'<td>{score["matched_incidents"]}/{score["observable_incidents"]}</td>'
            f'<td>{score["before_start"]}</td>'
            f'<td>{score["unmatched_alerts_per_scorable_day"]:.3f}</td></tr>'
        )
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MetroPT-3 compressor detection</title>
<style>
body{{font:16px/1.5 system-ui;color:#15343a;background:#f7faf9;max-width:58rem;margin:2rem auto;padding:0 1rem}}
table{{border-collapse:collapse;background:white;width:100%}} th,td{{text-align:left;border-bottom:1px solid #cfdfdc;padding:.65rem}}
thead{{background:#e0eeeb}} .scroll{{overflow:auto}} a{{color:#086370}}
</style>
<h1>Compressor event detection · MetroPT-3</h1>
<p>Comparison from 1 April to 1 September 2020 (partial final day), using thresholds set on March data.</p>
<div class="scroll"><table><thead><tr><th>Detector</th><th>Recorded incidents matched</th>
<th>First alert before incident</th><th>Unmatched alerts per scorable day</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p><a href="metrics.json">Event-level details and calibration</a> · <a href="alerts.csv">Alert timestamps</a></p>
</html>
"""
    path.write_text(page, encoding="utf-8")


def audit(path: Path, expected: str, output: Path, budget: float) -> dict:
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("Expected a positive, finite alert budget")
    digest = sha256(path)
    if digest != expected.lower():
        raise ValueError(f"MetroPT-3 SHA-256 mismatch: {digest}")
    windows, diagnostics = read_archive(path)
    splits, results, alerts = run_experiment(windows, budget)
    payload = {
        "source": SOURCE, "archive_bytes": path.stat().st_size, "archive_sha256": digest,
        "diagnostics": diagnostics, "calibration_alert_budget": budget,
        "splits": splits, "detectors": results,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with (output / "alerts.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("detector", "alert_time_source_clock"))
        writer.writerows((name, alert.isoformat()) for name, times in alerts.items() for alert in times)
    write_report(output / "events.html", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "audit"):
        command = commands.add_parser(name)
        command.add_argument("--archive", required=True, type=Path)
        command.add_argument("--sha256", required=True)
    commands.choices["audit"].add_argument("--out", required=True, type=Path)
    commands.choices["audit"].add_argument("--budget", type=float, default=1.0)
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            download(args.archive, args.sha256.lower())
        else:
            result = audit(args.archive, args.sha256, args.out, args.budget)
            print(json.dumps({"diagnostics": result["diagnostics"], "detectors": result["detectors"]}, indent=2))
    except (OSError, ValueError, BadZipFile) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
