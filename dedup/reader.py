import os

from hashlib import md5

from .context import ctx


class File:
    def __init__(self, filename, directory):
        self.filename = filename
        self._stat = None
        self._hash = None
        self.directory = directory

    @property
    def hashed(self):
        return self._hash is not None

    @property
    def size(self):
        return self.stat.st_size

    def ensure_stat(self):
        """Populate stat for caching (no hashing yet)."""
        self.stat

    def ensure_hash(self):
        """Compute hash (only call for size-collision files)."""
        self.stat  # populate _stat for cache invalidation
        self.hash

    @property
    def hash(self):
        if not self._hash:
            self._hash = FileReader.hash(self.filename)
        return self._hash

    @property
    def stat(self):
        if not self._stat:
            self._stat = FileReader.stat(self.filename)
        return self._stat

    @classmethod
    def from_cache(cls, other: "File"):
        f = cls(other.filename, other.directory)
        mst = f.stat
        ost = other.stat
        if (mst.st_size, round(mst.st_mtime, 2)) == (
            ost.st_size,
            round(ost.st_mtime, 2),
        ):
            f._hash = other._hash
        return f


class FileReader:
    CHUNK_SIZE = 64 * 1024  # 64KB chunks

    @staticmethod
    def hash(filename, full=False):
        """Quick hash for initial scan. Use full=True for verification."""
        file_size = os.path.getsize(filename)

        if full or file_size <= ctx.large_file_threshold:
            return FileReader._hash_full_file(filename)
        return FileReader._hash_partial(filename, file_size)

    @staticmethod
    def _hash_full_file(filename):
        m = md5()
        with open(filename, "rb") as fi:
            while chunk := fi.read(FileReader.CHUNK_SIZE):
                m.update(chunk)
        return m.hexdigest()

    @staticmethod
    def _hash_partial(filename, file_size):
        """Hash prefix + middle + suffix for large files."""
        m = md5()
        segment_size = ctx.partial_hash_size

        with open(filename, "rb") as fi:
            # prefix
            FileReader._hash_segment(fi, m, segment_size)

            # middle
            middle_pos = (file_size - segment_size) // 2
            fi.seek(middle_pos)
            FileReader._hash_segment(fi, m, segment_size)

            # suffix
            fi.seek(file_size - segment_size)
            FileReader._hash_segment(fi, m, segment_size)

        return m.hexdigest()

    @staticmethod
    def _hash_segment(fi, m, size):
        bytes_read = 0
        while bytes_read < size:
            chunk = fi.read(min(FileReader.CHUNK_SIZE, size - bytes_read))
            if not chunk:
                break
            m.update(chunk)
            bytes_read += len(chunk)

    @staticmethod
    def stat(f):
        return os.stat(f)
