from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from detection import Incident, calibrate, episodes, incident_report
from telemetry import Bucket, WINDOW, read_archive


def bucket(minute, score=1.0):
    time = datetime(2020, 4, 10, 0) + timedelta(minutes=minute)
    return Bucket(time, "other", (score,) * 7, score)


class MetroTests(unittest.TestCase):
    def test_gap_resets_streak_and_cooldown_suppresses_repeat(self):
        windows = [bucket(m) for m in (5, 10, 20, 25, 30, 35, 40, 45, 50, 55, 60)]
        scores = [1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1]
        self.assertEqual(episodes(windows, scores, 0.5), [bucket(30).time])

    def test_incident_lead_and_unmatched(self):
        windows = [bucket(m) for m in (5, 10, 15, 30, 35, 40, 300)]
        event = Incident("example", bucket(35).time, bucket(40).time)
        alerts = [bucket(30).time, bucket(35).time, bucket(300).time]
        metrics = incident_report(windows, alerts, incidents=(event,), lead=WINDOW)
        self.assertEqual(metrics["matched_incidents"], 1)
        self.assertEqual(metrics["before_start"], 1)
        self.assertEqual(metrics["outcomes"][0]["lead_minutes"], 5)
        self.assertEqual(metrics["outcomes"][0]["alerts_in_window"], 2)
        self.assertEqual(metrics["unmatched_alerts"], 1)

    def test_calibration_respects_episode_rate(self):
        windows = [bucket(m) for m in range(5, 525, 5)]
        values = [window.time.minute % 20 for window in windows]
        tuned = calibrate(windows, values, 0.1)
        self.assertLessEqual(tuned["alerts_per_scorable_day"], 0.1)

    def test_archive_gaps_keep_calendar_and_right_edge(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "small.zip"
            header = "timestamp,TP2,TP3,H1,Reservoirs,Oil_temperature,Motor_current"
            start = datetime(2020, 4, 19, 0)
            rows = []
            for minute in (0, 10):
                for index in range(25):
                    timestamp = start + timedelta(minutes=minute, seconds=10 * index)
                    rows.append(f"{timestamp.isoformat()},9,8,0,7,50,7")
            with ZipFile(archive, "w") as handle:
                handle.writestr("telemetry.csv", "\n".join([header, *rows]))
            windows, info = read_archive(archive)
            self.assertEqual([row.time for row in windows], [
                start + timedelta(minutes=5), start + timedelta(minutes=15)
            ])
            self.assertEqual(windows[0].mode, "loaded")
            self.assertEqual(info["interior_nonscorable_windows"], 1)
            self.assertEqual(info["gaps_over_one_minute"], 1)
            self.assertEqual(info["common_spacing_seconds"][0], (10, 48))


if __name__ == "__main__":
    unittest.main()
