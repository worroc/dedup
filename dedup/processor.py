import os
import shutil
import stat
import pickle

from collections import defaultdict
from typing import Any, Dict, List, Tuple
from pathlib import Path

from .walker import Walker
from .misc import del_file
from . import cache
from . import colander
from .context import ctx
from . import logger


class Processor:
    def __init__(self, dirs):
        super().__init__()
        self.dirs = dirs

        self.press = colander.Press()

    def clear_cache(self):
        menu = """
What do you want to clear?
  1. Hash cache      - .dedup-meta.cpl files in scanned directories (speeds up re-scans)
  2. Session files   - checkpoint, final_redundant, pending_moves (current dedup session)
  3. Saved answers   - answers, newdirs (user decisions from previous runs)
  4. Rules           - rules, ignore, remove lists (appraiser patterns)
  5. All of the above
  q. Cancel
"""
        print(menu)
        answer = input("choice> ").strip().lower()

        if answer == "q":
            logger.info("cancelled")
            return

        choices = set(answer.replace(",", " ").split())
        if "5" in choices:
            choices = {"1", "2", "3", "4"}

        if "1" in choices:
            self._clear_hash_cache()
        if "2" in choices:
            self._clear_session_files()
        if "3" in choices:
            self._clear_saved_answers()
        if "4" in choices:
            self._clear_rules()

    def _clear_hash_cache(self):
        logger.info("clearing hash cache...")
        w = Walker()
        for d in self.dirs:
            for d in w.directories(d):
                cache.clear(d)
        logger.ok("hash cache cleared")

    def _clear_session_files(self):
        logger.info("clearing session files...")
        for f in [
            ctx.checkpoint_filename,
            ctx.final_redundant,
            ctx.pending_moves_filename,
            ctx.progress_filename,
        ]:
            if f.exists():
                f.unlink()
                logger.ok(f"removed {f}")

    def _clear_saved_answers(self):
        logger.info("clearing saved answers...")
        for f in [ctx.answers_filename, ctx.newdirs_filename]:
            if f.exists():
                f.unlink()
                logger.ok(f"removed {f}")

    def _clear_rules(self):
        logger.info("clearing rules...")
        for f in [
            ctx.appraiser_rules_filename,
            ctx.appraiser_ignore_filename,
            ctx.appraiser_remove_filename,
        ]:
            if f.exists():
                f.unlink()
                logger.ok(f"removed {f}")

    def calculus(self) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        # calculates a full tree and duplicates
        accoumulation = {}
        all_directories = {}
        w = Walker()

        for d in self.dirs:
            files, directories = w.build(d)
            accoumulation.update(files)
            all_directories.update(directories)

        for dir_cache in all_directories.values():
            if dir_cache:
                dir_cache.store()

        duplicates = self._duplicates(accoumulation)

        return accoumulation, duplicates

    def stats(self):
        # display all
        files, dups = self.calculus()
        for md5, files in dups.items():
            logger.info(f"{md5}")
            for filename in files:
                logger.info(f"\t{filename}")

    def dedup(self):
        if ctx.checkpoint_filename.exists() and ctx.rerun:
            with ctx.checkpoint_filename.open(mode="rb") as fi:
                dups = pickle.load(fi)
        else:
            _files, dups = self.calculus()
            if not dups:
                logger.info("no duplicates")
                return
            with ctx.checkpoint_filename.open(mode="wb") as fo:
                pickle.dump(dups, fo)

        if ctx.final_redundant.exists() and ctx.rerun:
            with ctx.final_redundant.open(mode="rb") as fi:
                files_to_delete = pickle.load(fi)
            if ctx.pending_moves_filename.exists():
                with ctx.pending_moves_filename.open(mode="rb") as fi:
                    pending_moves = pickle.load(fi)
            else:
                pending_moves = {}
        else:
            files_to_delete = self.press.squeeze_redundant(dups)
            pending_moves = self.press.get_pending_moves()
            with ctx.final_redundant.open(mode="wb") as fo:
                pickle.dump(files_to_delete, fo)
            with ctx.pending_moves_filename.open(mode="wb") as fo:
                pickle.dump(pending_moves, fo)

        logger.info(
            f"processing: {len(files_to_delete)} deletions, {len(pending_moves)} moves\n"
        )
        self._purge(files_to_delete, pending_moves, dups)

    def _purge(self, files_to_delete, pending_moves, dups):
        while True:
            answer = input(
                "do you want to remove {} files and move {} files? yes/no/list> ".format(
                    len(files_to_delete), len(pending_moves)
                )
            ).strip()
            if answer == "list":
                # show pending moves
                if pending_moves:
                    logger.info("=== MOVES ===")
                    for src, dst in pending_moves.items():
                        logger.ok(f"{src} -> {dst}")

                # let make reverse list and display that deleted and where to leave
                logger.info("=== DELETIONS ===")
                good_map = defaultdict(set)
                del_map = defaultdict(set)
                rev = {}
                for hash_id, files in dups.items():
                    for f in files:
                        rev[f] = hash_id

                for index, file_name in enumerate(files_to_delete):
                    hs = rev.get(file_name)
                    if hs:
                        del_map[hs].add(file_name)

                for hs, files in del_map.items():
                    good_map[hs] = set(dups[hs]) - files

                for hs, files in good_map.items():
                    logger.ok("\n".join(files))
                    for index, df in enumerate(del_map[hs]):
                        logger.error(f"\t{index:3}. {df}")
                continue
            elif answer == "no":
                logger.info("no changes.\n")
                break
            elif answer == "yes":
                # execute moves first
                for src, dst in pending_moves.items():
                    if not os.path.exists(src):
                        logger.warning(f"source not found, skipping: {src}")
                        continue
                    dst_dir = os.path.dirname(dst)
                    if not ctx.dry_run:
                        if not os.path.exists(dst_dir):
                            os.makedirs(dst_dir)
                        shutil.move(src, dst)
                        logger.ok(f"moved {src} -> {dst}")
                    else:
                        logger.info(f"dry-run: would move {src} -> {dst}")

                # execute deletions
                total = len(files_to_delete)
                for i, file_name in enumerate(files_to_delete):
                    if i % 100 == 0:
                        logger.debug(f"removed {i} files of {total}")
                    del_file(file_name)

                # remove empty directories (skip cache file)
                dirs = set()
                for file in files_to_delete:
                    dirs.add(Path(file).parts[:-1])

                dirs = sorted(list(dirs), key=lambda x: len(x), reverse=True)
                total = len(dirs)
                for i, d in enumerate(dirs):
                    directory = Path(*d)
                    logger.info(directory)
                    cache.clear(directory)
                    if os.path.exists(directory) and not os.listdir(directory):
                        logger.info("exists")
                        try:
                            os.rmdir(directory)
                        except PermissionError:
                            os.chmod(directory, stat.S_IWRITE)
                            os.rmdir(directory)
                break
            else:
                logger.info("unknown input\n")

    def _duplicates(self, files):
        from .reader import FileReader

        # pass 1: group by size
        by_size = defaultdict(list)
        for filename, file_obj in files.items():
            try:
                by_size[file_obj.size].append((filename, file_obj))
            except Exception as e:
                logger.warning(f"unable to get size for {filename}: {e}")

        # filter to size collisions only
        size_collisions = {sz: items for sz, items in by_size.items() if len(items) > 1}
        total_collisions = sum(len(items) for items in size_collisions.values())
        logger.info(
            f"size collisions: {total_collisions} files in {len(size_collisions)} groups"
        )

        # pass 2: hash only files with size collisions
        by_hash = defaultdict(list)
        for size, items in size_collisions.items():
            for filename, file_obj in items:
                try:
                    if not file_obj.hashed:
                        file_obj.ensure_hash()
                    by_hash[file_obj.hash].append(filename)
                except Exception as e:
                    logger.warning(f"unable to hash {filename}: {e}")

        # filter to hash collisions
        candidates = {h: fnames for h, fnames in by_hash.items() if len(fnames) > 1}

        # pass 3: verify large files with full hash
        verified = {}
        for quick_hash, filenames in candidates.items():
            has_large = any(
                os.path.getsize(f) > ctx.large_file_threshold
                for f in filenames
                if os.path.exists(f)
            )
            if not has_large:
                verified[quick_hash] = filenames
                continue

            # re-hash large files with full hash
            logger.info(f"verifying {len(filenames)} large files...")
            full_hashes = defaultdict(list)
            for f in filenames:
                if os.path.exists(f):
                    full_hash = FileReader.hash(f, full=True)
                    full_hashes[full_hash].append(f)

            for full_hash, verified_files in full_hashes.items():
                if len(verified_files) > 1:
                    verified[full_hash] = verified_files

        return verified
