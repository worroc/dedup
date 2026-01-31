import os
import pickle

from . import logger
from .context import ctx
from .misc import del_file


def cache_file(directory):
    return os.path.join(directory, ctx.cache_filename)


class DirCache(dict):
    def __init__(self, directory: str):
        self.cache_path = cache_file(directory)

    def store(self):
        if not ctx.dry_run:
            with open(self.cache_path, "wb") as fo:
                pickle.dump(self, fo)

    def load(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "rb") as fi:
                try:
                    fixed_cache = pickle.load(fi)
                    # fixed_cache = {to_abs(k): v for (k,v) in pickle.load(fi).items()}
                    self.update(fixed_cache)
                except Exception as e:
                    logger.info(f"unable to load {self.cache_path}. {e}")
            # self.store()

    def add(self, key, data):
        self[key] = data

    def wipe(self):
        del_file(self.cache_path)


def load(directory: str):
    cache = DirCache(directory)
    cache.load()
    return cache


def new(directory: str):
    cache = DirCache(directory)
    return cache


def clear(directory: str):
    cache = DirCache(directory)
    cache.wipe()


def exists(directory: str):
    return os.path.exists(cache_file(directory))
