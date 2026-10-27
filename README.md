# Claude usage widget

A small widget on your desktop that estimates how much of your Claude Max plan you've used: the 5-hour window (ring) and the weekly limit (bar).

- It starts from the official numbers when it has them: the `usage-file` mod (in `mod\`) runs inside the Claude app's Claude Code and writes your real 5-hour and weekly percentages to `%USERPROFILE%\.claude\usage-widget\usage.json` each time they move. The footer then reads `official 14:02 + est.`: the reading from 14:02, plus an estimate of what you've used since.
- The estimate comes from Claude Code's transcripts, which the editor extension and the Claude app both write as you work: each reply becomes a share of your limits. It never touches your Claude login. With no usable reading (none yet, or its windows have reset) the footer reads `estimate · 14:02` and the numbers are the estimate alone, usually within a few points of Claude's usage page but off by about a fifth in some windows.
- The official reading only changes when a Claude app session gets a reply. The editor extension's Claude Code may be too old to run mods (they need 2.1.287 or newer), so a day spent there runs on the estimate since the last reading.
- It sits just above the desktop, behind all your windows, and comes to the front while the desktop is active (Win+D, or a click on the desktop). It stays out of the taskbar and Alt+Tab, and updates every 30 seconds.
- A thin white mark on the ring and on the bar shows how far that window has run. Each is green while your use keeps up with the clock, orange when it runs more than ten points ahead, and pink from 85%.
- The text is in Hanken Grotesk, under the SIL Open Font License, from `fonts\`, like the to-do widget. Only the widget loads it, so nothing is installed in Windows; without the files it falls back to Segoe UI.

## Commands

Run these in PowerShell from this folder:

| Command | Does |
|---|---|
| `pythonw widget.py` | Start the widget, without a console window |
| `python scratch\check_accuracy.py` | Compare the estimate with Claude's real numbers |
| `python -m unittest discover -s tests` | Run the tests |
| `claude plugin test mod` | Run the mod's tests (with the Claude app's `claude.exe`, see CLAUDE.md) |

Right-click the widget to exit. Drag it to move it; it reopens where you left it (saved in `data\position.json`). Starting it while it's already running does nothing, so there's never more than one.

## The usage-file mod

It's installed at user scope from this folder (`.claude-plugin\marketplace.json` lists it) and loads in each new Claude app session. It has no display, no network, and writes only that one file. To install it again, for example on a fresh setup, run in a Claude Code prompt:

```
/plugin marketplace add C:\repos\Jack\claude-usage-widget
/plugin install usage-file@claude-usage-widget
```

`/plugin uninstall usage-file@claude-usage-widget` removes it; the widget then goes back to the estimate alone.

## Start with Windows

A shortcut named `Claude usage widget` in your Startup folder starts the widget when you sign in (press Win+R and type `shell:startup` to see it). Delete the shortcut to stop that. If you move this folder, run this from the new folder to make the shortcut again:

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$([Environment]::GetFolderPath('Startup'))\Claude usage widget.lnk"); $s.TargetPath = "$env:WINDIR\pyw.exe"; $s.Arguments = 'widget.py'; $s.WorkingDirectory = "$PWD"; $s.Save()
```

`pyw.exe` is the Python launcher without a console window, so the shortcut keeps working after a Python upgrade.

## If the numbers drift

`FIVE_HOUR_FULL` and `WEEKLY_FULL` at the top of `usage_estimate.py` turn token use into percentages; the comment above them says when each was set. To recheck, ask Claude in a Claude app session to check the usage widget: it reads your real usage and runs `scratch\check_accuracy.py`, which lists real against estimated numbers and prints the values that fit best. Readings under 20% are too coarse to set the factors.