"""Repository synchronization utilities for the Applied Groundwater Modelling course.

Safe-by-default logic to align a working copy with a target remote/branch while
protecting user changes, especially outside the controlled JupyterHub environment.

Typical usage inside a notebook:

    from pathlib import Path
    from repo_sync import sync_repository, print_sync_summary
    result = sync_repository(
        force_reset=False,
        allow_local_reset=False,
        dry_run=False,
        repo_path_override=None,
        target_remote="origin",
        target_branch="course_2025",
    )
    print_sync_summary(result)

No SystemExit calls are made; callers receive a result dataclass with flags
indicating whether a destructive action occurred or was blocked.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import os
import subprocess
import textwrap
import shutil
import glob
from typing import Iterable, List, Optional

__all__ = [
    "RepoSyncResult",
    "discover_repo",
    "sync_repository",
    "print_sync_summary",
]

@dataclass
class RepoSyncResult:
    repo_path: Optional[str]
    jupyterhub: bool
    changed_files: List[str]
    performed_reset: bool
    blocked: bool
    message: str
    error: Optional[str] = None
    ran_git_clean: bool = False
    git_clean_removed: List[str] = field(default_factory=list)
    ran_extra_clean: bool = False
    extra_removed: List[str] = field(default_factory=list)

    def as_dict(self):  # convenience
        return asdict(self)


def _run(cmd, cwd: Path):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def discover_repo(
    override: Optional[str | Path] = None,
    candidate_names: Iterable[str] = ("applied_groundwater_modelling.git", "applied_groundwater_modelling"),
) -> Optional[Path]:
    """Attempt to locate the repository root directory.

    Strategy:
      1. Explicit override (absolute or ~ path)
      2. Candidate names under $HOME
      3. git rev-parse from current working directory
      4. Upward directory walk looking for a .git folder
    """
    if override:
        p = Path(override).expanduser().resolve()
        if p.exists():
            return p
        else:
            print(f"[WARN] REPO_PATH_OVERRIDE '{p}' does not exist.")

    # Home directory candidates
    for name in candidate_names:
        c = (Path.home() / name).expanduser()
        if c.exists():
            return c

    # git rev-parse
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        if rev.returncode == 0:
            top = Path(rev.stdout.strip())
            if (top / ".git").exists():
                return top
    except Exception:
        pass

    # Upward walk
    try:
        here = Path.cwd()
        for parent in [here, *here.parents]:
            if (parent / ".git").exists():
                return parent
    except Exception:
        pass

    return None


def _safe_remove(root: Path, p: Path, removed: List[str]):
    """Remove file or directory under root if it's inside the repo (safety check)."""
    try:
        p = p.resolve()
        root = root.resolve()
        if not str(p).startswith(str(root)):
            return
        if (root / '.git') in [p, *p.parents]:
            # never touch .git
            return
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except IsADirectoryError:
                shutil.rmtree(p, ignore_errors=True)
        removed.append(str(p.relative_to(root)))
    except Exception:
        # swallow individual errors to continue
        pass


def _glob_find(root: Path, pattern: str) -> List[Path]:
    # Glob relative to root; support **
    pattern = pattern.strip()
    if not pattern:
        return []
    # Deny path traversal patterns proactively
    if '..' in pattern.split('/'):
        return []
    # Use glob with recursive
    return [Path(p) for p in glob.glob(str(root / pattern), recursive=True)]


def sync_repository(
    force_reset: bool = False,
    allow_local_reset: bool = False,
    dry_run: bool = False,
    repo_path_override: Optional[str | Path] = None,
    target_remote: str = "origin",
    target_branch: str = "course_2025",
    clean: bool = True,
    verbose: bool = True,
    # New options expected by 0_sync_repo.ipynb
    deep_clean: bool = False,
    deep_clean_include_ignored: bool = False,
    deep_clean_extra: Optional[List[str]] = None,
) -> RepoSyncResult:
    """Synchronize repository with remote target.

    Parameters
    ----------
    force_reset : bool
        Perform destructive reset even if local changes exist.
    allow_local_reset : bool
        Permit destructive reset outside JupyterHub (safety off locally).
    dry_run : bool
        If True, never perform destructive actions; only report.
    repo_path_override : str | Path | None
        Explicit path to repository root.
    target_remote : str
        Remote name (default 'origin').
    target_branch : str
        Branch to align with (default 'course_2025').
    clean : bool
        Whether to run `git clean` after successful reset (legacy alias).
    verbose : bool
        Print progress messages.
    deep_clean : bool
        If True, run a deeper clean step after reset. Equivalent to `git clean -fd`,
        or `-fdx` when deep_clean_include_ignored is True.
    deep_clean_include_ignored : bool
        If True and deep_clean is enabled, include git-ignored files (`-x`).
    deep_clean_extra : list[str] | None
        Additional glob patterns (relative to repo root) to remove after git clean,
        e.g., ['outputs/**', 'data/tmp/*'].
    Returns
    -------
    RepoSyncResult
        Structured result object.
    """
    repo_path = discover_repo(repo_path_override)
    is_jupyterhub = any(k.startswith("JUPYTERHUB_") for k in os.environ)

    if repo_path is None:
        msg = "No repository found (override/candidates/git rev-parse/all parents failed)."
        if verbose:
            print("[WARN]", msg)
        return RepoSyncResult(None, is_jupyterhub, [], False, True, msg)

    if verbose:
        print(f"[ENV] JupyterHub detected: {is_jupyterhub}")
        print(f"[INFO] Using repository: {repo_path}")
        print("[STEP] Fetch latest remote refs...")

    fetch_res = _run(["git", "fetch", target_remote], repo_path)
    if fetch_res.returncode != 0:
        err = f"git fetch failed: {fetch_res.stderr.strip()}"
        if verbose:
            print("[ERROR]", err)
        return RepoSyncResult(str(repo_path), is_jupyterhub, [], False, True, "Fetch failed", err)

    if verbose:
        print("[STEP] Checking status...")
    status_res = _run(["git", "status", "--porcelain"], repo_path)
    changed = [l for l in status_res.stdout.strip().splitlines() if l.strip()]

    if changed and verbose:
        print("\n[WARNING] Local (uncommitted or untracked) changes detected.")
        for c in changed:
            print("   ", c)
        guidance = """
You have local work in the teaching repository.
If you want to keep it, copy the changed files NOW to a personal directory, e.g.:
    mkdir -p ~/own_model_files
    cp <file_you_care_about> ~/own_model_files/
Then re-run with appropriate flags (force_reset / allow_local_reset) if you intend to discard changes.
        """
        print(textwrap.dedent(guidance))

    # Block if changed and not forcing
    if changed and not force_reset:
        return RepoSyncResult(str(repo_path), is_jupyterhub, changed, False, True, "Blocked: local changes present and force_reset is False")

    # Block locally if not allowed
    if not is_jupyterhub and not allow_local_reset:
        if verbose:
            print("[SAFE MODE] Not on JupyterHub; destructive reset disabled (allow_local_reset=False).")
        return RepoSyncResult(str(repo_path), is_jupyterhub, changed, False, True, "Blocked: local reset not allowed")

    if dry_run:
        if verbose:
            print("[DRY RUN] Would perform hard reset and optional clean, but dry_run=True.")
        return RepoSyncResult(str(repo_path), is_jupyterhub, changed, False, False, "Dry run only – no changes made")

    # Perform reset
    if verbose:
        print(f"[STEP] Hard resetting to {target_remote}/{target_branch} ...")
    reset_res = _run(["git", "reset", "--hard", f"{target_remote}/{target_branch}"], repo_path)
    if reset_res.returncode != 0:
        err = f"git reset failed: {reset_res.stderr.strip()}"
        if verbose:
            print("[ERROR]", err)
        return RepoSyncResult(str(repo_path), is_jupyterhub, changed, False, True, "Reset failed", err)
    if verbose and reset_res.stdout.strip():
        print(reset_res.stdout.strip())

    # Determine cleaning mode
    result = RepoSyncResult(str(repo_path), is_jupyterhub, changed, True, False, "Reset completed successfully")

    # Legacy clean behaviour
    if clean and not deep_clean:
        clean_res = _run(["git", "clean", "-fd"], repo_path)
        result.ran_git_clean = (clean_res.returncode == 0)
        if verbose and clean_res.returncode == 0:
            print("[STEP] Removed untracked files (if any).")

    # New deep clean behaviour
    if deep_clean:
        flags = ["git", "clean", "-f", "-d"]
        if deep_clean_include_ignored:
            flags.append("-x")
        if verbose:
            print(f"[STEP] Deep clean via: {' '.join(flags)}")
        # First do a preview to capture what will be removed
        preview_flags = flags + ["-n"]
        preview = _run(preview_flags, repo_path)
        removed_preview = []
        for line in preview.stdout.splitlines():
            line = line.strip()
            # git clean -n prints "Would remove path"
            m = re.match(r"Would remove (.+)", line)
            if m:
                removed_preview.append(m.group(1).strip())
        # Now perform the actual clean
        clean_exec = _run(flags, repo_path)
        result.ran_git_clean = (clean_exec.returncode == 0)
        if result.ran_git_clean:
            # Try to capture actual removed lines too
            actual_removed = []
            for line in clean_exec.stdout.splitlines():
                line = line.strip()
                m = re.match(r"Removing (.+)", line)
                if m:
                    actual_removed.append(m.group(1).strip())
            result.git_clean_removed = actual_removed or removed_preview
        if verbose:
            print(f"[STEP] Deep clean completed. Items: {len(result.git_clean_removed)}")

        # Extra pattern removal
        if deep_clean_extra:
            if verbose:
                print("[STEP] Removing extra patterns: ", ", ".join(deep_clean_extra))
            removed_extra: List[str] = []
            for pat in deep_clean_extra:
                for match in _glob_find(repo_path, pat):
                    _safe_remove(repo_path, match, removed_extra)
            result.ran_extra_clean = True
            result.extra_removed = removed_extra
            if verbose:
                print(f"[STEP] Extra patterns removed: {len(removed_extra)}")

    if verbose:
        print("\n[OK] Repository now matches remote branch.")

    return result


def print_sync_summary(result: RepoSyncResult):
    """Pretty-print a summary block for a RepoSyncResult."""
    print("\n=== SYNC SUMMARY ===")
    for k, v in result.as_dict().items():
        if k == "changed_files" and v:
            print(f"{k}:")
            for cf in v:
                print("   ", cf)
        elif k in ("git_clean_removed", "extra_removed") and v:
            print(f"{k} ({len(v)}):")
            for item in v[:50]:  # cap verbosity
                print("   ", item)
            if len(v) > 50:
                print(f"   ... (+{len(v)-50} more)")
        else:
            print(f"{k}: {v}")
