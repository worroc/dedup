import os
import time
from typing import Dict, List, Optional, Tuple

from . import appraiser
from .misc import ReloadRuleException

from . import logger
from .context import ctx

FileHash = str
FilePath = str


class Press:
    def __init__(self):
        self.appraiser = appraiser.Appraiser()
        self._newdirs = {}  # source_dir -> set of suggested new_dirs
        self._auto_newdirs = set()  # activated dirs for auto-move
        self._pending_moves = {}  # source_path -> dest_path
        self._load_newdirs()

    def get_pending_moves(self):
        return self._pending_moves

    def _load_newdirs(self):
        if ctx.rerun and os.path.exists(ctx.newdirs_filename):
            with ctx.newdirs_filename.open(encoding="utf-8", mode="rt") as fi:
                for line in fi.readlines():
                    line = line.strip()
                    if not line:
                        continue
                    source_dir, new_dir = line.split(":", 1)
                    if source_dir not in self._newdirs:
                        self._newdirs[source_dir] = set()
                    self._newdirs[source_dir].add(new_dir)
            logger.debug(f"loaded {len(self._newdirs)} newdir mappings")

    def _save_newdir(self, source_dirs: List[str], new_dir: str):
        with ctx.newdirs_filename.open(encoding="utf-8", mode="a") as fo:
            for source_dir in source_dirs:
                if source_dir not in self._newdirs:
                    self._newdirs[source_dir] = set()
                if new_dir not in self._newdirs[source_dir]:
                    self._newdirs[source_dir].add(new_dir)
                    fo.write(f"{source_dir}:{new_dir}\n")

    def _get_suggested_newdirs(self, files: List[str]) -> List[str]:
        """Get all suggested new directories for the given files."""
        suggestions = set()
        for f in files:
            file_dir = os.path.dirname(os.path.abspath(f))
            if file_dir in self._newdirs:
                suggestions.update(self._newdirs[file_dir])
        return sorted(suggestions)

    def squeeze_redundant(self, dups: Dict[FileHash, List[FilePath]]) -> List[FilePath]:
        redundant_files = []
        total = len(dups)
        start = time.monotonic()
        bulk = 100
        for index, (_md5, files) in enumerate(dups.items()):
            while True:
                if index % bulk == 0:
                    now = time.monotonic() + 1
                    velocity = round(bulk / (now - start), 2) or 0
                    start = time.monotonic()
                    logger.info(
                        f"{total - index} files left, {velocity} files per second"
                    )
                good_files, redundant_by_rules = self.appraiser.decide(files)
                redundant_files += redundant_by_rules

                if len(good_files) <= 1:
                    break

                logger.info(f"file {index} from {total}")
                try:
                    good_files, redundant = self.filter_by_biobot(good_files)
                    for file in good_files:
                        self.appraiser.add_from_file(file)
                    redundant_files += redundant
                    break
                except ReloadRuleException:
                    self.appraiser.reload_rules()
                    continue

            # store good_file to file for future rerun
        return redundant_files

    def filter_by_biobot(self, files) -> Tuple[List[FilePath], List[FilePath]]:
        # return rule, selected file and files to remove

        # check if any suggested dir is activated for auto-move
        suggested = self._get_suggested_newdirs(files)
        for sug in suggested:
            if sug in self._auto_newdirs:
                return self._move_to_new_location(files, sug)

        # question the user for keep rule
        logger.info("what do you want to keep?\n")

        questions = []
        logger.info("-. remove all\n")
        logger.info("+. leave all\n")
        logger.info("r. reload rules\n")
        logger.info("n. move to new location\n")

        # show suggested new directories if any (a=again, b, c, ...)
        suggested = self._get_suggested_newdirs(files)
        suggested_map = {}
        for i, sug in enumerate(suggested):
            key = chr(ord("a") + i)  # a, b, c, ...
            suggested_map[key] = sug
            logger.info(f"{key}. move to {sug}\n")
            questions.append(key)

        files = sorted(files)
        for index, filename in enumerate(files):
            logger.info(f"{index}. {filename}\n")
            questions.append(str(index))
        questions += ["-", "+", "r", "n"]

        answer = ""
        while answer not in questions:
            answer = input("select>").lower()

        if answer == "-":
            return [], files
        elif answer == "+":
            self.appraiser.save_answer(files)
            return files, []
        elif answer == "r":
            raise ReloadRuleException()
        elif answer == "n":
            return self._move_to_new_location(files, None)
        elif answer in suggested_map:
            selected_dir = suggested_map[answer]
            self._auto_newdirs.add(selected_dir)
            logger.info(f"auto-move enabled for: {selected_dir}\n")
            return self._move_to_new_location(files, selected_dir)

        keep_index = int(answer)
        files_to_delete = files[:keep_index] + files[keep_index + 1 :]

        self.appraiser.save_answer([files[keep_index]])
        return [files[keep_index]], files_to_delete

    def _move_to_new_location(
        self, files, new_dir: Optional[str] = None
    ) -> Tuple[List[FilePath], List[FilePath]]:
        # prompt for new directory if not provided
        if new_dir is None:
            new_dir = input("new directory>").strip()
            new_dir = os.path.expanduser(new_dir)
            new_dir = os.path.abspath(new_dir)

        # save mapping: all source directories -> new_dir
        source_dirs = list({os.path.dirname(os.path.abspath(f)) for f in files})
        self._save_newdir(source_dirs, new_dir)

        # find first existing file to move (checkpoint may be stale)
        source_file = None
        for f in files:
            if os.path.exists(f):
                source_file = f
                break

        if source_file is None:
            logger.warning("no source files exist, skipping")
            return [], []

        filename = os.path.basename(source_file)
        new_path = os.path.join(new_dir, filename)

        # record pending move (executed later in _purge)
        self._pending_moves[source_file] = new_path
        logger.info(f"queued move: {source_file} -> {new_path}")

        # add new location to rules
        self.appraiser.add_from_file(new_path)
        self.appraiser.save_answer([new_path])

        # all other files are redundant
        files_to_delete = [f for f in files if f != source_file]
        return [new_path], files_to_delete
