import unittest
from datetime import datetime, timedelta, timezone

from datetime import date

from widget import RAINBOW, day_colour, resets_at, resets_in, source_text

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


class DayColourTest(unittest.TestCase):
    def test_a_week_goes_round_the_rainbow_from_monday(self):
        week = [day_colour(date(2026, 10, 19 + i)) for i in range(7)]  # Monday 19 Oct to Sunday 25 Oct
        self.assertEqual(week, list(RAINBOW))

    def test_next_monday_starts_again(self):
        self.assertEqual(day_colour(date(2026, 10, 26)), RAINBOW[0])


if __name__ == "__main__":
    unittest.main()
