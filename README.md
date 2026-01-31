# dedup

A command-line tool to find and remove duplicate files across directories using MD5 hash comparison.

## Features

- Scans multiple directories for duplicate files
- Uses MD5 hashing for accurate file comparison
- Caches file hashes for faster subsequent runs
- Interactive decision-making for handling duplicates
- Supports dry-run mode to preview changes
- Moves files to trash by default (safe deletion)
- Rule-based automatic duplicate resolution
- Checkpoint/resume support for large operations

## Installation

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv)

```bash
uv pip install .
```

## Development Setup

After cloning the repo, run:

```bash
make setup
```

This installs dependencies and sets up pre-commit hooks (ruff, mypy, pytest).

### Available Commands

| Command | Description |
|---------|-------------|
| `make setup` | Install deps + pre-commit hooks |
| `make test` | Run tests |
| `make lint` | Run linter + formatter + type checker |
| `make check` | Run all pre-commit hooks |

## Usage

### Find duplicates (stats)

Display all duplicate files without making changes:

```bash
dedup -d /path/to/directory stats
```

### Remove duplicates (dedup)

Interactively remove duplicate files:

```bash
dedup -d /path/to/directory dedup
```

### Multiple directories

Scan multiple directories:

```bash
dedup -d /path/one -d /path/two dedup
```

## Global Options

| Option | Description |
|--------|-------------|
| `-d, --dirs` | Directory to scan (required, can be used multiple times) |
| `-v, --verbose` | Enable verbose/debug output |
| `--dry-run` | Preview changes without making them |
| `-c` | Continue from previous run (resume checkpoint) |

## Commands

### `stats`

Displays all duplicate files grouped by MD5 hash. No files are modified.

### `dedup`

Finds duplicates and interactively prompts for resolution:

| Option | Description |
|--------|-------------|
| `-u, --unlink` | Permanently delete files instead of moving to trash |

During interactive mode, you can:
- Select a number to keep that file and delete others
- Enter `-` to remove all duplicates
- Enter `+` to keep all files
- Enter `r` to reload rules
- Enter `n` to move files to a new location
- Select suggested directories (a, b, c...) for auto-move

### `clear_cache`

Clears cached file hashes from scanned directories:

```bash
dedup -d /path/to/directory clear_cache
```

| Option | Description |
|--------|-------------|
| `-u, --unlink` | Permanently delete cache files instead of moving to trash |

## Configuration Files

The tool uses several `.dedup.*` files for state and configuration:

| File | Purpose |
|------|---------|
| `.dedup.rules.list` | Directory weight rules for automatic decisions |
| `.dedup.ignore.list` | Patterns to ignore during deduplication |
| `.dedup.remove.list` | Patterns for files to always remove |
| `.dedup.answers.list` | Previously selected files to keep |
| `.dedup.checkpoint` | Checkpoint for resuming operations |
| `.dedup-meta.cpl` | Per-directory hash cache |

### Ignore file format (`.dedup.ignore.list`)

```
=:/full/path/to/ignore
~:partial_match
```

### Remove file format (`.dedup.remove.list`)

```
f:filename.jpg
d:/directory/path/
~:partial_match
```

## Testing

Run all tests:

```bash
uv run pytest tests/ -v
```

Run specific test class:

```bash
uv run pytest tests/test_integration.py::TestDedupRemoval -v
```

### Test Summary

| Test Class | Tests | What it verifies |
|------------|-------|------------------|
| **TestDuplicateDetection** | 3 | Finds duplicates across/within directories |
| **TestMultipleDirectories** | 1 | Scanning multiple root paths |
| **TestDeepNesting** | 1 | Deep directory trees (5+ levels) |
| **TestCacheSpeedup** | 2 | Cache speeds up rescans, invalidates on file change |
| **TestPartialHashing** | 4 | Large file optimization (prefix+middle+suffix hash) |
| **TestSizeFirstOptimization** | 2 | Only size-collision files are hashed |
| **TestDedupRemoval** | 3 | Files correctly marked/removed, no duplicates remain |
| **TestMoveToNewDirectory** | 2 | Move duplicates to new location instead of delete |
| **TestActualFileOperations** | 4 | Files actually deleted/moved, dry-run safety, empty dir cleanup |
| **TestClearCache** | 4 | Clearing hash cache, session files, answers, rules |
| **TestCache** | 2 | Cache create/load/wipe |
| **TestFileReader** | 2 | MD5 hashing correctness |
| **TestWalker** | 2 | Directory traversal |

### Test Configuration

Tests use injectable thresholds for fast execution:

```python
reset_ctx.large_file_threshold = 100  # bytes (default 100MB)
reset_ctx.partial_hash_size = 10      # bytes (default 10MB)
```

## Additional Tool: tidy

Organizes files into date-based directories:

```bash
tidy images /path/to/files
```

Moves files into subdirectories named by modification date (YYYY-MM-DD).

## License

MIT
