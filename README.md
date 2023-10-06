This is a unobtrusive, scriptable reminder/habit/todo task-runner.

Probably easiest explained with some examples:

```bash
# remind me to listen to a new album once a week

# interfaces with my spreadsheet where I track my albums
# https://github.com/seanbreckenridge/albums
LISTENCOUNT="$(hpi query -r 1w my.nextalbums.history | jq 'length')" || exit 1

if [[ "${LISTENCOUNT}" == '0' ]]; then
    exit 2  # this has 'expired', exit code 2 means print the script name
else
    exit 0  # all good, I've listened to a new album recently
fi
```

[`flipflop`](https://sean.fish/d/flipflop.py?redirect) are toggeable todos for things that I need to do often. Think like: re-add a energy bar to my bag, refill medication.

I'll often run `flipflop` when I'm away from my computer using [termux](https://termux.dev/en/) on my phone. The data for that is then synced to my computer with [syncthing](https://syncthing.net/)

Instead of adding some reminder system inside `flipflop`, `reminder-sink` is the 'sink' for the data:

```bash
OUTPUT="$(flipflop.py status -fo json | jq 'keys[]' -r)"

if [[ -n "$OUTPUT" ]]; then
	echo "$OUTPUT"
	exit 3  # this has 'expired', exit code 3 prints the output of this script
fi
exit 0  # no output, nothing to do from flipflop
```

So, if I was to run `reminder-sink` and all of these had expired, I'd get something like:

```bash
$ reminder-sink run
listen_to_album   # from the name of the script
refill_medication  # these 2 lines were the output of 'flipflop.py status'
add_energy_bar
```

This does not actually have any way to setup/remind you for specific habits/tasks,
it provides more of a set of rules which make for an unobtrusive reminder/habit tracker

Instead of reminding me once a day to do something, this uses local data (or an API request
if you want -- its just a script, you can do whatever you want!) to determine if I've done
it within the timeframe

I really dislike habit building/reminder apps that interrupt my workflow. When I get the
notification to remind me to do something, it feels like I _have to_ do it at that moment,
else I'll forget or delay it, which is totally antithetical to actually building a habit

But, if there's no reminder, I often forget to do things.

Instead, this displays the number of tasks which have expired in my menu bar. So, its
still visible to me and I'll glance whenever I have a free minute, but I don't
get interrupted or feel like I have to 'snooze'/delay the habit.

I also don't feel too horrible if there's a number there for a couple hours, I get
around to the task eventually

I generally track my habits with my `Self` type using [`ttally`](https://github.com/seanbreckenridge/ttally),
and use [`i3blocks`](https://github.com/vivien/i3blocks) for my status bar. The block this runs for
`reminder-sink` looks like this:

![image](https://github.com/seanbreckenridge/reminder-sink/assets/7804791/0bc9706d-419c-41fe-91dc-217893ba2475)

```bash
#!/usr/bin/env bash

# if I left-click the icon, send a notification with what's expired
case "${BLOCK_BUTTON}" in
1)
    notify-send "$(reminder-sink)"
    ;;
esac

reminder-sink run | wc -l
```

You could of course script together a little cron job that _does_ actually remind you once an hour if you have any expired jobs:

```bash
OUT="$(reminder-sink run)"
if [[ -n "${OUT}" ]]; then
    notify-send "${OUT}"
fi
```

Or just run `reminder-sink run` when you start up a new terminal or something, this is very flexible

You can see some of my other reminder-sink jobs [in my dotfiles](https://github.com/seanbreckenridge/dotfiles/tree/master/.local/scripts/reminder-sink), but I use this for stuff like:

- reminding me to log my weight at least once a week
- making sure I drink enough water (using [`ttally`](https://github.com/seanbreckenridge/ttally))
- listen to album once a week (by using my [spreadsheet](https://sean.fish/s/albums))
- tracking physical activity
- remind me to re-fill on medication when it runs out
- watch something on my movie/tv show backlog once every couple days (this gets tracked automatically by my [`mpv-history-daemon`](https://github.com/seanbreckenridge/mpv-history-daemon))

## Usage:

```
Usage: reminder-sink [OPTIONS] COMMAND [ARGS]...

  reminders-sink is a script that takes other scripts as input and runs them
  in parallel. The exit code of each script it runs determines what reminder-
  sink does:

  0: I've done this task recently, no need to warn
  2: I haven't done this task recently, print the script name
  3: I haven't done this task recently, print the output of the script
  Anything else: Fatal error

  You can set the REMINDER_SINK_PATH environment variable to a colon-delimited
  list of directories that contain reminder-sink jobs. For example, in your
  shell profile, set:

  export REMINDER_SINK_PATH="${HOME}/.local/share/reminder-sink:${HOME}/Documents/reminder-sink"

  This scans the directories for executables and runs them in parallel. A
  script is considered enabled if it is executable or if the file name ends
  with '.enabled'.

Options:
  -d, --debug  print debug information  [env var: REMINDER_SINK_DEBUG]
  -h, --help   Show this message and exit.

Commands:
  list  list all scripts
  run   run all scripts in parallel
  test  test a script
```

This uses the shebang of the script (e.g. `#!/usr/bin/env bash` or `#!/usr/bin/python3`) to determine
what to run the file with. If it can't detect properly, it uses `bash` (you can change that like `REMINDER_SINK_DEFAULT_INTERPRETER=python`)

## Example

```
[ ~ ] $ reminder-sink list
Script(path=PosixPath('/home/sean/data/reminder-sink/self_type_common.py'), enabled=False)
Script(path=PosixPath('/home/sean/data/reminder-sink/physical_activity.enabled'), enabled=True)
Script(path=PosixPath('/home/sean/data/reminder-sink/mal_sources'), enabled=False)
Script(path=PosixPath('/home/sean/.local/scripts/reminder-sink/flipflop'), enabled=True)
Script(path=PosixPath('/home/sean/.local/scripts/reminder-sink/weight'), enabled=True)
Script(path=PosixPath('/home/sean/.local/scripts/reminder-sink/listen_to_album'), enabled=True)
Script(path=PosixPath('/home/sean/.local/scripts/reminder-sink/food'), enabled=True)
Script(path=PosixPath('/home/sean/.local/scripts/reminder-sink/water'), enabled=True)
```

This runs the scripts in parallel, with the number of threads equal to the number of cores you have available:

```
2023-10-06 00:54:28,197 DEBUG - reminder-sink: Running scripts with 16 threads
2023-10-06 00:54:28,197 DEBUG - reminder-sink: Searching /home/sean/data/reminder-sink
2023-10-06 00:54:28,197 DEBUG - self_type_common: not enabled
2023-10-06 00:54:28,197 DEBUG - physical_activity: Starting '/usr/bin/env bash /home/sean/data/reminder-sink/physical_activity.enabled'
2023-10-06 00:54:28,199 DEBUG - mal_sources: Starting '/usr/bin/env bash /home/sean/data/reminder-sink/mal_sources'
2023-10-06 00:54:28,199 DEBUG - reminder-sink: finished searching /home/sean/data/reminder-sink
2023-10-06 00:54:28,199 DEBUG - reminder-sink: Searching /home/sean/.local/scripts/reminder-sink
2023-10-06 00:54:28,200 DEBUG - flipflop: Starting '/usr/bin/env bash /home/sean/.local/scripts/reminder-sink/flipflop'
2023-10-06 00:54:28,201 DEBUG - weight: Starting '/usr/bin/env bash /home/sean/.local/scripts/reminder-sink/weight'
2023-10-06 00:54:28,203 DEBUG - listen_to_album: Starting '/usr/bin/env bash /home/sean/.local/scripts/reminder-sink/listen_to_album'
2023-10-06 00:54:28,203 DEBUG - food: Starting '/usr/bin/env bash /home/sean/.local/scripts/reminder-sink/food'
2023-10-06 00:54:28,204 DEBUG - reminder-sink: finished searching /home/sean/.local/scripts/reminder-sink
2023-10-06 00:54:28,204 DEBUG - water: Starting '/usr/bin/env bash /home/sean/.local/scripts/reminder-sink/water'
2023-10-06 00:54:28,218 DEBUG - mal_sources: (took 0.01922) with exit code 0 and output ''
2023-10-06 00:54:28,306 DEBUG - flipflop: (took 0.10657) with exit code 0 and output ''
2023-10-06 00:54:28,319 DEBUG - physical_activity: (took 0.12172) with exit code 0 and output ''
2023-10-06 00:54:28,321 DEBUG - weight: (took 0.12033) with exit code 0 and output ''
2023-10-06 00:54:28,346 DEBUG - food: (took 0.14306) with exit code 0 and output ''
2023-10-06 00:54:28,357 DEBUG - water: (took 0.15303) with exit code 0 and output ''
2023-10-06 00:54:28,436 DEBUG - listen_to_album: (took 0.23399) with exit code 0 and output ''
```

## Installation

Requires `python3.10+`

To install with pip, run:

```
pip install reminder-sink
```

## Usage

```
reminder-sink --help
```

### Tests

```bash
git clone 'https://github.com/seanbreckenridge/reminder-sink'
cd ./reminder-sink
pip install '.[testing]'
flake8 ./reminder-sink
mypy ./reminder-sink
```
