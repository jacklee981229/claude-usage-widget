<div align="center">

# Claude usage widget

A small Windows desktop widget for your Claude Max plan:<br>the 5-hour window as a ring, the weekly limit as a bar.

<img src=".github/readme/on-pace.png" width="300" alt="The widget: 34% of the 5-hour window and 28% of the week used, both on pace, in green">

</div>

## The colours mean something

The thin white mark shows how far each window has run. Green means your use keeps up with it.

<table>
  <tr>
    <td align="center" width="25%"><img src=".github/readme/ahead.png" alt="63% of the 5-hour window used, ahead of time, in orange"></td>
    <td align="center" width="25%"><img src=".github/readme/nearly-full.png" alt="91% of the 5-hour window and 87% of the week used, nearly full, in pink"></td>
    <td align="center" width="25%"><img src=".github/readme/estimate.png" alt="An estimate only: the 5-hour window on pace, the week ahead of time"></td>
    <td align="center" width="25%"><img src=".github/readme/not-started.png" alt="No 5-hour window running yet: an empty ring at 0%"></td>
  </tr>
  <tr>
    <td align="center"><b>Ahead of time</b><br>Orange: more than ten points ahead of the clock.</td>
    <td align="center"><b>Nearly full</b><br>Pink from 85%.</td>
    <td align="center"><b>Estimate only</b><br>No official reading yet, so it's all estimated.</td>
    <td align="center"><b>Not started</b><br>The next 5-hour window starts with your next request.</td>
  </tr>
</table>

## Features

- **Official numbers first.** A small Claude Code mod writes your real 5-hour and weekly percentages; the widget adds an estimate of what you've used since.
- **Works without the mod.** It estimates from Claude Code's transcripts, and never touches your Claude login.
- **Stays out of the way.** It sits on the desktop behind your windows, comes forward on Win+D, and stays out of the taskbar and Alt+Tab.
- **Nothing to install.** Python and tkinter only, no packages. Updates every 30 seconds.

## Quick start

In PowerShell, from this folder:

```powershell
pythonw widget.py
```

Drag it to move it; right-click it to exit.

For the official numbers, install the `usage-file` mod from a Claude Code prompt in the Claude app:

```
/plugin marketplace add C:\path\to\claude-usage-widget
/plugin install usage-file@claude-usage-widget
```

To start the widget when you sign in to Windows:

```powershell
python startup.py
```

<details>
<summary><b>How the numbers work</b></summary>

- The mod (in `mod\`) writes your real percentages to `%USERPROFILE%\.claude\usage-widget\usage.json` each time they move. It has no display, no network, and writes only that file. The footer then reads `official 14:02 + est.`: the reading from 14:02, plus an estimate of what you've used since.
- The estimate turns each reply in Claude Code's transcripts (written by both the editor extension and the Claude app) into a share of your limits. With no usable reading, the footer reads `estimate · 14:02`. It's usually within a few points of Claude's usage page, but off by about a fifth in some windows.
- The official reading only changes when a Claude app session gets a reply. Mods need Claude Code 2.1.287 or newer, which an editor extension may not have, so a day spent there runs on the estimate.
- `/plugin uninstall usage-file@claude-usage-widget` removes the mod; the widget then goes back to the estimate alone.

**If the numbers drift:** `FIVE_HOUR_FULL` and `WEEKLY_FULL` at the top of `usage_estimate.py` turn token use into percentages. Ask Claude in a Claude app session to check the usage widget: it reads your real usage and runs `scratch\check_accuracy.py`, which prints the values that fit best. Readings under 20% are too coarse to set them.

</details>

<details>
<summary><b>Start with Windows</b></summary>

`python startup.py` puts a shortcut named `Claude usage widget` in your Startup folder (Win+R, `shell:startup`). Delete it to stop.

The shortcut runs `Claude Usage.exe`, a renamed copy of Python's `pythonw.exe`, so Task Manager lists the widget as "Claude Usage". It still runs `widget.py` from this folder, so a code change needs only a restart. Reinstalling Python or moving this folder breaks it: exit the widget and run `python startup.py` again.

Only one copy runs at a time. It reopens where you left it (saved in `data\position.json`).

</details>

<details>
<summary><b>Development</b></summary>

| Command | Does |
|---|---|
| `python -m unittest discover -s tests` | Run the tests |
| `python scratch\check_accuracy.py` | Compare the estimate with Claude's real numbers |
| `claude plugin test mod` | Run the mod's tests (with the Claude app's `claude.exe`, see CLAUDE.md) |

The text is in Hanken Grotesk (SIL Open Font License), loaded from `fonts\` for the widget only; without it, Segoe UI.

</details>
