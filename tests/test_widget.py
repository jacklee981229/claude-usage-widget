import unittest
from datetime import datetime, timedelta, timezone

from widget import (AHEAD, FIVE_HOURS, NEARLY_FULL, ON_PACE, WEEK, due_alerts, elapsed, full_in, pace, resets_at,
                    resets_in, source_text)

UTC = timezone.utc
MALAYSIA = timezone(timedelta(hours=8))


class ResetTextTest(unittest.TestCase):
    def test_resets_in_rounds_up_to_the_minute(self):
        reset = datetime(2026, 9, 26, 18, 20, tzinfo=UTC)
        self.assertEqual(resets_in(reset, datetime(2026, 9, 26, 16, 15, tzinfo=UTC)), "resets in 2h 5m")
        self.assertEqual(resets_in(reset, datetime(2026, 9, 26, 18, 19, 30, tzinfo=UTC)), "resets in 1m")
        self.assertEqual(resets_in(reset, datetime(2026, 9, 26, 18, 21, tzinfo=UTC)), "resets in 0m")

    def test_no_window_running(self):
        self.assertEqual(resets_in(None, datetime(2026, 9, 26, 16, 15, tzinfo=UTC)), "not started")

    def test_weekly_reset_in_malaysia_time(self):
        self.assertEqual(resets_at(datetime(2026, 10, 3, 1, 0, tzinfo=UTC), MALAYSIA), "resets Sat 09:00")


class SourceTextTest(unittest.TestCase):
    def test_official_reading_time_in_malaysia_time(self):
        now = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)
        self.assertEqual(source_text(datetime(2026, 10, 23, 6, 2, tzinfo=UTC), now, MALAYSIA), "official 14:02 + est.")

    def test_no_reading_is_an_estimate_at_now(self):
        self.assertEqual(source_text(None, datetime(2026, 10, 23, 8, 0, tzinfo=UTC), MALAYSIA), "estimate · 16:00")


class ElapsedTest(unittest.TestCase):
    def test_five_hour_window_with_3h_11m_left(self):
        now = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)
        self.assertAlmostEqual(elapsed(now + timedelta(hours=3, minutes=11), now, FIVE_HOURS), 109 / 300)

    def test_week_from_saturday_to_tuesday_afternoon(self):
        now = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)  # Tuesday 15:00 in Malaysia
        self.assertAlmostEqual(elapsed(datetime(2026, 10, 31, 1, 0, tzinfo=UTC), now, WEEK), 78 / 168)

    def test_stays_between_none_and_all(self):
        now = datetime(2026, 10, 27, 7, 0, tzinfo=UTC)
        self.assertEqual(elapsed(now - timedelta(minutes=5), now, FIVE_HOURS), 1.0)
        self.assertEqual(elapsed(now + timedelta(hours=6), now, FIVE_HOURS), 0.0)
        self.assertIsNone(elapsed(None, now, FIVE_HOURS))


class PaceTest(unittest.TestCase):
    def test_keeping_up_with_the_clock(self):
        self.assertEqual(pace(43, 0.36), (ON_PACE, "On pace"))

    def test_more_than_ten_points_ahead(self):
        self.assertEqual(pace(50, 0.36), (AHEAD, "Ahead of time"))
        self.assertEqual(pace(46, 0.36)[0], ON_PACE)

    def test_nearly_full_wins_even_late_in_the_window(self):
        self.assertEqual(pace(88, 0.95), (NEARLY_FULL, "Nearly full"))

    def test_no_window_running_is_on_pace(self):
        self.assertEqual(pace(0, None), (ON_PACE, "On pace"))

    def test_filling_before_the_reset_says_when(self):
        now = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)
        self.assertEqual(pace(40, 0.5, now + timedelta(minutes=42, seconds=21), now), (AHEAD, "Full in ~43m"))
        self.assertEqual(pace(91, 0.9, now + timedelta(minutes=12), now), (NEARLY_FULL, "Full in ~12m"))


class FullInTest(unittest.TestCase):
    NOW = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)

    def test_minutes_hours_and_days(self):
        self.assertEqual(full_in(self.NOW + timedelta(minutes=59, seconds=1), self.NOW), "Full in ~1h 0m")
        self.assertEqual(full_in(self.NOW + timedelta(hours=1, minutes=20), self.NOW), "Full in ~1h 20m")
        self.assertEqual(full_in(self.NOW + timedelta(days=1, hours=4, minutes=30), self.NOW), "Full in ~1d 4h")

    def test_already_full(self):
        self.assertEqual(full_in(self.NOW, self.NOW), "Full")


class DueAlertsTest(unittest.TestCase):
    NOW = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)
    RESET = datetime(2026, 10, 28, 8, 44, tzinfo=UTC)
    SOON = NOW + timedelta(minutes=42)

    def test_filling_before_the_reset_raises_once_per_window(self):
        due = due_alerts({}, self.NOW, 68, self.RESET, self.SOON, None, MALAYSIA)
        self.assertEqual(due, {"five-pace": self.RESET.isoformat()})
        self.assertEqual(due_alerts(due, self.NOW, 70, self.RESET, self.SOON, None, MALAYSIA), {})
        later = self.RESET + timedelta(hours=5)
        self.assertEqual(due_alerts(due, self.NOW, 40, later, self.SOON, None, MALAYSIA),
                         {"five-pace": later.isoformat()})

    def test_90_percent_raises_even_after_the_pace_alert(self):
        sent = {"five-pace": self.RESET.isoformat()}
        self.assertEqual(due_alerts(sent, self.NOW, 89, self.RESET, self.SOON, None, MALAYSIA), {})
        self.assertEqual(due_alerts(sent, self.NOW, 90, self.RESET, None, None, MALAYSIA),
                         {"five-full": self.RESET.isoformat()})

    def test_no_window_raises_nothing(self):
        self.assertEqual(due_alerts({}, self.NOW, 95, None, None, None, MALAYSIA), {})

    def test_week_raises_once_a_malaysian_day(self):
        sent = due_alerts({}, self.NOW, 10, self.RESET, None, self.SOON, MALAYSIA)
        self.assertEqual(sent, {"week-pace": "2026-10-28"})
        # 23:30 the same day in Malaysia, then 00:30 the next.
        self.assertEqual(due_alerts(sent, datetime(2026, 10, 28, 15, 30, tzinfo=UTC), 10, None, None, self.SOON,
                                    MALAYSIA), {})
        self.assertEqual(due_alerts(sent, datetime(2026, 10, 28, 16, 30, tzinfo=UTC), 10, None, None, self.SOON,
                                    MALAYSIA), {"week-pace": "2026-10-29"})


if __name__ == "__main__":
    unittest.main()
