import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from usage_estimate import (FIVE_HOUR_FULL, WEEKLY_FULL, WEEKLY_RESET, TranscriptReader, combine, estimate,
                            five_hour_window, forecast, read_official, weekly_window, weighted_cost)

UTC = timezone.utc
M = 1_000_000


def at(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


class WeightedCostTest(unittest.TestCase):
    def test_every_token_type_at_its_price(self):
        usage = {"input_tokens": M, "output_tokens": M, "cache_read_input_tokens": M,
                 "cache_creation_input_tokens": 2 * M,
                 "cache_creation": {"ephemeral_5m_input_tokens": M, "ephemeral_1h_input_tokens": M}}
        # Opus 5.5: input 4 + output 20 + 5-minute write 5 + 1-hour write 8 + cache read 0.20
        self.assertAlmostEqual(weighted_cost("claude-opus-5-5", usage), 37.2)

    def test_cache_writes_without_a_split_count_as_5_minute(self):
        self.assertAlmostEqual(weighted_cost("claude-opus-5-5", {"cache_creation_input_tokens": M}), 5.0)

    def test_fast_mode_doubles(self):
        self.assertAlmostEqual(weighted_cost("claude-opus-5-5", {"output_tokens": M, "speed": "fast"}), 40.0)

    def test_opus_5_carries_its_plan_weight(self):
        self.assertAlmostEqual(weighted_cost("claude-opus-5", {"output_tokens": M}), 25 * 1.85)

    def test_dated_and_unknown_models(self):
        self.assertAlmostEqual(weighted_cost("claude-haiku-4-5-20251001", {"output_tokens": M}), 5.0)
        self.assertAlmostEqual(weighted_cost("claude-sonnet-9", {"output_tokens": M}), 20.0)


class FiveHourWindowTest(unittest.TestCase):
    def test_starts_at_first_activity_rounded_down_to_10_minutes(self):
        self.assertEqual(five_hour_window({at("2026-09-26 13:27:45")}, at("2026-09-26 14:00")),
                         (at("2026-09-26 13:20"), at("2026-09-26 18:20")))

    def test_next_window_starts_when_activity_follows_a_reset(self):
        activity = {at("2026-09-02 01:12:11"), at("2026-09-02 01:45:44"), at("2026-09-02 06:10:16")}
        self.assertEqual(five_hour_window(activity, at("2026-09-02 06:30")),
                         (at("2026-09-02 06:10"), at("2026-09-02 11:10")))

    def test_activity_exactly_at_the_end_starts_a_new_window(self):
        activity = {at("2026-09-26 08:00"), at("2026-09-26 13:00")}
        self.assertEqual(five_hour_window(activity, at("2026-09-26 13:05")),
                         (at("2026-09-26 13:00"), at("2026-09-26 18:00")))

    def test_no_window_after_5_quiet_hours_and_future_activity_ignored(self):
        activity = {at("2026-09-26 08:00"), at("2026-09-26 14:00")}
        self.assertIsNone(five_hour_window(activity, at("2026-09-26 13:30")))


class WeeklyWindowTest(unittest.TestCase):
    def test_windows_around_the_known_reset(self):
        week = timedelta(days=7)
        self.assertEqual(weekly_window(WEEKLY_RESET), (WEEKLY_RESET, WEEKLY_RESET + week))
        self.assertEqual(weekly_window(WEEKLY_RESET - timedelta(seconds=1)), (WEEKLY_RESET - week, WEEKLY_RESET))
        self.assertEqual(weekly_window(WEEKLY_RESET + timedelta(days=20)), (WEEKLY_RESET + 2 * week, WEEKLY_RESET + 3 * week))

    def test_saturday_9am_malaysia_time(self):
        # 27 Sep 00:15 in UTC+8 falls in the week from Sat 26 Sep 09:00 to Sat 3 Oct 09:00.
        self.assertEqual(weekly_window(at("2026-09-26 16:15")), (at("2026-09-26 01:00"), at("2026-10-03 01:00")))


class EstimateTest(unittest.TestCase):
    def setUp(self):
        self.costs = [
            (at("2026-09-25 23:00"), 1000.0),  # before this week
            (at("2026-09-26 02:00"), WEEKLY_FULL * 0.10 - FIVE_HOUR_FULL * 0.10),
            (at("2026-09-26 13:30"), FIVE_HOUR_FULL * 0.10),
            (at("2026-09-26 15:00"), 50.0),  # after `now` in the first test
        ]
        self.activity = {at("2026-09-25 23:00"), at("2026-09-26 02:00"), at("2026-09-26 13:28"), at("2026-09-26 13:30")}

    def test_both_windows(self):
        five, five_reset, week, week_reset = estimate(self.costs, self.activity, at("2026-09-26 14:00"))
        self.assertAlmostEqual(five, 10.0)
        self.assertEqual(five_reset, at("2026-09-26 18:20"))
        self.assertAlmostEqual(week, 10.0)
        self.assertEqual(week_reset, at("2026-10-03 01:00"))

    def test_no_running_5_hour_window(self):
        five, five_reset, week, _ = estimate(self.costs, self.activity, at("2026-09-26 19:00"))
        self.assertEqual((five, five_reset), (0.0, None))
        self.assertAlmostEqual(week, 10.0 + 50 / WEEKLY_FULL * 100)


class ReadOfficialTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "usage.json"

    def test_reads_both_windows(self):
        self.file.write_text(json.dumps({
            "measuredAt": "2026-10-23T06:02:00.000Z",
            "fiveHour": {"percent": 42.5, "resetsAt": "2026-10-23T09:00:00Z"},
            "sevenDay": {"percent": 61, "resetsAt": "2026-10-24T01:00:00Z"}}), encoding="utf-8")
        self.assertEqual(read_official(self.file), {
            "measured_at": at("2026-10-23 06:02"),
            "five_hour": (42.5, at("2026-10-23 09:00")),
            "seven_day": (61.0, at("2026-10-24 01:00"))})

    def test_one_window_missing(self):
        self.file.write_text(json.dumps({"measuredAt": "2026-10-23T06:02:00Z", "fiveHour": None,
                                         "sevenDay": {"percent": 61, "resetsAt": "2026-10-24T01:00:00Z"}}), encoding="utf-8")
        official = read_official(self.file)
        self.assertIsNone(official["five_hour"])
        self.assertEqual(official["seven_day"], (61.0, at("2026-10-24 01:00")))

    def test_missing_broken_or_zoneless_file_is_none(self):
        self.assertIsNone(read_official(self.file))
        self.file.write_text("{not json", encoding="utf-8")
        self.assertIsNone(read_official(self.file))
        self.file.write_text(json.dumps({"measuredAt": "2026-10-23T06:02:00"}), encoding="utf-8")
        self.assertIsNone(read_official(self.file))

    def test_zoneless_reset_drops_that_window(self):
        self.file.write_text(json.dumps({"measuredAt": "2026-10-23T06:02:00Z",
                                         "fiveHour": {"percent": 42.5, "resetsAt": "2026-10-23T09:00:00"}}), encoding="utf-8")
        self.assertIsNone(read_official(self.file)["five_hour"])


class CombineTest(unittest.TestCase):
    NOW = at("2026-10-23 08:00")

    def setUp(self):
        self.official = {"measured_at": at("2026-10-23 06:00"),
                         "five_hour": (40.0, at("2026-10-23 09:00")),
                         "seven_day": (60.0, at("2026-10-24 01:00"))}
        self.costs = [
            (at("2026-10-23 05:30"), FIVE_HOUR_FULL * 0.30),  # already in the official reading
            (at("2026-10-23 07:00"), FIVE_HOUR_FULL * 0.05),  # since the reading
        ]
        self.activity = {at("2026-10-23 05:30"), at("2026-10-23 07:00")}

    def test_official_plus_use_since_the_reading(self):
        five, five_reset, week, week_reset, measured_at = combine(self.costs, self.activity, self.NOW, self.official)
        self.assertAlmostEqual(five, 45.0)
        self.assertEqual(five_reset, at("2026-10-23 09:00"))
        self.assertAlmostEqual(week, 60.0 + FIVE_HOUR_FULL * 0.05 / WEEKLY_FULL * 100)
        self.assertEqual(week_reset, at("2026-10-24 01:00"))
        self.assertEqual(measured_at, at("2026-10-23 06:00"))

    def test_reset_5_hour_window_falls_back_to_the_estimate(self):
        later = at("2026-10-23 10:00")
        costs = self.costs + [(at("2026-10-23 09:30"), FIVE_HOUR_FULL * 0.02)]
        activity = self.activity | {at("2026-10-23 09:30")}
        five, five_reset, week, _, measured_at = combine(costs, activity, later, self.official)
        # The estimate's own window, started 09:30 with the first request after 09:00.
        self.assertAlmostEqual(five, 2.0)
        self.assertEqual(five_reset, at("2026-10-23 14:30"))
        self.assertAlmostEqual(week, 60.0 + FIVE_HOUR_FULL * 0.07 / WEEKLY_FULL * 100)
        self.assertEqual(measured_at, at("2026-10-23 06:00"))

    def test_both_windows_reset_is_the_estimate_alone(self):
        later = at("2026-10-24 02:00")
        self.assertEqual(combine(self.costs, self.activity, later, self.official),
                         (*estimate(self.costs, self.activity, later), None))

    def test_no_official_reading_is_the_estimate_alone(self):
        self.assertEqual(combine(self.costs, self.activity, self.NOW, None),
                         (*estimate(self.costs, self.activity, self.NOW), None))


class ForecastTest(unittest.TestCase):
    NOW = at("2026-10-28 06:00")
    FIVE_RESET = NOW + timedelta(hours=2, minutes=44)
    WEEK_RESET = at("2026-10-31 01:00")

    def steady(self, percent, minutes, every=5, full=FIVE_HOUR_FULL):
        """`percent` of a window used in even replies every `every` minutes over the last `minutes`."""
        times = [self.NOW - timedelta(minutes=m) for m in range(0, minutes, every)]
        return [(t, full * percent / 100 / len(times)) for t in times]

    def five_full(self, costs, used, reset=None):
        return forecast(costs, self.NOW, used, reset or self.FIVE_RESET, 0, self.WEEK_RESET)[0]

    def test_68_percent_in_an_hour_and_a_half_fills_in_42_minutes(self):
        # The last half hour holds 6 of the 18 replies, 22.7 points; 32 more take 42.4 minutes at that pace.
        full = self.five_full(self.steady(68, 90), 68)
        self.assertAlmostEqual((full - self.NOW) / timedelta(minutes=1), 42.35, places=1)

    def test_the_same_pace_raises_it_at_30_percent(self):
        self.assertIsNotNone(self.five_full(self.steady(30, 40), 30))
        self.assertIsNone(self.five_full(self.steady(29, 40), 29))

    def test_idle_for_a_quarter_hour_forecasts_nothing(self):
        costs = [(t - timedelta(minutes=16), c) for t, c in self.steady(68, 90)]
        self.assertIsNone(self.five_full(costs, 68))

    def test_a_pace_that_lasts_past_the_reset_forecasts_nothing(self):
        self.assertIsNone(self.five_full(self.steady(40, 30), 40, reset=self.NOW + timedelta(minutes=30)))
        self.assertIsNotNone(self.five_full(self.steady(40, 30), 40, reset=self.NOW + timedelta(hours=4)))

    def test_pace_counts_only_this_window(self):
        # The window began 10 minutes ago: the previous window's replies before that don't set the pace.
        reset = self.NOW + timedelta(hours=4, minutes=50)
        old = [(self.NOW - timedelta(minutes=m), FIVE_HOUR_FULL) for m in (12, 15, 20)]
        now_costs = self.steady(35, 10)
        full = self.five_full(old + now_costs, 35, reset)
        self.assertAlmostEqual((full - self.NOW) / timedelta(minutes=1), 65 / 35 * 10)

    def test_no_window_running(self):
        self.assertIsNone(forecast(self.steady(68, 90), self.NOW, 0, None, 0, self.WEEK_RESET)[0])

    def test_week_paced_on_its_last_day(self):
        # Wednesday 14:00 in Malaysia, 71% used, 30 points of it in the last day: full in a day, before Saturday.
        costs = self.steady(30, 24 * 60, every=60, full=WEEKLY_FULL)
        week_full = forecast(costs, self.NOW, 0, None, 71, self.WEEK_RESET)[1]
        self.assertAlmostEqual((week_full - self.NOW) / timedelta(hours=1), 29 / 30 * 24)
        self.assertIsNone(forecast(self.steady(10, 24 * 60, every=60, full=WEEKLY_FULL), self.NOW, 0, None, 71,
                                   self.WEEK_RESET)[1])


def user_line(ts, uuid):
    return json.dumps({"type": "user", "uuid": uuid, "parentUuid": None, "timestamp": ts,
                       "message": {"role": "user", "content": "hi"}})


def reply_line(ts, msg_id, output, uuid, parent=None, model="claude-opus-5-5"):
    return json.dumps({"type": "assistant", "uuid": uuid, "parentUuid": parent, "timestamp": ts,
                       "requestId": "req_" + msg_id,
                       "message": {"id": msg_id, "model": model, "usage": {"output_tokens": output}}})


class TranscriptReaderTest(unittest.TestCase):
    NOW = at("2026-09-26 14:00")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "c--repos-Jack" / "session.jsonl"
        self.file.parent.mkdir()
        self.reader = TranscriptReader(tmp.name)

    def write(self, text):
        with open(self.file, "a", encoding="utf-8") as fh:
            fh.write(text)

    def test_reply_repeated_per_content_block_counts_once(self):
        self.write("\n".join([user_line("2026-09-26T13:28:00.000Z", "u1"),
                              reply_line("2026-09-26T13:28:05.000Z", "msg_1", 10, "a1", "u1"),
                              reply_line("2026-09-26T13:28:06.000Z", "msg_1", 50, "a2", "a1")]) + "\n")
        self.reader.refresh(self.NOW)
        self.assertEqual(list(self.reader.costs.values()), [(at("2026-09-26 13:28:06"), 50 * 20 / M)])
        # The request went out when the prompt was written.
        self.assertEqual(self.reader.activity, {at("2026-09-26 13:28:00")})

    def test_prompt_without_a_reply_is_not_activity(self):
        self.write("\n".join([user_line("2026-09-26T13:00:00.000Z", "u0"),
                              user_line("2026-09-26T13:28:00.000Z", "u1"),
                              reply_line("2026-09-26T13:28:05.000Z", "msg_1", 10, "a1", "u1")]) + "\n")
        self.reader.refresh(self.NOW)
        self.assertEqual(self.reader.activity, {at("2026-09-26 13:28:00")})

    def test_unfinished_line_waits_for_its_newline(self):
        line = reply_line("2026-09-26T13:28:05.000Z", "msg_1", 10, "a1")
        self.write(line[:30])
        self.reader.refresh(self.NOW)
        self.assertEqual(self.reader.costs, {})
        self.write(line[30:] + "\n" + reply_line("2026-09-26T13:40:00.000Z", "msg_2", 10, "a2") + "\n")
        self.reader.refresh(self.NOW)
        self.assertEqual(len(self.reader.costs), 2)
        # With the prompt line missing, the reply's own time stands in for the request.
        self.assertEqual(self.reader.activity, {at("2026-09-26 13:28:05"), at("2026-09-26 13:40")})

    def test_synthetic_replies_and_old_lines_are_dropped(self):
        self.write(reply_line("2026-09-26T13:28:05.000Z", "msg_1", 10, "a1", model="<synthetic>") + "\n"
                   + reply_line("2026-09-10T00:00:00.000Z", "msg_2", 10, "a2") + "\n")
        self.reader.refresh(self.NOW)
        self.assertEqual((self.reader.costs, self.reader.activity), ({}, set()))


if __name__ == "__main__":
    unittest.main()
