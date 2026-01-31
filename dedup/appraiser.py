import os
from typing import List, Tuple
from collections import defaultdict

from . import logger

from .context import ctx
from .misc import to_abs


class Appraiser:
    def __init__(self):
        self._rules = defaultdict(int)  # file_path: weight
        self._answers = set()
        self._ignore = defaultdict(set)
        self._remove = defaultdict(set)
        self.reload_rules()
        self.load_answers()

    def calc_weight(self, filepath):
        # calculates weight for cpeciefic filepath
        weight = 0
        for rule in self._rules:
            if filepath.startswith(rule):
                weight += self._rules[rule]

            if os.path.dirname(filepath) == rule:
                # increase wieght if rule exact match the file directory
                weight += self._rules[rule]
        return weight

    def is_ignored(self, file) -> bool:
        while file:
            if file in self._ignore["="]:
                return True
            for pat in self._ignore["~"]:
                if pat in file:
                    return True
            dirname = os.path.dirname(file)
            if file == dirname:
                return False
            file = dirname
        return False

    def in_remove(self, directory, filename):
        if os.path.basename(filename) in self._remove["f"]:
            return True
        elif directory in self._remove["d"]:
            return True
        for par in self._remove["~"]:
            if par in filename:
                return True
        return False

    def weight(self, files, filter_removed=True):
        weighted = defaultdict(list)
        leftovers = []
        dirs = set()
        for filename in files:
            filename = to_abs(filename)
            directory = os.path.dirname(filename)

            if filter_removed:
                if self.in_remove(directory, filename):
                    leftovers.append(filename)
                    continue

            if directory in dirs:
                # we have already file in this directory
                leftovers.append(filename)
                continue
            else:
                dirs.add(directory)

            weighted[self.calc_weight(filename)].append(filename)

        if not weighted:
            weighted, leftovers = self.weight(files, filter_removed=False)
        return weighted, leftovers

    def decide(self, files) -> Tuple[List[str], List[str]]:
        files = [file for file in files if not self.is_ignored(file)]

        if not files:
            return [], []

        selected, _leftovers = self.already_selected(files)
        if selected:
            return selected, _leftovers

        weighted, leftovers = self.weight(files)

        sorted_by_weight = sorted(weighted.items(), reverse=True)
        if sorted_by_weight:
            selected = sorted_by_weight[0][1]

            for x in sorted_by_weight[1:]:
                leftovers += x[1]

        return selected, leftovers

    def add_from_file(self, file_path: str):
        dirname = to_abs(os.path.dirname(file_path))
        self._rules[dirname] += 1
        with ctx.appraiser_rules_filename.open(encoding="utf-8", mode="w") as fo:
            for _path, _weight in self._rules.items():
                fo.write(f"{_weight}:{_path}\n")

    def reload_rules(self):
        self._rules = defaultdict(int)

        if ctx.rerun and os.path.exists(ctx.appraiser_rules_filename):
            logger.debug(f"read rules from {ctx.appraiser_rules_filename}")
            with ctx.appraiser_rules_filename.open(encoding="utf-8", mode="rt") as fi:
                for line in fi.readlines():
                    line = line.strip()
                    if not line:
                        continue
                    _wieght, _path = line.split(":", 1)
                    self._rules[_path] = int(_wieght)
            logger.debug(f"read ignore file from {ctx.appraiser_ignore_filename}")
            self._ignore = defaultdict(set)
            if os.path.exists(ctx.appraiser_ignore_filename):
                with ctx.appraiser_ignore_filename.open(
                    encoding="utf-8", mode="rt"
                ) as fi:
                    # format
                    # =:/pictures/fdgdf/  # if /pictures/fdgdf/ == abs_file_name
                    # ~:print  # if print in abs_file_name

                    for line in fi.readlines():
                        line = line.strip()
                        if not line:
                            continue
                        tp, text = line.split(":", 1)
                        self._ignore[tp].add(text)

            logger.debug(f"read removal file from {ctx.appraiser_remove_filename}")
            self._remove = defaultdict(set)
            if os.path.exists(ctx.appraiser_remove_filename):
                with ctx.appraiser_remove_filename.open(
                    encoding="utf-8", mode="rt"
                ) as fi:
                    # f:aaa.jpg  # if aaa.jpg == os.path.basename("/ddd/ggg/aaa.jpg")
                    # d:/aaa/bbb/  # if /aaa/bbb/ == os.path.dirname("/ddd/ggg/aaa.jpg")
                    # ~:print  # if print in abs_file_name

                    for line in fi.readlines():
                        line = line.strip()
                        if not line:
                            continue
                        tp, text = line.split(":", 1)
                        self._remove[tp].add(text)

    def load_answers(self):
        logger.debug(f"read answers file from {ctx.answers_filename}")
        if ctx.rerun and os.path.exists(ctx.answers_filename):
            with ctx.answers_filename.open(encoding="utf-8", mode="rt") as fi:
                self._answers = {
                    to_abs(line.strip()) for line in fi.readlines() if line.strip()
                }
            logger.debug(f"loaded {len(self._answers)} answers")

    def already_selected(self, files: List[str]):
        normalized = {to_abs(f): f for f in files}
        selected = [normalized[k] for k in normalized if k in self._answers]
        leftovers = [normalized[k] for k in normalized if k not in self._answers]
        return selected, leftovers

    def save_answer(self, files: List[str]):
        with ctx.answers_filename.open(encoding="utf-8", mode="a") as fo:
            for file in files:
                normalized = to_abs(file)
                if normalized not in self._answers:
                    self._answers.add(normalized)
                    fo.write(normalized + "\n")
