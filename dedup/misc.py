import os
from pathlib import Path

import send2trash
from . import logger
from .context import ctx


class ReloadRuleException(BaseException): ...


def del_file(file_path: str):
    if not os.path.exists(file_path):
        return
    try:
        if not ctx.dry_run:
            if ctx.unlink:
                os.unlink(file_path)
            else:
                send2trash.send2trash(file_path)
    except Exception:
        logger.debug(f"unable to delete file {file_path}")


def to_abs(path: str):
    return str(Path(path).resolve())
