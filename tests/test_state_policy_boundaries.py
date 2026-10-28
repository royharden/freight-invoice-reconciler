"""Builder-only storage regressions; all writable fixtures live in pytest tmp_path."""
import ctypes
from pathlib import Path
import sys

import pytest

from freightrec import state_policy


@pytest.mark.parametrize("value", [None, True, b"C:/state.db", "", "relative.db", ":memory:", "file:C:/state.db?mode=rwc", r"\\server\share\state.db", r"\\?\C:\state.db", "//server/share/state.db"])
def test_nonordinary_locations_refuse(value):
    """what_bug_this_catches: SQLite URI, relative or network location bypass."""
    with pytest.raises(ValueError):
        state_policy.validate_state_path(value)


@pytest.mark.parametrize("component", ["OneDrive", "onedrive", "OneDrive - Builder Org"])
def test_onedrive_components_refuse_without_creation(tmp_path, component):
    target = tmp_path / component / "state.db"
    with pytest.raises(ValueError, match="outside OneDrive"):
        state_policy.validate_state_path(target)
    assert not target.exists()


def test_own_checkout_and_explicit_source_roots_refuse(tmp_path, monkeypatch):
    """what_bug_this_catches: caller forgetting the module's own checkout root."""
    checkout = Path(state_policy.__file__).parents[2]
    # what_bug_this_catches: master can violate OneDrive and source policies;
    # refusal is required, but reason precedence must not depend on checkout root.
    with pytest.raises(ValueError, match="outside (source|OneDrive)"):
        state_policy.validate_state_path(checkout / "new-state.db")
    supplied = tmp_path / "other-source"
    supplied.mkdir()
    target = supplied / "nested" / "state.db"
    # Establish that this controlled path passes all non-source placement guards.
    assert state_policy.validate_state_path(target) == target.resolve()
    # Exercise automatic source exclusion outside OneDrive so its removal fails
    # even when the actual checkout above is already excluded by OneDrive.
    with monkeypatch.context() as patch:
        patch.setattr(state_policy, "_SOURCE_ROOT", supplied)
        with pytest.raises(ValueError, match="outside source"):
            state_policy.validate_state_path(target)
    with pytest.raises(ValueError, match="outside source"):
        state_policy.validate_state_path(target, forbidden_roots=(supplied,))
    assert not target.parent.exists()


def test_missing_local_file_is_resolved_without_state_creation(tmp_path):
    target = tmp_path / "new-parent" / "review.db"
    assert state_policy.validate_state_path(target) == tmp_path.resolve() / "new-parent" / "review.db"
    assert not target.parent.exists()
    assert not target.exists()


def test_existing_regular_file_preserved_and_directory_refused(tmp_path):
    target = tmp_path / "existing.db"
    target.write_bytes(b"builder sentinel, not an actual database")
    before = target.read_bytes()
    assert state_policy.validate_state_path(target) == target.resolve()
    assert target.read_bytes() == before
    with pytest.raises(ValueError, match="ordinary file"):
        state_policy.validate_state_path(tmp_path)


def test_stream_and_invalid_forbidden_root_refuse(tmp_path):
    with pytest.raises(ValueError):
        state_policy.validate_state_path(str(tmp_path / "review.db") + ":stream")
    with pytest.raises(ValueError):
        state_policy.validate_state_path(tmp_path / "review.db", forbidden_roots=("relative-root",))
    with pytest.raises(ValueError):
        state_policy.validate_state_path(tmp_path / "review.db", forbidden_roots=tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows drive API contract")
@pytest.mark.parametrize("kind", [0, 1, 4, 999])
def test_remote_unknown_and_unavailable_drive_types_refuse(tmp_path, monkeypatch, kind):
    """what_bug_this_catches: mapped drive accepted as a local letter path."""
    roots = []

    class DriveType:
        def __call__(self, anchor):
            roots.append(anchor)
            return kind

    class Kernel:
        GetDriveTypeW = DriveType()

    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: Kernel())
    with pytest.raises(ValueError, match="known local Windows drive"):
        state_policy.validate_state_path(tmp_path / "state.db")
    assert roots == [tmp_path.anchor]


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows DLL loading contract")
def test_drive_api_loading_failure_refuses(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("builder simulated API failure")

    monkeypatch.setattr(ctypes, "WinDLL", unavailable)
    with pytest.raises(ValueError, match="drive status is unavailable"):
        state_policy.validate_state_path(tmp_path / "state.db")


@pytest.mark.parametrize("destination", ["OneDrive", "source"])
def test_directory_symlink_cannot_hide_forbidden_ancestor(tmp_path, destination):
    """what_bug_this_catches: checking lexical path while target is forbidden."""
    target = tmp_path / destination
    target.mkdir()
    alias = tmp_path / "safe-alias"
    try:
        alias.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"local directory symlink capability unavailable: {exc}")
    roots = (target,) if destination == "source" else ()
    with pytest.raises(ValueError, match="outside (OneDrive|source)"):
        state_policy.validate_state_path(alias / "review.db", forbidden_roots=roots)
    assert not (target / "review.db").exists()


def test_dangling_symlink_refuses_instead_of_treating_target_as_missing(tmp_path):
    alias = tmp_path / "dangling"
    try:
        alias.symlink_to(tmp_path / "absent-parent", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"local directory symlink capability unavailable: {exc}")
    with pytest.raises(ValueError):
        state_policy.validate_state_path(alias / "review.db")
