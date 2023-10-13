from __future__ import annotations
import sys
import os
import time
import subprocess
import shlex
import logging
from pathlib import Path
from typing import TextIO, Iterable, NamedTuple, Optional
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

import click

USAGE = """\
reminders-sink is a script that takes other scripts as input
and runs them in parallel. The exit code of each script it runs determines what
reminder-sink does:

\b
0: I've done this task recently, no need to warn
2: I haven't done this task recently, print the script name
3: I haven't done this task recently, print the output of the script
Anything else: Fatal error

You can set the REMINDER_SINK_PATH environment variable to a colon-delimited
list of directories that contain reminder-sink jobs. For example, in your shell
profile, set:

\b
export REMINDER_SINK_PATH="${HOME}/.local/share/reminder-sink:${HOME}/Documents/reminder-sink"

This scans the directories for executables and runs them in parallel. A script is
considered enabled if it is executable or if the file name ends with '.enabled'.
"""


INTERPRETER = os.environ.get("REMINDER_SINK_DEFAULT_INTERPRETER", "bash")


def is_executable(path: str) -> bool:
    return os.access(path, os.X_OK)


Result = tuple[str, int, str]
IGNORE_FILES = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".stignore"}


class Script(NamedTuple):
    path: Path
    enabled: bool

    @property
    def name(self) -> str:
        return self.path.stem

    def detect_shebang(self) -> Optional[str]:
        with open(self.path) as f:
            first_line = f.readline()
        if first_line.startswith("#!"):
            interp = first_line[2:].strip()
            # remove /usr/bin/env, its looked up in PATH anyways
            if interp.startswith("/usr/bin/env "):
                interp = interp[len("/usr/bin/env ") :]
            return interp
        return None

    def run(self) -> Result:
        name = self.name
        start = time.perf_counter()
        interp = self.detect_shebang() or INTERPRETER
        args = [*shlex.split(interp), str(self.path)]
        logging.debug(f"{name}: Starting '{' '.join(args)}'")
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        exitcode = proc.wait()

        output = proc.stdout.read() if proc.stdout else ""

        assert proc.stderr is not None, "stderr should be a pipe"
        for line in proc.stderr:
            logging.debug(f"{name}: {line.rstrip()}")

        logging.debug(
            f"{name}: (took {round(time.perf_counter() - start, 5)}) with exit code {exitcode} and output {repr(output.strip())}"
        )
        return name, exitcode, output


def find_execs() -> Iterable[Script]:
    dirs = os.environ.get("REMINDER_SINK_PATH")
    if not dirs:
        click.echo(
            "The REMINDER_SINK_PATH environment variable is not set. "
            "It should contain a colon-delimited list of directories "
            "that contain reminder-sink jobs. "
            "For example, in your shell profile, set:\n"
            'export REMINDER_SINK_PATH="${HOME}/.local/share/reminder-sink:${HOME}/data/reminder-sink"'
        )
        return
    for d in dirs.split(":"):
        if not d.strip():
            continue
        logging.debug(f"reminder-sink: Searching {d}")
        if not os.path.isdir(d):
            click.echo(f"Error: {d} is not a directory", err=True)
            continue
        for file in os.listdir(d):
            if os.path.basename(file) in IGNORE_FILES:
                continue
            abspath = os.path.abspath(os.path.join(d, file))
            enabled = is_executable(abspath) or file.endswith(".enabled")
            yield Script(path=Path(abspath), enabled=enabled)

        logging.debug(f"reminder-sink: finished searching {d}")


def run_parallel_scripts(
    executables: Iterable[Script],
    cpu_count: int,
) -> Iterable[Future[Result]]:
    logging.debug(f"reminder-sink: Running scripts with {cpu_count} threads")
    with ThreadPoolExecutor(max_workers=cpu_count) as executor:
        for script in executables:
            if not script.enabled:
                logging.debug(f"{script.name}: not enabled")
                continue
            yield executor.submit(script.run)


def print_result(res: Result, out: TextIO) -> None:
    name, exitcode, output = res
    match exitcode:
        case 0:
            pass
        case 2:
            out.write(name + "\n")
        case 3:
            out.write(output.rstrip("\n") + "\n")
        case _:
            logging.error(
                f"{name}: exited with non-(0,2,3) exit code. Pass --debug or set REMINDER_SINK_DEBUG=1 to see output"
            )


def write_results(futures: Iterable[Future[Result]], out: TextIO) -> None:
    for future in as_completed(futures):
        print_result(future.result(), out)


FORMAT = "%(asctime)s %(levelname)s - %(message)s"


@click.group(
    help=USAGE,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="See https://github.com/seanbreckenridge/reminder-sink for more information",
)
@click.option(
    "-d",
    "--debug",
    envvar="REMINDER_SINK_DEBUG",
    show_default=True,
    show_envvar=True,
    is_flag=True,
    help="print debug information",
)
def main(debug: bool) -> None:
    if debug:
        logging.basicConfig(level=logging.DEBUG, format=FORMAT)
    else:
        logging.basicConfig(level=logging.INFO, format=FORMAT)


@main.command(short_help="list all scripts", name="list")
def _list() -> None:
    click.echo("\n".join([str(s) for s in find_execs()]))


@main.command(short_help="test a script", name="test")
@click.argument("SCRIPT", type=click.Path(exists=True, dir_okay=False))
def _test(script: str) -> None:
    click.echo(f"Testing {script}", err=True)
    logging.basicConfig(level=logging.DEBUG, format=FORMAT)
    name, exitcode, output = Script(path=Path(script), enabled=True).run()
    click.echo(f"Finished {name} with exit code {exitcode} and output {repr(output)}")
    exit(exitcode)


@main.command(short_help="run all scripts in parallel")
@click.option(
    "-c",
    "--cpu-count",
    show_default=True,
    type=int,
    help="number of threads to use",
    default=os.cpu_count(),
)
def run(cpu_count: int) -> None:
    """
    Run all scripts in parallel, print the names of the scripts which
    have expired
    """
    executables = find_execs()

    write_results(run_parallel_scripts(executables, cpu_count=cpu_count), sys.stdout)
    sys.stdout.flush()


if __name__ == "__main__":
    main(prog_name="reminder-sink")
