import pytest

from dedup.context import ctx


@pytest.fixture
def temp_tree(tmp_path):
    """Creates a temporary directory tree with test files and cleans up after."""
    tree_root = tmp_path / "test_tree"
    tree_root.mkdir()

    yield tree_root

    # cleanup is automatic with tmp_path


@pytest.fixture
def duplicate_tree(tmp_path):
    """Creates a tree with duplicate files for testing dedup logic."""
    root = tmp_path / "dup_tree"
    root.mkdir()

    dir_a = root / "dir_a"
    dir_b = root / "dir_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # identical files in different directories
    content = b"duplicate content here"
    (dir_a / "file1.txt").write_bytes(content)
    (dir_b / "file1_copy.txt").write_bytes(content)

    # unique file
    (dir_a / "unique.txt").write_bytes(b"unique content")

    # another set of duplicates
    content2 = b"another duplicate"
    (dir_a / "dup2.txt").write_bytes(content2)
    (dir_b / "dup2_copy.txt").write_bytes(content2)

    yield root


@pytest.fixture
def reset_ctx():
    """Reset context to defaults before and after test."""
    original = {
        "verbose": ctx.verbose,
        "dry_run": ctx.dry_run,
        "rerun": ctx.rerun,
        "dirs": ctx.dirs,
        "unlink": ctx.unlink,
        "large_file_threshold": ctx.large_file_threshold,
        "partial_hash_size": ctx.partial_hash_size,
    }

    ctx.verbose = False
    ctx.dry_run = True
    ctx.rerun = False
    ctx.dirs = []
    ctx.unlink = False
    ctx.large_file_threshold = 100 * 1024 * 1024  # 100MB default
    ctx.partial_hash_size = 10 * 1024 * 1024  # 10MB default

    yield ctx

    for k, v in original.items():
        setattr(ctx, k, v)


@pytest.fixture
def working_dir(temp_tree, monkeypatch):
    """Change working directory to temp_tree's parent for test, restore after."""
    work_dir = temp_tree.parent
    monkeypatch.chdir(work_dir)
    yield work_dir
