# CLAUDE.md

Desktop widget for Claude plan usage (Python + tkinter, no packages) plus `usage-file`, a Claude Code mod in `mod/` that writes the official percentages for it. The README covers what it does and its commands.

## Where to look

- `usage_estimate.py`: the transcript estimate, `read_official` (the mod's file) and `combine` (official reading + estimate since).
- `widget.py`: the window and its drawing, and the alert chime (`check_alerts`; what was raised is in `data/alerts.json`). The alert is a sound only: Jack turned down the on-screen alert card (it made him anxious), so don't bring one back.
- `usage_estimate.forecast`: when each window fills at the recent pace; it drives the "Full in" word and the alerts.
- `mod/hooks/register.ts`: the mod; `mod/tests/` its tests.
- `scratch/check_accuracy.py`: recheck the calibration factors.
- `scratch/shoot.py`: the widget in set states with test data. After a change to the look, rerun it for the README's pictures (`.github/readme/`) and, with `hold`, for the showcase video's clips (`usage`, `usage-ahead`).

## Theme (W1, shared with the to-do widget)

- Ground: near-black `#0b0e15` with a soft indigo light falling from the top (`light_at`); the ring and bar are painted on that light.
- Colour logic: colours mean something. Green keeps up with the clock, orange runs more than ten points ahead, pink from 85%; a thin white mark shows how far the window has run. No colour of the day.
- Type: Hanken Grotesk; the percentage big and bold, the pace word small and in its colour.
- Shapes: one round-capped ring for the 5-hour window, a round-ended bar for the week, both painted pixel by pixel; Windows 11 rounded corners.
- Elements: A (dark ground with light), B (colours that mean something), E (round data).
- Looks we don't use: two rings stacked (the week goes in the bar).

## Rules and traps

- There's no `claude` on PATH. Run plugin commands with the Claude app's own binary, at `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude-code\<version>\<hash>\claude.exe` (find the current one among the running `claude.exe` processes): `plugin validate mod`, `plugin test mod`.
- `plugin list` shows the installed mod is read from `mod/` itself; if a change doesn't show in a new session, run `plugin marketplace update claude-usage-widget`. The mod API normalizes paths, so a test sees `C:\Users\...\.claude\...`, not the `/` the mod wrote.
- Mods need Claude Code 2.1.287+. The Claude Code in an editor extension can be older, so only Claude app sessions are sure to write the file.
- TypeScript isn't installed here, so `tsc` can't run; `plugin validate` and `plugin test` are the mod's checks.
- Jack's own widget runs from Startup as `Claude Usage.exe` (made by `startup.py`), with a one-copy mutex. To screenshot a change, use `scratch/shoot.py`, which skips the mutex; never stop his.
