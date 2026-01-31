"""
dedup -d /path/to/directory stats
dedup -d /path/to/directory dedup
dedup tidy /path/to/directory
"""

import logging
import time
from collections import defaultdict
from pathlib import Path

import click

from dedup import processor
from dedup.context import ctx


@click.group()
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False, help="dry run")
@click.option("--dirs", "-d", multiple=True, help="directories")
@click.option("-c", is_flag=True, default=False, help="continue previous run")
def cli(verbose, dry_run, dirs, c):
    click.echo("Verbose mode is %s" % ("on" if verbose else "off"))
    ctx.verbose = verbose
    ctx.dry_run = dry_run
    ctx.rerun = c
    ctx.dirs = dirs

    if verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO
    fmt = "'%(asctime)s %(levelname)s [%(filename)s:%(lineno)s - %(funcName)10s()]  %(message)s"
    logging.basicConfig(format=fmt, datefmt="%m/%d/%Y %I:%M:%S %p", level=loglevel)


def _require_dirs():
    """Validate that -d option was provided."""
    if not ctx.dirs:
        raise click.UsageError("Missing option '-d' / '--dirs'.")


@cli.command()
def stats():
    _require_dirs()
    processor.Processor(ctx.dirs).stats()


@cli.command()
@click.option(
    "--unlink",
    "-u",
    is_flag=True,
    default=False,
    help="dont move to trash, delete files",
)
def dedup(unlink):
    _require_dirs()
    ctx.unlink = unlink
    processor.Processor(ctx.dirs).dedup()


@cli.command("clear_cache")
@click.option(
    "--unlink", "-u", is_flag=True, default=False, help="Unlink or move to trash"
)
def clear_cache(unlink):
    _require_dirs()
    ctx.unlink = unlink
    processor.Processor(ctx.dirs).clear_cache()


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def tidy(path: str):
    """Organize files into date-based directories (YYYY-MM-DD)."""
    dir_path = Path(path)
    if not dir_path.is_dir():
        raise click.UsageError(f"Path must be a directory: {path}")

    place = defaultdict(set)

    for file in dir_path.glob("*"):
        if file.is_dir():
            continue
        tm = time.localtime(file.stat().st_mtime)
        new_place = dir_path / time.strftime("%Y-%m-%d", tm)
        place[new_place].add(file)

    for new_place, files in place.items():
        for file in files:
            target = new_place / file.name
            click.echo(f"{file} -> {target}")
            if not ctx.dry_run:
                new_place.mkdir(exist_ok=True)
                file.replace(target)


if __name__ == "__main__":
    cli()
