"""
python main.py -s --dry-run -d /media/ilya/500GB/pictures/ dedup
"""

import logging
import click

from dedup import processor
from dedup.context import ctx


@click.group()
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False, help="dry run")
@click.option("--dirs", "-d", required=True, multiple=True, help="directories")
@click.option("-c", is_flag=True, default=False, help="continue previouse run")
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
    FORMAT = "'%(asctime)s %(levelname)s [%(filename)s:%(lineno)s - %(funcName)10s()]  %(message)s"
    logging.basicConfig(format=FORMAT, datefmt="%m/%d/%Y %I:%M:%S %p", level=loglevel)


@cli.command()
def stats():
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
    ctx.unlink = unlink
    processor.Processor(ctx.dirs).dedup()


@cli.command("clear_cache")
@click.option(
    "--unlink", "-u", is_flag=True, default=False, help="Unlink or move to trash"
)
def clear_cache(unlink):
    ctx.unlink = unlink
    processor.Processor(ctx.dirs).clear_cache()


if __name__ == "__main__":
    cli()
