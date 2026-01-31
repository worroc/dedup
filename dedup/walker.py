import os
from pathlib import Path

from . import logger

from .context import ctx
from .reader import File
from . import cache
from .misc import to_abs


class Walker:
    def directories(self, dir_name: str):
        for current_dir, dirs, files in os.walk(dir_name):
            if os.path.basename(current_dir).startswith("."):
                continue
            yield current_dir

    def build(self, dir_name: str):
        """wall through the FS and scan files
        return dict of all files
        """
        progress_file = None
        progress_data = set()
        if ctx.rerun:
            logger.info(f"using progress file {ctx.progress_filename}")
            try:
                with ctx.progress_filename.open(encoding="utf-8", mode="rt") as fi:
                    progress_data = set(
                        [str(Path(x.strip()).resolve()) for x in fi.readlines()]
                    )
            except FileNotFoundError:
                progress_data = set()
            progress_file = ctx.progress_filename.open(encoding="utf-8", mode="a")
        else:
            progress_file = ctx.progress_filename.open(encoding="utf-8", mode="w")

        try:
            counter = 0
            accomulator = {}
            directories = {}
            resolved_dir = Path(dir_name).resolve()
            logger.info(f"reading file system {resolved_dir}")
            for current_dir, dirs, files in os.walk(resolved_dir):
                # process single directory
                if os.path.basename(current_dir).startswith("."):
                    continue
                current_dir = str(Path(current_dir).resolve())
                old_cache = cache.load(current_dir)
                if old_cache and current_dir in progress_data:
                    directories[current_dir] = old_cache
                    accomulator.update(old_cache)
                    logger.warning(f"cached: {current_dir}")
                    continue
                logger.ok(f"mapping {current_dir}")
                new_cache = cache.new(current_dir)
                cache_changed = False
                exception = False
                for file in files:
                    if file == ctx.cache_filename:
                        continue
                    counter += 1

                    filename = to_abs(os.path.join(current_dir, file))

                    if filename in old_cache:
                        file_obj = File.from_cache(old_cache.get(filename))
                        cache_changed = cache_changed or not file_obj.hashed
                    else:
                        file_obj = File(filename, current_dir)
                        cache_changed = True
                    new_cache[filename] = file_obj

                    # only populate stat (hashing deferred to size-collision check)
                    try:
                        file_obj.ensure_stat()
                    except Exception:
                        logger.warning(f"unable to stat file {filename}")
                        exception = True
                        continue

                if cache_changed:
                    if not exception:
                        if progress_file:
                            progress_file.write(current_dir + "\n")
                            progress_file.flush()
                    new_cache.store()

                directories[current_dir] = new_cache
                accomulator.update(new_cache)
            return accomulator, directories
        finally:
            if progress_file:
                progress_file.close()
