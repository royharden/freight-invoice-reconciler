"""Validate local SQLite file locations without opening or creating state."""
from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
import stat
from typing import Iterable


_SOURCE_ROOT = Path(__file__).parent.parent.parent


def _ordinary_absolute(value: object) -> Path:
    try:
        raw = os.fspath(value)
    except TypeError as exc:
        raise ValueError("state location must be an absolute filesystem path") from exc
    if not isinstance(raw, str) or not raw or any(ord(c) < 32 for c in raw):
        raise ValueError("state location must be a nonempty ordinary path")
    # Exclude UNC, Win32 device/extended namespaces and POSIX double-slash roots.
    if raw.startswith(("\\\\", "//")):
        raise ValueError("state must use a local ordinary filesystem path")
    windows = PureWindowsPath(raw)
    if windows.drive.startswith("\\") or ":" in raw[len(windows.drive):]:
        raise ValueError("SQLite URI, device and stream paths are not state files")
    path = Path(raw)
    if not path.is_absolute():
        raise ValueError("state location must be absolute")
    if os.name == "nt":
        _require_local_windows_drive(path)
        for part in path.parts[1:]:
            if part in (".", ".."):
                continue
            if part.endswith((" ", ".")) or any(c in part for c in '<>"|?*'):
                raise ValueError("state location contains a nonordinary Windows component")
            if PureWindowsPath(part).is_reserved():
                raise ValueError("state location contains a reserved Windows name")
    return path


def _require_local_windows_drive(path: Path) -> None:
    # Query only this drive root; no enumeration, credentials or environment.
    # DRIVE_UNKNOWN/NO_ROOT_DIR/REMOTE fail closed. Local removable/fixed/CD/RAM
    # media pass placement only; SQLite permission/writability is not proved.
    import ctypes
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        drive_type = kernel.GetDriveTypeW
        drive_type.argtypes = [ctypes.c_wchar_p]
        drive_type.restype = ctypes.c_uint
        kind = drive_type(path.anchor)
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        raise ValueError("local Windows drive status is unavailable") from exc
    if kind not in (2, 3, 5, 6):
        raise ValueError("state requires a known local Windows drive")


def _resolve_existing_ancestors(path: Path) -> Path:
    """Resolve the nearest existing ancestor strictly, preserving missing suffix."""
    cursor = path
    while True:
        try:
            cursor.lstat()
            break
        except FileNotFoundError:
            parent = cursor.parent
            if parent == cursor:
                raise ValueError("state path has no resolvable existing ancestor")
            cursor = parent
    # lstat notices dangling links; strict resolve then refuses them rather than
    # treating them as missing normal directories. Junctions use native Path APIs.
    resolved = cursor.resolve(strict=True)
    suffix = path.relative_to(cursor)
    if suffix.parts and not resolved.is_dir():
        raise ValueError("state ancestor is not a directory")
    return resolved.joinpath(suffix).resolve(strict=False)


def _onedrive(path: Path) -> bool:
    return any(part.casefold() == "onedrive" or part.casefold().startswith("onedrive - ")
               for part in path.parts)


def _within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def validate_state_path(path, *, forbidden_roots: Iterable = ()) -> Path:
    """Return a resolved local file path outside OneDrive and source checkouts.

    Raise ValueError on invalid/unavailable resolution. No environment variables
    are read and no file/directory/database is opened or created. Callers supply
    any other checkout roots that cannot be derived from this module location.
    """
    try:
        candidate = _ordinary_absolute(path)
        if _onedrive(candidate):
            raise ValueError("SQLite state must be outside OneDrive")
        resolved = _ordinary_absolute(str(_resolve_existing_ancestors(candidate)))
        if _onedrive(resolved):
            raise ValueError("SQLite state must be outside OneDrive")
        if isinstance(forbidden_roots, (str, bytes, os.PathLike)):
            raise ValueError("forbidden_roots must be a collection of absolute roots")
        roots = [_SOURCE_ROOT, *forbidden_roots]
        for raw_root in roots:
            root = _resolve_existing_ancestors(_ordinary_absolute(raw_root))
            # Check both lexical and resolved paths, so '..' or links cannot
            # disguise containment and a checkout link cannot become state.
            if _within(candidate, _ordinary_absolute(raw_root)) or _within(resolved, root):
                raise ValueError("SQLite state must be outside source checkouts")
        try:
            mode = resolved.stat().st_mode
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(mode):
                raise ValueError("state target must be an ordinary file")
        return resolved
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid SQLite state location: {exc}") from exc
