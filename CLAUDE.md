# CLAUDE.md

Desktop widget for Claude plan usage (Python + tkinter, no packages) plus `usage-file`, a Claude Code mod in `mod/` that writes the official percentages for it. The README covers what it does and its commands.

## Where to look

- `usage_estimate.py`: the transcript estimate, `read_official` (the mod's file) and `combine` (official reading + estimate since).
- `widget.py`: the window and its drawing.
- `mod/hooks/register.ts`: the mod; `mod/tests/` its tests.
- `scratch/check_accuracy.py`: recheck the calibration factors.

## Rules and traps

- There's no `claude` on PATH. Run plugin commands with the Claude app's own binary, at `%LOCALAPPDATA%\Claude-Data\claude_pzs8sxrjxfjjc\claude-code\<version>\<hash>\claude.exe` (find the current one among the running `claude.exe` processes): `plugin validate mod`, `plugin test mod`.
- `plugin list` shows the installed mod is read from `mod/` itself; if a change doesn't show in a new session, run `plugin marketplace update claude-usage-widget`. The mod API normalizes paths, so a test sees `C:\Users\...\.claude\...`, not the `/` the mod wrote.
- Mods need Claude Code 2.1.287+. The Claude Code in an editor extension can be older, so only Claude app sessions are sure to write the file.
- TypeScript isn't installed here, so `tsc` can't run; `plugin validate` and `plugin test` are the mod's checks.
- Jack's own widget runs from Startup with a one-copy mutex. To screenshot a change, run a separate copy that skips the mutex; never stop his.
