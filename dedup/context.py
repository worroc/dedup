from typing import List
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class RunContext:
    verbose: bool = False
    dry_run: bool = False
    rerun: bool = False
    dirs: List[Path] = field(default_factory=list)
    unlink: bool = False
    cache_filename: str = ".dedup-meta.cpl"
    progress_filename: Path = Path(".dedup.progress")
    appraiser_rules_filename: Path = Path(".dedup.rules.list")
    appraiser_ignore_filename: Path = Path(".dedup.ignore.list")
    appraiser_remove_filename: Path = Path(".dedup.remove.list")
    answers_filename: Path = Path(".dedup.answers.list")
    newdirs_filename: Path = Path(".dedup.newdirs.list")
    checkpoint_filename: Path = Path(".dedup.checkpoint")
    final_redundant: Path = Path(".dedup.final_redundant")
    pending_moves_filename: Path = Path(".dedup.pending_moves")

    # hash optimization thresholds
    large_file_threshold: int = 100 * 1024 * 1024  # 100MB
    partial_hash_size: int = 10 * 1024 * 1024  # 10MB per segment


ctx = RunContext()
