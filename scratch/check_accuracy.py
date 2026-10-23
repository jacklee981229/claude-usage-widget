"""Compare the widget's estimate with the real numbers.

Real numbers come from the transcripts: get_usage results from Claude app sessions
(Claude's copy of the app's usage screen), and the moments a limit was hit (100%).
"""
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import usage_estimate as ue  # noqa: E402

LABELS = {"5-hour limit": "5-hour", "Weekly · all models": "weekly"}
# Transcripts are deleted after 30 days, so older real numbers can't be estimated any more.
OLDEST = datetime.now(timezone.utc) - timedelta(days=25)
LIMIT_TYPES = {"five_hour": "5-hour", "seven_day": "weekly"}


def real_numbers():
    """Yield (time, window, real %, real reset, source)."""
    calls, hits = set(), {}
    for path in ue.PROJECTS_DIR.rglob("*.jsonl"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "get_usage" not in line and "5-hour limit" not in line and "quotaLimits" not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                time = datetime.fromisoformat(entry["timestamp"]) if "timestamp" in entry else None
                limit = entry.get("quotaLimits") or {}
                if limit.get("status") == "rejected" and limit.get("rateLimitType") in LIMIT_TYPES:
                    key = (limit["rateLimitType"], limit.get("resetsAt"))
                    hits[key] = min(hits.get(key, time), time)
                content = (entry.get("message") or {}).get("content")
                for block in content if isinstance(content, list) else []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("name", "").endswith("__get_usage"):
                        calls.add(block["id"])
                    elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                        text = block.get("content")
                        if isinstance(text, list):
                            text = "".join(b.get("text", "") for b in text if isinstance(b, dict))
                        try:
                            windows = json.loads(text)["plan"]["windows"]
                        except (ValueError, KeyError, TypeError):
                            continue
                        for w in windows:
                            if w.get("label") in LABELS:
                                yield time, LABELS[w["label"]], w["percentUsed"], datetime.fromisoformat(w["resetsAt"]), "usage screen"
    for (kind, reset), time in hits.items():
        yield time, LIMIT_TYPES[kind], 100, datetime.fromtimestamp(reset, timezone.utc), "limit hit"


def local(time, pattern):
    return time.astimezone().strftime(pattern) if time else "-"


reader = ue.TranscriptReader(days=40)
reader.refresh()
costs = list(reader.costs.values())
fits = {"5-hour": [], "weekly": []}
print(f"{'when':<17} {'window':<7} {'real':>5} {'est':>5}  {'reset real':<10} {'reset est':<10} source")
for time, window, real, real_reset, source in sorted(real_numbers()):
    if time < OLDEST:
        continue
    five, five_reset, week, week_reset = ue.estimate(costs, reader.activity, time)
    est, est_reset = (five, five_reset) if window == "5-hour" else (week, week_reset)
    print(f"{local(time, '%Y-%m-%d %H:%M'):<17} {window:<7} {real:>4}% {est:>4.0f}%  "
          f"{local(real_reset, '%a %H:%M'):<10} {local(est_reset, '%a %H:%M'):<10} {source}")
    # Whole-percent rounding makes low readings too coarse to fit the factors.
    if source == "usage screen" and real >= 20:
        full = ue.FIVE_HOUR_FULL if window == "5-hour" else ue.WEEKLY_FULL
        fits[window].append(full * est / real)
for window, values in fits.items():
    if values:
        print(f"{window}: 100% fits best at {statistics.median(values):.0f} weighted API dollars "
              f"(set to {ue.FIVE_HOUR_FULL if window == '5-hour' else ue.WEEKLY_FULL:.0f})")
