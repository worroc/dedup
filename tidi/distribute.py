import click
import time
from pathlib import Path
from collections import defaultdict


@click.command("images")
@click.argument("path", type=click.Path(exists=True))
def distribute(path: str):
    dir_path = Path(path)
    assert dir_path.is_dir()

    place = defaultdict(set)

    for file in dir_path.glob("*"):
        if file.is_dir():
            continue
        tm = time.gmtime(file.stat().st_mtime)
        new_plce = dir_path / time.strftime("%Y-%m-%d", tm)
        place[new_plce].add(file)

    for new_place, files in place.items():
        new_place.mkdir(exist_ok=True)
        for file in files:
            target = new_place / file.name
            file.replace(target)
