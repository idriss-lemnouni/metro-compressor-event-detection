"""Parse MetroPT-3 without loading the raw sensor archive into memory."""
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from io import TextIOWrapper
import math
from pathlib import Path
from statistics import fmean, median
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile

SOURCE = "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip"
SENSORS = ("TP2", "TP3", "H1", "Reservoirs", "Oil_temperature", "Motor_current")
WINDOW = timedelta(minutes=5)
MINIMUM_SAMPLES = 20


@dataclass(frozen=True)
class Bucket:
    time: datetime
    mode: str
    features: tuple[float, ...]
    pressure: float


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def member_name(archive):
    candidates = [info for info in archive.infolist() if info.filename.lower().endswith(".csv")]
    if len(candidates) != 1 or candidates[0].file_size > 350_000_000:
        raise ValueError("Expected one MetroPT-3 sensor CSV below 350 MB")
    return candidates[0]


def download(path: Path, expected: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as folder:
        temporary = Path(folder) / path.name
        with urlopen(SOURCE, timeout=60) as source, temporary.open("wb") as target:
            size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > 230_000_000:
                    raise ValueError("MetroPT-3 archive exceeded 230 MB")
                target.write(chunk)
        if sha256(temporary) != expected:
            raise ValueError("MetroPT-3 SHA-256 mismatch")
        with ZipFile(temporary) as archive:
            member_name(archive)
        temporary.replace(path)


def aggregate(start: datetime, values: list[tuple[float, ...]]) -> Bucket:
    tp2, tp3, h1, reservoir, oil, motor = zip(*values)
    loaded = fmean(value >= 6 for value in motor)
    pressure = sorted(reservoir)[(len(reservoir) - 1) // 10]
    features = (
        median(tp2), median(tp3), median(h1), pressure, median(oil),
        max(tp3) - min(tp3), loaded,
    )
    return Bucket(start + WINDOW, "loaded" if loaded >= 0.2 else "other", features, pressure)


def read_archive(path: Path) -> tuple[list[Bucket], dict]:
    buckets = []
    quality = Counter()
    cadences = Counter()
    start = previous = first = None
    values = []
    with ZipFile(path) as archive, archive.open(member_name(archive)) as member:
        reader = csv.DictReader(TextIOWrapper(member, encoding="utf-8-sig"))
        if not {"timestamp", *SENSORS}.issubset(reader.fieldnames or []):
            raise ValueError("Expected timestamp and the six named sensor columns")
        for row in reader:
            quality["rows"] += 1
            timestamp = datetime.fromisoformat(row["timestamp"])
            if timestamp.tzinfo is not None:
                raise ValueError("Expected the timezone-unqualified provider clock")
            if previous is not None:
                seconds = (timestamp - previous).total_seconds()
                if seconds <= 0:
                    raise ValueError(f"Non-increasing timestamp at row {quality['rows']}")
                if seconds > 60:
                    quality["gaps_over_one_minute"] += 1
                cadences[seconds] += 1
            else:
                first = timestamp
            previous = timestamp
            bucket_start = timestamp.replace(minute=timestamp.minute // 5 * 5, second=0, microsecond=0)
            if start is not None and bucket_start != start:
                if len(values) >= MINIMUM_SAMPLES:
                    buckets.append(aggregate(start, values))
                else:
                    quality["sparse_observed_windows"] += 1
                values = []
            start = bucket_start
            try:
                readings = tuple(float(row[sensor]) for sensor in SENSORS)
            except (ValueError, TypeError):
                quality["bad_sensor_rows"] += 1
                continue
            if not all(math.isfinite(reading) for reading in readings):
                quality["bad_sensor_rows"] += 1
                continue
            values.append(readings)
        if start is not None:
            if len(values) >= MINIMUM_SAMPLES:
                buckets.append(aggregate(start, values))
            else:
                quality["sparse_observed_windows"] += 1
    if not buckets:
        raise ValueError("No valid five-minute buckets")
    quality["scorable_windows"] = len(buckets)
    # Count non-scorable bins over the interior calendar, including absent and sparse bins.
    quality["interior_nonscorable_windows"] = (
        int((buckets[-1].time - buckets[0].time) / WINDOW) + 1 - len(buckets)
    )
    return buckets, {
        **quality, "first_timestamp": first.isoformat(), "last_timestamp": previous.isoformat(),
        "common_spacing_seconds": cadences.most_common(5),
    }
