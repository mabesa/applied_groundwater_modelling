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

from dataclasses import dataclass, asdict
from pathlib import Path
import os
import subprocess
import textwrap
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


def sync_repository(
    force_reset: bool = False,
    allow_local_reset: bool = False,
    dry_run: bool = False,
    repo_path_override: Optional[str | Path] = None,
    target_remote: str = "origin",
    target_branch: str = "course_2025",
    clean: bool = True,
    verbose: bool = True,
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
        Whether to run `git clean -fd` after successful reset.
    verbose : bool
        Print progress messages.

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

    if clean:
        clean_res = _run(["git", "clean", "-fd"], repo_path)
        if verbose and clean_res.returncode == 0:
            print("[STEP] Removed untracked files (if any).")

    if verbose:
        print("\n[OK] Repository now matches remote branch.")

    return RepoSyncResult(str(repo_path), is_jupyterhub, changed, True, False, "Reset completed successfully")


def print_sync_summary(result: RepoSyncResult):
    """Pretty-print a summary block for a RepoSyncResult."""
    print("\n=== SYNC SUMMARY ===")
    for k, v in result.as_dict().items():
        if k == "changed_files" and v:
            print(f"{k}:")
            for cf in v:
                print("   ", cf)
        else:
            print(f"{k}: {v}")
