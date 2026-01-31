from dedup import cache
from dedup.reader import FileReader
from dedup.walker import Walker


class TestCache:
    def test_cache_create_and_load(self, temp_tree, reset_ctx):
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        dir_cache = cache.new(str(temp_tree))
        dir_cache.add("file1.txt", {"hash": "abc123", "size": 100})
        dir_cache.add("file2.txt", {"hash": "def456", "size": 200})
        dir_cache.store()

        loaded = cache.load(str(temp_tree))
        assert "file1.txt" in loaded
        assert loaded["file1.txt"]["hash"] == "abc123"
        assert "file2.txt" in loaded

    def test_cache_wipe(self, temp_tree, reset_ctx):
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        dir_cache = cache.new(str(temp_tree))
        dir_cache.add("file1.txt", {"hash": "abc123"})
        dir_cache.store()

        cache_path = temp_tree / reset_ctx.cache_filename
        assert cache_path.exists()

        cache.clear(str(temp_tree))
        assert not cache_path.exists()


class TestFileReader:
    def test_hash_file(self, temp_tree):
        test_file = temp_tree / "test.txt"
        test_file.write_bytes(b"test content for hashing")

        hash1 = FileReader.hash(str(test_file))
        hash2 = FileReader.hash(str(test_file))

        assert hash1 == hash2
        assert len(hash1) == 32  # md5 hex length

    def test_different_content_different_hash(self, temp_tree):
        file1 = temp_tree / "file1.txt"
        file2 = temp_tree / "file2.txt"
        file1.write_bytes(b"content one")
        file2.write_bytes(b"content two")

        hash1 = FileReader.hash(str(file1))
        hash2 = FileReader.hash(str(file2))

        assert hash1 != hash2


class TestWalker:
    def test_walk_directory(self, temp_tree, reset_ctx, working_dir):
        reset_ctx.cache_filename = ".test-cache.cpl"

        (temp_tree / "file1.txt").write_bytes(b"content1")
        (temp_tree / "file2.txt").write_bytes(b"content2")
        subdir = temp_tree / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_bytes(b"content3")

        walker = Walker()
        files, directories = walker.build(str(temp_tree))

        assert len(files) == 3
        assert any("file1.txt" in f for f in files)
        assert any("file3.txt" in f for f in files)

    def test_walk_empty_directory(self, temp_tree, reset_ctx, working_dir):
        reset_ctx.cache_filename = ".test-cache.cpl"

        walker = Walker()
        files, directories = walker.build(str(temp_tree))

        assert len(files) == 0
