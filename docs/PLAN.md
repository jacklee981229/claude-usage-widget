# Plan

A small desktop widget that shows how much of my Claude Max plan I've used, with weekly history later.

## Decisions (26–27 Sep 2026)

- **The numbers are estimates from Claude Code's transcripts** (`~/.claude/projects`), which the editor extension and the Claude app both write as I work. No login or token handling.
  - Why: exact live numbers need either Claude Code's saved login outside Claude Code (a grey area with Anthropic's terms, and a usage-monitor app has been linked to an account suspension) or the status line, which only the terminal CLI runs. Neither the editor extension's Claude panel nor the Claude app ran it when tested on 26 Sep. Claude Code mods (2.1.287+) later gave a third way; the widget now starts from their official reading (README).
  - Each reply is weighted by its API price and a per-model plan weight, then turned into % by two factors calibrated against the Claude app's usage screen.
  - Claude chats outside Claude Code aren't counted.
- Percentages only; exact token counts aren't needed. No Fable number.
- Widget pinned to the desktop, behind all windows.
- Personal vs work split shown as a share of tokens.
- Python 3.14 + tkinter + SQLite, all built in. No packages.

## Accuracy

- The 5-hour factor was set from the usage screen on 26 Sep (20/31/40%, Opus 5.5); the next reading, 44%, was estimated at 44%.
- The weekly factor was first set from readings of 7–10%, which are too coarse in whole percents: on 8 Oct it read 85% at a real 76%. It's now set from that 76% reading.
- The 5-hour reset time is off when Claude is used outside this laptop (claude.ai, phone, PC): on 8 Oct the window started at 08:00 with no laptop activity until 10:01.
- The four September limit hits (Opus 5, really 100%) read 79%, 96%, 96% and 123%: expect about ±20% from one window to another.
- Opus 5 counts about 1.85× as much as Opus 5.5 per API dollar, or the limit was raised after 9 Sep; the data can't tell these apart.
- `scratch/check_accuracy.py` rechecks this. New real readings come from get_usage calls in Claude app sessions.

## Tasks

### 1. Live widget (built 27 Sep)

- `usage_estimate.py` reads new transcript lines every 30 seconds and rebuilds the 5-hour window (it starts at the first request after the previous one ended, rounded down to 10 minutes) and the weekly window (resets Saturday 09:00).
- `widget.py`: a normal window kept just above the desktop, under every app window, and moved to the top while the desktop is the active window (Win+D). Putting it inside the desktop window itself draws nothing on Windows 11 24H2+ (tried 27 Sep, plain and layered). Donut for the 5-hour %, bar for the weekly %, reset times, "estimate · HH:MM". Drag to move (position remembered), right-click → Exit, one copy at a time.

Acceptance: unit tests pass; the estimate is within a few points of the usage screen; the widget stays behind windows, shows on Win+D, and stays out of the taskbar and Alt+Tab.

Tasks 2 and 4 are still to be discussed, including their order.

### 2. Notifications

- When the 5-hour window resets and a new session is available.
- When usage reaches 50%, 80% and 90%.
- Open: 5-hour, weekly or both for the thresholds; Windows notification or a pop-up by the widget.

### 3. Start with Windows (built 30 Sep)

- A shortcut named `Claude usage widget` in the Startup folder runs `pyw.exe widget.py` from this folder, the same way the to-do widget starts. There's no `--install` flag as first planned; the README has the one-line command to recreate the shortcut, and deleting it stops the auto-start.
- Fixed along the way: with the to-do widget also running, the two swapped places twice a second, since each kept pushing itself directly onto the desktop. The usage widget now moves only when an app window is beneath it.

Acceptance: after signing in, the widget is on the desktop without starting it by hand.

### 4. Lighter

Measured on 27 Sep: the running widget uses 44 MB of RAM (29 MB its own) and 0.014% CPU. The breakdown:

- Python itself: 16 MB.
- tkinter window: +13 MB.
- Transcript data: +25 MB right after loading; 6 MB of that is data kept for 8 days.
- For a moment at startup the widget peaks at about 170 MB, because it reads whole transcript files at once.

Options, from small to big:

- Read the transcripts in small pieces instead of whole files: the startup peak drops from ~170 MB to ~40 MB.
- Keep less: match replies to requests using only the last line of each transcript, and store times as plain numbers. Saves a few MB all the time.
- Drop tkinter and draw with Windows' own drawing calls: about 13 MB less, but more code.
- Rewrite as a compiled program: a few MB in total, but it needs new tools and is effectively a new project.

Acceptance: measured before and after with the same one-minute check.

### 5. Weekly history

- One bar per week: estimated % of the weekly limit, from the transcripts.
- Weekly totals are saved, since transcripts older than 30 days are deleted. They reach back to 26 Aug and lose the oldest day each day, so building this soon keeps the most weeks.

Acceptance: unit tests on weeks built from fake transcript lines; the history view shows real weeks.

### 6. Personal vs work

- Share of tokens per week: under `C:\repos\Jack` = personal, other `C:\repos` folders = work, the rest = other. Reads only token counts and folders, never conversation content.

Acceptance: unit tests for sorting folders (paths appear as both `C:\` and `c:\`) and for totals; a separate script cross-checks the totals.

## Later

- Since 23 Oct 2026 the usage-file mod writes the exact numbers (see README). The readings in `%USERPROFILE%\.claude\usage-widget\usage.json` could recalibrate the factors automatically; only the latest reading is kept so far.
