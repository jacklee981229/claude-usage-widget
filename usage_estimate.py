"""Estimate Claude plan usage (5-hour and weekly %) from Claude Code's transcripts.

Anthropic doesn't publish the limits in tokens, so each reply is weighted by its
API price and scaled by factors calibrated against the Claude app's usage screen.
When the usage-file mod has written an official reading, that is the base instead,
and only the use since the reading is estimated.
"""
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
# Written by the usage-file mod (mod/) with the official percentages from Claude Code.
OFFICIAL_FILE = Path.home() / ".claude" / "usage-widget" / "usage.json"

# USD per million tokens: input, output, cache read.
PRICES = {
    "claude-opus-5-5": (4, 20, 0.20),
    "claude-opus-5": (5, 25, 0.50),
    "claude-fable-5-1": (10, 50, 0.25),
    "claude-fable-5": (10, 50, 1.00),
    "claude-sonnet-5": (2, 10, 0.20),
    "claude-haiku-4-5": (1, 5, 0.10),
}
UNKNOWN_MODEL_PRICE = PRICES["claude-opus-5-5"]
# The plan doesn't count every model at its API price: the September limit hits
# (all Opus 5) came at about half the API cost that 100% takes on Opus 5.5.
PLAN_WEIGHTS = {"claude-opus-5": 1.85}

# Weighted API dollars that make 100%, calibrated against the Claude app's usage
# screen: 5-hour on 26 Sep 2026 (readings of 20-44%), weekly on 8 Oct 2026 (76%).
# The screen shows whole percents, so readings under ~20% are too coarse to set
# these. Recheck with scratch/check_accuracy.py.
FIVE_HOUR_FULL = 195.0
WEEKLY_FULL = 1500.0

FIVE_HOURS = timedelta(hours=5)
WEEK = timedelta(days=7)
# A known weekly reset; the weekly limit resets at this time every 7 days.
WEEKLY_RESET = datetime(2026, 10, 3, 1, 0, tzinfo=timezone.utc)


def _model_key(model):
    # Longest prefix first, so claude-opus-5-5 isn't read as claude-opus-5.
    for key in sorted(PRICES, key=len, reverse=True):
        if model.startswith(key):
            return key
    return None


def weighted_cost(model, usage):
    """API-price cost of one reply in USD, times the model's plan weight."""
    key = _model_key(model)
    inp, out, read = PRICES[key] if key else UNKNOWN_MODEL_PRICE
    created = usage.get("cache_creation") or {}
    write_1h = created.get("ephemeral_1h_input_tokens") or 0
    write_5m = created.get("ephemeral_5m_input_tokens")
    if write_5m is None:
        write_5m = (usage.get("cache_creation_input_tokens") or 0) - write_1h
    cost = ((usage.get("input_tokens") or 0) * inp
            + (usage.get("output_tokens") or 0) * out
            + write_5m * inp * 1.25
            + write_1h * inp * 2
            + (usage.get("cache_read_input_tokens") or 0) * read) / 1_000_000
    if usage.get("speed") == "fast":
        cost *= 2
    return cost * PLAN_WEIGHTS.get(key, 1.0)


class TranscriptReader:
    """Keeps the replies and activity from recent transcripts, reading only new lines on each refresh."""

    def __init__(self, projects_dir=PROJECTS_DIR, days=8):
        self.projects_dir = Path(projects_dir)
        self.days = days
        self.offsets = {}
        self.costs = {}  # (message id, request id) -> (time, cost)
        self.activity = set()  # times of the requests that got a reply
        self.lines = {}  # line uuid -> (time, is a reply), to find what each reply answered

    def refresh(self, now=None):
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self.days)
        for path in self.projects_dir.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            offset = self.offsets.get(path, 0)
            if stat.st_mtime < cutoff.timestamp() or stat.st_size == offset:
                continue
            if stat.st_size < offset:
                offset = 0
            try:
                with open(path, "rb") as fh:
                    fh.seek(offset)
                    data = fh.read()
            except OSError:
                continue
            # A line still being written has no newline yet; it's read next time.
            end = data.rfind(b"\n") + 1
            for line in data[:end].splitlines():
                self._add(line)
            self.offsets[path] = offset + end
        self.costs = {k: v for k, v in self.costs.items() if v[0] >= cutoff}
        self.activity = {t for t in self.activity if t >= cutoff}
        self.lines = {k: v for k, v in self.lines.items() if v[0] >= cutoff}

    def _add(self, line):
        try:
            entry = json.loads(line)
            uuid, stamp = entry.get("uuid"), entry.get("timestamp")
            time = datetime.fromisoformat(stamp) if uuid and stamp else None
        except (ValueError, TypeError, AttributeError):
            return
        if time is None:
            return
        message = entry.get("message")
        if entry.get("type") != "assistant" or not isinstance(message, dict):
            self.lines[uuid] = (time, False)
            return
        self.lines[uuid] = (time, True)
        usage, model = message.get("usage"), message.get("model")
        if not usage or not model or model == "<synthetic>":
            return
        # A window starts with a request, which is sent when the line before the reply is
        # written. Prompts that never reach Anthropic (local commands) have no reply.
        # Replies arrive as one line per content block; only the first follows a non-reply.
        parent = self.lines.get(entry.get("parentUuid"))
        if parent is None or not parent[1]:
            self.activity.add(parent[0] if parent else time)
        # Each content-block line repeats the reply's usage.
        key = (message.get("id"), entry.get("requestId"))
        cost = weighted_cost(model, usage)
        if key not in self.costs or cost > self.costs[key][1]:
            self.costs[key] = (time, cost)


def five_hour_window(activity, now):
    """The 5-hour window running at `now` as (start, end), or None when there isn't one.

    A window starts at the first prompt or reply after the previous window ended,
    rounded down to 10 minutes; Anthropic's reset times line up that way.
    """
    window = None
    for time in sorted(t for t in activity if t <= now):
        if window is None or time >= window[1]:
            start = time.replace(minute=time.minute - time.minute % 10, second=0, microsecond=0)
            window = (start, start + FIVE_HOURS)
    return window if window and now < window[1] else None


def weekly_window(now):
    start = WEEKLY_RESET + math.floor((now - WEEKLY_RESET) / WEEK) * WEEK
    return start, start + WEEK


def read_official(path=OFFICIAL_FILE):
    """The official reading the usage-file mod last wrote, or None when there's none to use.

    Returns {"measured_at": datetime, "five_hour": (percent, reset) or None, "seven_day": ...}.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        measured_at = datetime.fromisoformat(data["measuredAt"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    # A time without a zone can't be compared with the transcripts' times.
    if measured_at.tzinfo is None:
        return None

    def window(key):
        try:
            reading = data[key]
            reset = datetime.fromisoformat(reading["resetsAt"])
            return (float(reading["percent"]), reset) if reset.tzinfo else None
        except (KeyError, TypeError, ValueError):
            return None

    return {"measured_at": measured_at, "five_hour": window("fiveHour"), "seven_day": window("sevenDay")}


def combine(costs, activity, now, official):
    """Return (5-hour %, 5-hour reset or None, weekly %, weekly reset, official reading time or None).

    Where the official reading's window is still running, its % is the base and only the use
    since the reading is estimated. Otherwise that window is the estimate alone, as before.
    """
    costs = list(costs)
    five, five_reset, week, week_reset = estimate(costs, activity, now)
    if official is None:
        return five, five_reset, week, week_reset, None
    measured_at = official["measured_at"]
    since = sum(cost for time, cost in costs if measured_at < time <= now)
    used = False
    if official["five_hour"] and official["five_hour"][1] > now:
        five, five_reset = official["five_hour"][0] + since / FIVE_HOUR_FULL * 100, official["five_hour"][1]
        used = True
    elif official["five_hour"]:
        # The official window has reset, so the next one starts with the first request after
        # that reset, even where older activity would put the estimate's own window elsewhere.
        window = five_hour_window({t for t in activity if t >= official["five_hour"][1]}, now)
        five = sum(cost for time, cost in costs if window and window[0] <= time <= now) / FIVE_HOUR_FULL * 100
        five_reset = window[1] if window else None
    if official["seven_day"] and official["seven_day"][1] > now:
        week, week_reset = official["seven_day"][0] + since / WEEKLY_FULL * 100, official["seven_day"][1]
        used = True
    return five, five_reset, week, week_reset, measured_at if used else None


def estimate(costs, activity, now):
    """Return (5-hour %, 5-hour reset or None, weekly %, weekly reset) at `now`.

    `costs` is an iterable of (time, weighted cost), as in TranscriptReader.costs.values().
    """
    costs = list(costs)

    def used(start):
        return sum(cost for time, cost in costs if start <= time <= now)

    five = five_hour_window(activity, now)
    week_start, week_end = weekly_window(now)
    five_pct = used(five[0]) / FIVE_HOUR_FULL * 100 if five else 0.0
    return five_pct, five[1] if five else None, used(week_start) / WEEKLY_FULL * 100, week_end
