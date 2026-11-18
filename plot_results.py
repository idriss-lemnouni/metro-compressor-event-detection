"""Render publication figures from verified run artifacts."""
from pathlib import Path
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK = "#172b3b"
MUTED = "#526575"
TEAL = "#007e78"
BLUE = "#4069ba"
ORANGE = "#b9502d"
SOFT = "#d5e1e7"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11, "text.color": INK,
    "axes.labelcolor": INK, "axes.titlecolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": SOFT, "axes.axisbelow": True, "grid.color": SOFT,
    "grid.linewidth": 0.7, "legend.frameon": False,
})


def save(fig, out, name, title, note):
    fig.suptitle(title, x=0.055, y=0.96, ha="left", fontsize=21, fontweight="bold")
    fig.text(0.055, 0.035, note, ha="left", color=MUTED, fontsize=9)
    fig.tight_layout(rect=(0.025, .085, .995, .87), pad=1.5)
    fig.savefig(out / (name + ".png"), dpi=180, facecolor="white")
    plt.close(fig)

def render(metrics, out):
    report = json.loads(metrics.read_text(encoding="utf-8"))
    detectors = report["detectors"]
    models = [("pressure", "Pressure baseline", BLUE), ("regime_robust", "Regime-aware", TEAL)]
    events = [row["id"] for row in detectors["regime_robust"]["test"]["outcomes"]]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for i, (key, name, color) in enumerate(models):
        offsets = {row["id"]: row["lead_minutes"] for row in detectors[key]["test"]["outcomes"]}
        for j, event in enumerate(events):
            y = j + (i - .5) * .28
            lead = offsets[event]
            if lead is None:
                ax.text(175, y, "No match", va="center", color=color, fontsize=9)
            else:
                x = -lead
                ax.scatter(x, y, color=color, marker="o" if i else "s", zorder=3)
                ax.annotate("0" if x == 0 else f"{x:+.0f}", (x, y), xytext=(6, -4), textcoords="offset points",
                            color=color, fontsize=9)
        ax.scatter([], [], color=color, marker="o" if i else "s", label=name)
    ax.axvline(0, color=ORANGE, linestyle="--", linewidth=1.3)
    ax.set(yticks=range(len(events)), yticklabels=events, xlim=(-85, 228), ylim=(-.5, len(events)-.45),
           xlabel="Minutes from documented start (negative = early)", ylabel="Incident")
    ax.invert_yaxis()
    ax.legend(loc="lower right", ncol=2, fontsize=9)
    ax.grid(axis="x")
    save(fig, out, "incident-timing", "Timing of the first alert for each incident",
         "MetroPT‑3 holdout · four documented incidents · an alert may be matched during the event or up to six hours before it")

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.4))
    for index, (ax, field, title) in enumerate(zip(axes, ["matched_incidents", "unmatched_alerts_per_scorable_day"],
                                                    ["Documented incidents matched", "Unmatched alerts / scorable day"])):
        values = [detectors[key]["test"][field] for key, _, _ in models]
        bars = ax.barh([name for _, name, _ in models], values, color=[c for _, _, c in models], height=.52)
        ax.bar_label(bars, fmt="%d" if not index else "%.3f", padding=5)
        ax.set(title=title, xlim=(0, max(values) * 1.25))
        ax.grid(axis="x")
    save(fig, out, "detector-tradeoffs", "Event matching and alert burden",
         "March-calibrated thresholds · April–September holdout · unmatched alerts may include unannotated events")

    splits = report["splits"]
    names = ["Fit", "Calibrate", "Holdout"]
    fig, ax = plt.subplots(figsize=(9.5, 4.5))
    other = [splits[k]["modes"].get("other", 0) for k in ("fit", "calibration", "test")]
    active = [splits[k]["modes"].get("loaded", 0) for k in ("fit", "calibration", "test")]
    ax.bar(names, other, color=BLUE, label="Other regime", width=.6)
    bars = ax.bar(names, active, bottom=other, color=TEAL, label="Loaded regime", width=.6)
    ax.bar_label(bars, labels=[f"{x+y:,}" for x, y in zip(other, active)], padding=4)
    ax.set(ylabel="Scorable five-minute windows", ylim=(0, max(x+y for x,y in zip(other,active)) * 1.19))
    ax.legend(loc="upper left")
    ax.grid(axis="y")
    save(fig, out, "scorable-windows", "Regime coverage across chronological splits",
         "A window is scorable with at least 20 valid readings · loaded windows meet the motor-current threshold")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=Path("reports/holdout-metrics.json"))
    parser.add_argument("--out", type=Path, default=Path("figures/results"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    render(args.metrics, args.out)
