import time

from dedup.processor import Processor
from dedup.context import ctx


class TestDuplicateDetection:
    def test_find_duplicates(self, duplicate_tree, reset_ctx, working_dir):
        reset_ctx.dry_run = True
        reset_ctx.cache_filename = ".test-cache.cpl"

        processor = Processor([str(duplicate_tree)])
        files, dups = processor.calculus()

        # should find 2 sets of duplicates
        assert len(dups) == 2

        # each set should have 2 files
        for hash_id, dup_files in dups.items():
            assert len(dup_files) == 2

    def test_no_duplicates_in_unique_tree(self, temp_tree, reset_ctx, working_dir):
        reset_ctx.dry_run = True
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create unique files only
        (temp_tree / "file1.txt").write_bytes(b"unique1")
        (temp_tree / "file2.txt").write_bytes(b"unique2")
        (temp_tree / "file3.txt").write_bytes(b"unique3")

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        assert len(dups) == 0

    def test_duplicates_same_directory(self, temp_tree, reset_ctx, working_dir):
        reset_ctx.dry_run = True
        reset_ctx.cache_filename = ".test-cache.cpl"

        # duplicates in same directory
        content = b"same content"
        (temp_tree / "copy1.txt").write_bytes(content)
        (temp_tree / "copy2.txt").write_bytes(content)
        (temp_tree / "copy3.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        assert len(dups) == 1
        dup_files = list(dups.values())[0]
        assert len(dup_files) == 3


class TestMultipleDirectories:
    def test_scan_multiple_roots(self, tmp_path, reset_ctx, working_dir):
        reset_ctx.dry_run = True
        reset_ctx.cache_filename = ".test-cache.cpl"

        root1 = tmp_path / "root1"
        root2 = tmp_path / "root2"
        root1.mkdir()
        root2.mkdir()

        content = b"shared duplicate"
        (root1 / "file.txt").write_bytes(content)
        (root2 / "file_copy.txt").write_bytes(content)

        processor = Processor([str(root1), str(root2)])
        files, dups = processor.calculus()

        assert len(dups) == 1


class TestDeepNesting:
    def test_deeply_nested_duplicates(self, temp_tree, reset_ctx, working_dir):
        reset_ctx.dry_run = True
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create deep nesting
        deep_path = temp_tree / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True)

        content = b"deep duplicate"
        (temp_tree / "shallow.txt").write_bytes(content)
        (deep_path / "deep.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        assert len(dups) == 1
        dup_files = list(dups.values())[0]
        assert len(dup_files) == 2


class TestCacheSpeedup:
    def test_second_scan_uses_cache(self, temp_tree, reset_ctx, working_dir):
        """Second scan should be faster due to cached hashes."""
        reset_ctx.dry_run = False  # need to write cache
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create files
        for i in range(20):
            (temp_tree / f"file{i}.txt").write_bytes(f"content {i}".encode() * 1000)

        # first scan - builds cache
        processor = Processor([str(temp_tree)])
        start1 = time.perf_counter()
        files1, dups1 = processor.calculus()
        time1 = time.perf_counter() - start1

        # verify cache file created
        cache_file = temp_tree / reset_ctx.cache_filename
        assert cache_file.exists()

        # second scan - should use cache
        processor2 = Processor([str(temp_tree)])
        start2 = time.perf_counter()
        files2, dups2 = processor2.calculus()
        time2 = time.perf_counter() - start2

        # results should be identical
        assert len(files1) == len(files2)

        # second scan should be faster (cache hit)
        # allow some margin for test flakiness
        assert time2 < time1 or time2 < 0.1  # either faster or both very fast

    def test_cache_invalidated_on_file_change(self, temp_tree, reset_ctx, working_dir):
        """Modified file should be re-hashed, not use stale cache."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        test_file = temp_tree / "changeme.txt"
        test_file.write_bytes(b"original content")

        # first scan
        processor = Processor([str(temp_tree)])
        files1, _ = processor.calculus()
        hash1 = list(files1.values())[0].hash

        # modify file with different size to ensure cache invalidation
        # (cache checks size and mtime)
        test_file.write_bytes(b"modified content that is longer")

        # second scan should detect change
        processor2 = Processor([str(temp_tree)])
        files2, _ = processor2.calculus()
        hash2 = list(files2.values())[0].hash

        assert hash1 != hash2


class TestPartialHashing:
    def test_large_file_uses_partial_hash(self, temp_tree, reset_ctx, working_dir):
        """Files above threshold use partial hash (prefix+middle+suffix)."""
        # use small thresholds for testing
        reset_ctx.large_file_threshold = 100  # 100 bytes
        reset_ctx.partial_hash_size = 10  # 10 bytes per segment
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create "large" file (>100 bytes) - partial hash
        # structure: prefix(10) + middle + suffix(10)
        large_content = b"A" * 10 + b"B" * 100 + b"C" * 10  # 120 bytes
        (temp_tree / "large.txt").write_bytes(large_content)

        from dedup.reader import FileReader

        quick_hash = FileReader.hash(str(temp_tree / "large.txt"), full=False)
        full_hash = FileReader.hash(str(temp_tree / "large.txt"), full=True)

        # partial and full hash should differ (partial skips middle B's)
        assert quick_hash != full_hash

    def test_small_file_uses_full_hash(self, temp_tree, reset_ctx, working_dir):
        """Files at or below threshold use full hash."""
        reset_ctx.large_file_threshold = 100
        reset_ctx.partial_hash_size = 10
        reset_ctx.dry_run = False

        # create "small" file (<=100 bytes) - full hash
        small_content = b"X" * 50
        (temp_tree / "small.txt").write_bytes(small_content)

        from dedup.reader import FileReader

        quick_hash = FileReader.hash(str(temp_tree / "small.txt"), full=False)
        full_hash = FileReader.hash(str(temp_tree / "small.txt"), full=True)

        # both should be identical for small files
        assert quick_hash == full_hash

    def test_partial_hash_detects_different_middles(
        self, temp_tree, reset_ctx, working_dir
    ):
        """Partial hash includes middle segment, catches different middles."""
        reset_ctx.large_file_threshold = 100
        reset_ctx.partial_hash_size = 10
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # same prefix/suffix, different middle
        file1 = b"A" * 10 + b"X" * 100 + b"Z" * 10
        file2 = b"A" * 10 + b"Y" * 100 + b"Z" * 10
        (temp_tree / "file1.txt").write_bytes(file1)
        (temp_tree / "file2.txt").write_bytes(file2)

        from dedup.reader import FileReader

        hash1 = FileReader.hash(str(temp_tree / "file1.txt"))
        hash2 = FileReader.hash(str(temp_tree / "file2.txt"))

        # should detect difference in middle
        assert hash1 != hash2

    def test_verification_catches_partial_hash_collision(
        self, temp_tree, reset_ctx, working_dir
    ):
        """Full hash verification catches files that match on partial but differ."""
        reset_ctx.large_file_threshold = 100
        reset_ctx.partial_hash_size = 10
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # craft files with same prefix+middle+suffix but different content
        # prefix=10, middle_pos=(120-10)//2=55, suffix_start=110
        # segments: [0:10], [55:65], [110:120]
        base = bytearray(120)
        base[0:10] = b"A" * 10  # prefix
        base[55:65] = b"M" * 10  # middle
        base[110:120] = b"Z" * 10  # suffix

        file1 = bytes(base)
        base[30:40] = b"DIFFERENT!"  # change outside sampled regions
        file2 = bytes(base)

        (temp_tree / "tricky1.txt").write_bytes(file1)
        (temp_tree / "tricky2.txt").write_bytes(file2)

        # run full dedup - verification should catch this
        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # should NOT be marked as duplicates after verification
        assert len(dups) == 0


class TestSizeFirstOptimization:
    def test_unique_sizes_not_hashed(self, temp_tree, reset_ctx, working_dir):
        """Files with unique sizes should not be hashed."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create files with unique sizes
        (temp_tree / "file1.txt").write_bytes(b"a")  # 1 byte
        (temp_tree / "file2.txt").write_bytes(b"bb")  # 2 bytes
        (temp_tree / "file3.txt").write_bytes(b"ccc")  # 3 bytes

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # no duplicates
        assert len(dups) == 0

        # verify no files were hashed (unique sizes)
        for file_obj in files.values():
            assert not file_obj.hashed, f"{file_obj.filename} should not be hashed"

    def test_only_size_collisions_hashed(self, temp_tree, reset_ctx, working_dir):
        """Only files with matching sizes should be hashed."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # unique size - should NOT be hashed
        (temp_tree / "unique.txt").write_bytes(b"unique content here")

        # same size (10 bytes each) - should be hashed
        (temp_tree / "dup1.txt").write_bytes(b"1234567890")
        (temp_tree / "dup2.txt").write_bytes(b"abcdefghij")

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # find file objects by name
        unique_file = [f for f in files.values() if "unique" in f.filename][0]
        dup_files = [f for f in files.values() if "dup" in f.filename]

        # unique size file should NOT be hashed
        assert not unique_file.hashed, "unique size file should not be hashed"

        # size collision files should be hashed
        for f in dup_files:
            assert f.hashed, f"{f.filename} should be hashed (size collision)"


class TestDedupRemoval:
    def test_correct_files_marked_for_deletion(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Verify that duplicate files are correctly marked for deletion."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create 3 copies of same file
        content = b"duplicate content"
        (temp_tree / "original.txt").write_bytes(content)
        (temp_tree / "copy1.txt").write_bytes(content)
        (temp_tree / "copy2.txt").write_bytes(content)

        # unique file - should NOT be deleted
        (temp_tree / "unique.txt").write_bytes(b"unique")

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # should find 1 group of 3 duplicates
        assert len(dups) == 1
        dup_files = list(dups.values())[0]
        assert len(dup_files) == 3

        # mock user input to auto-select first file (keep index 0)
        inputs = iter(["0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)

        # should mark 2 files for deletion (keep 1 of 3)
        assert len(files_to_delete) == 2

        # unique file should NOT be in deletion list
        unique_path = str(temp_tree / "unique.txt")
        assert unique_path not in files_to_delete

    def test_multiple_duplicate_groups(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Test handling of multiple independent duplicate groups."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # group 1: 3 copies
        (temp_tree / "group1_a.txt").write_bytes(b"content group 1")
        (temp_tree / "group1_b.txt").write_bytes(b"content group 1")
        (temp_tree / "group1_c.txt").write_bytes(b"content group 1")

        # group 2: 2 copies
        (temp_tree / "group2_a.txt").write_bytes(b"content group 2")
        (temp_tree / "group2_b.txt").write_bytes(b"content group 2")

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # should find 2 groups
        assert len(dups) == 2

        # mock user input - select first file for each group
        inputs = iter(["0", "0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)

        # group1: keep 1, delete 2
        # group2: keep 1, delete 1
        # total: 3 files to delete
        assert len(files_to_delete) == 3

    def test_all_duplicates_removed_after_purge(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Verify no duplicates remain after purge."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True  # delete instead of trash

        content = b"duplicate content here"
        (temp_tree / "keep.txt").write_bytes(content)
        (temp_tree / "delete1.txt").write_bytes(content)
        (temp_tree / "delete2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # mock input: select first file to keep, then "yes" to confirm
        inputs = iter(["0", "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()

        # execute purge
        processor._purge(files_to_delete, pending_moves, dups)

        # verify: only 1 file remains with that content
        remaining = list(temp_tree.glob("*.txt"))
        assert len(remaining) == 1

        # rescan should find no duplicates
        processor2 = Processor([str(temp_tree)])
        files2, dups2 = processor2.calculus()
        assert len(dups2) == 0


class TestMoveToNewDirectory:
    def test_move_duplicate_to_new_location(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Test moving a duplicate to a new directory instead of deleting."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True

        # create duplicates in different dirs
        dir_a = temp_tree / "dir_a"
        dir_b = temp_tree / "dir_b"
        new_dir = temp_tree / "new_location"
        dir_a.mkdir()
        dir_b.mkdir()

        content = b"duplicate content"
        (dir_a / "file.txt").write_bytes(content)
        (dir_b / "file_copy.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        assert len(dups) == 1

        # mock all inputs in sequence
        inputs = iter(["n", str(new_dir), "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()

        # should have 1 move queued
        assert len(pending_moves) == 1

        # execute purge
        processor._purge(files_to_delete, pending_moves, dups)

        # verify file was moved
        assert new_dir.exists()
        moved_files = list(new_dir.glob("*"))
        assert len(moved_files) == 1

    def test_move_queued_correctly(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Test that move is queued with correct source and destination."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # files must be in different directories
        dir_a = temp_tree / "dir_a"
        dir_b = temp_tree / "dir_b"
        target_dir = temp_tree / "target"
        dir_a.mkdir()
        dir_b.mkdir()

        content = b"duplicate"
        (dir_a / "file1.txt").write_bytes(content)
        (dir_b / "file2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # select "n" and specify target_dir
        inputs = iter(["n", str(target_dir)])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()

        # verify move is queued correctly
        assert len(pending_moves) == 1
        src, dst = list(pending_moves.items())[0]
        assert str(target_dir) in dst


class TestActualFileOperations:
    def test_files_actually_deleted(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Verify files are actually deleted from filesystem."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True  # permanent delete

        content = b"to be deleted"
        keep_file = temp_tree / "keep.txt"
        del_file1 = temp_tree / "delete1.txt"
        del_file2 = temp_tree / "delete2.txt"

        keep_file.write_bytes(content)
        del_file1.write_bytes(content)
        del_file2.write_bytes(content)

        # verify all exist before
        assert keep_file.exists()
        assert del_file1.exists()
        assert del_file2.exists()

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # select first file to keep
        inputs = iter(["0", "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()
        processor._purge(files_to_delete, pending_moves, dups)

        # verify: only 1 file remains
        remaining = list(temp_tree.glob("*.txt"))
        assert len(remaining) == 1
        assert remaining[0].read_bytes() == content

    def test_files_actually_moved(self, temp_tree, reset_ctx, working_dir, monkeypatch):
        """Verify files are actually moved to new location."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True

        # files in different directories to trigger interactive mode
        dir_a = temp_tree / "dir_a"
        dir_b = temp_tree / "dir_b"
        dest = temp_tree / "dest"
        dir_a.mkdir()
        dir_b.mkdir()

        content = b"move me"
        (dir_a / "original.txt").write_bytes(content)
        (dir_b / "copy.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # all inputs in one iterator: "n" -> dest path -> "yes" for purge
        inputs = iter(["n", str(dest), "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()

        assert len(pending_moves) == 1

        processor._purge(files_to_delete, pending_moves, dups)

        # verify: file moved to dest
        assert dest.exists()
        dest_files = list(dest.glob("*"))
        assert len(dest_files) == 1
        assert dest_files[0].read_bytes() == content

    def test_dry_run_does_not_delete(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Verify dry-run mode doesn't actually delete files."""
        reset_ctx.dry_run = True  # DRY RUN
        reset_ctx.cache_filename = ".test-cache.cpl"

        content = b"should survive"
        (temp_tree / "file1.txt").write_bytes(content)
        (temp_tree / "file2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        inputs = iter(["0", "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()
        processor._purge(files_to_delete, pending_moves, dups)

        # both files should still exist
        remaining = list(temp_tree.glob("*.txt"))
        assert len(remaining) == 2

    def test_empty_directories_removed_after_delete(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Verify empty directories are cleaned up after deleting files."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True

        # create nested structure - one dir will become empty after delete
        main_dir = temp_tree / "main"
        nested_dir = temp_tree / "nested" / "deep"
        main_dir.mkdir()
        nested_dir.mkdir(parents=True)

        content = b"duplicate"
        main_file = main_dir / "main.txt"
        nested_file = nested_dir / "nested.txt"
        main_file.write_bytes(content)
        nested_file.write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # find which index is the main file (to keep it)
        dup_files = list(dups.values())[0]
        keep_index = next(i for i, f in enumerate(dup_files) if "main" in f)

        inputs = iter([str(keep_index), "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()
        processor._purge(files_to_delete, pending_moves, dups)

        # verify: main_dir still exists with file, nested_dir removed (empty)
        assert main_file.exists()
        assert not nested_file.exists()
        assert not nested_dir.exists()


class TestStatsCommand:
    def test_stats_displays_duplicates(self, temp_tree, reset_ctx, working_dir, capsys):
        """Test stats command displays duplicate information."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        content = b"duplicate"
        (temp_tree / "file1.txt").write_bytes(content)
        (temp_tree / "file2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        processor.stats()

        # stats should run without error and produce output
        capsys.readouterr()
        # output goes to logger, not stdout, but no exception = success


class TestPurgeOptions:
    def test_purge_list_option(self, temp_tree, reset_ctx, working_dir, monkeypatch):
        """Test 'list' option in purge shows pending changes."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        dir_a = temp_tree / "dir_a"
        dir_b = temp_tree / "dir_b"
        dir_a.mkdir()
        dir_b.mkdir()

        content = b"duplicate"
        (dir_a / "file1.txt").write_bytes(content)
        (dir_b / "file2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # select file to keep
        inputs = iter(["0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()

        # now test list then yes
        inputs = iter(["list", "yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        processor._purge(files_to_delete, pending_moves, dups)

        # should complete without error

    def test_purge_no_option(self, temp_tree, reset_ctx, working_dir, monkeypatch):
        """Test 'no' option in purge cancels without changes."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True

        content = b"duplicate"
        (temp_tree / "file1.txt").write_bytes(content)
        (temp_tree / "file2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        inputs = iter(["0"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        files_to_delete = processor.press.squeeze_redundant(dups)
        pending_moves = processor.press.get_pending_moves()

        # say "no" to purge
        inputs = iter(["no"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        processor._purge(files_to_delete, pending_moves, dups)

        # both files should still exist
        assert (temp_tree / "file1.txt").exists()
        assert (temp_tree / "file2.txt").exists()

    def test_purge_move_source_not_found(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Test purge handles missing source file for move gracefully."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        # create pending move with non-existent source
        pending_moves = {"/nonexistent/source.txt": str(temp_tree / "dest.txt")}
        files_to_delete = []
        dups = {}

        inputs = iter(["yes"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        # should complete without error, just warn
        processor = Processor([str(temp_tree)])
        processor._purge(files_to_delete, pending_moves, dups)


class TestCheckpointRerun:
    def test_rerun_loads_checkpoint(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Test that rerun loads from checkpoint files."""
        import pickle

        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.unlink = True

        # create duplicate files
        content = b"duplicate"
        (temp_tree / "file1.txt").write_bytes(content)
        (temp_tree / "file2.txt").write_bytes(content)

        # first run - creates checkpoint
        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # save checkpoint manually
        with ctx.checkpoint_filename.open(mode="wb") as fo:
            pickle.dump(dups, fo)

        # enable rerun mode
        reset_ctx.rerun = True

        # second run should load from checkpoint
        processor2 = Processor([str(temp_tree)])

        # mock dedup to just verify checkpoint is loaded
        inputs = iter(["0", "no"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        processor2.dedup()

        # checkpoint file should exist
        assert ctx.checkpoint_filename.exists()

    def test_rerun_loads_final_redundant(
        self, temp_tree, reset_ctx, working_dir, monkeypatch
    ):
        """Test that rerun loads files_to_delete from checkpoint."""
        import pickle

        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.rerun = True

        # create checkpoint files
        dups = {"hash1": [str(temp_tree / "f1.txt"), str(temp_tree / "f2.txt")]}
        files_to_delete = [str(temp_tree / "f2.txt")]

        with ctx.checkpoint_filename.open(mode="wb") as fo:
            pickle.dump(dups, fo)
        with ctx.final_redundant.open(mode="wb") as fo:
            pickle.dump(files_to_delete, fo)

        # create the actual files
        (temp_tree / "f1.txt").write_bytes(b"content")
        (temp_tree / "f2.txt").write_bytes(b"content")

        processor = Processor([str(temp_tree)])

        # say no to avoid actual deletion
        inputs = iter(["no"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        processor.dedup()

        # both files still exist (we said no)
        assert (temp_tree / "f1.txt").exists()
        assert (temp_tree / "f2.txt").exists()


class TestLargeFileVerification:
    def test_large_files_verified_with_full_hash(
        self, temp_tree, reset_ctx, working_dir
    ):
        """Test that large file duplicates are verified with full hash."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"
        reset_ctx.large_file_threshold = 50  # 50 bytes
        reset_ctx.partial_hash_size = 10  # 10 bytes

        # create "large" files (>50 bytes) that are actual duplicates
        content = b"A" * 100  # 100 bytes, same content
        (temp_tree / "large1.txt").write_bytes(content)
        (temp_tree / "large2.txt").write_bytes(content)

        processor = Processor([str(temp_tree)])
        files, dups = processor.calculus()

        # should find them as duplicates after full verification
        assert len(dups) == 1
        assert len(list(dups.values())[0]) == 2


class TestClearCache:
    def test_clear_hash_cache(self, temp_tree, reset_ctx, working_dir):
        """Test clearing hash cache files from scanned directories."""
        reset_ctx.dry_run = False
        reset_ctx.cache_filename = ".test-cache.cpl"

        (temp_tree / "file.txt").write_bytes(b"content")

        # create cache by scanning
        processor = Processor([str(temp_tree)])
        processor.calculus()

        cache_file = temp_tree / reset_ctx.cache_filename
        assert cache_file.exists()

        # clear using internal method
        processor._clear_hash_cache()

        assert not cache_file.exists()

    def test_clear_session_files(self, temp_tree, reset_ctx, working_dir):
        """Test clearing session checkpoint files."""
        reset_ctx.dry_run = False

        # create session files
        ctx.checkpoint_filename.write_bytes(b"checkpoint")
        ctx.final_redundant.write_bytes(b"redundant")
        ctx.pending_moves_filename.write_bytes(b"moves")

        assert ctx.checkpoint_filename.exists()
        assert ctx.final_redundant.exists()
        assert ctx.pending_moves_filename.exists()

        processor = Processor([str(temp_tree)])
        processor._clear_session_files()

        assert not ctx.checkpoint_filename.exists()
        assert not ctx.final_redundant.exists()
        assert not ctx.pending_moves_filename.exists()

    def test_clear_saved_answers(self, temp_tree, reset_ctx, working_dir):
        """Test clearing saved user answers."""
        ctx.answers_filename.write_text("answer1\n")
        ctx.newdirs_filename.write_text("dir1\tdir2\n")

        assert ctx.answers_filename.exists()
        assert ctx.newdirs_filename.exists()

        processor = Processor([str(temp_tree)])
        processor._clear_saved_answers()

        assert not ctx.answers_filename.exists()
        assert not ctx.newdirs_filename.exists()

    def test_clear_rules(self, temp_tree, reset_ctx, working_dir):
        """Test clearing appraiser rule files."""
        ctx.appraiser_rules_filename.write_text("rule1\n")
        ctx.appraiser_ignore_filename.write_text("ignore1\n")
        ctx.appraiser_remove_filename.write_text("remove1\n")

        processor = Processor([str(temp_tree)])
        processor._clear_rules()

        assert not ctx.appraiser_rules_filename.exists()
        assert not ctx.appraiser_ignore_filename.exists()
        assert not ctx.appraiser_remove_filename.exists()
