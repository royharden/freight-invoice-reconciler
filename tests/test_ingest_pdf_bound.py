"""Builder-only PDF worker boundary regressions, not sandbox qualification.

what_bug_this_catches: an elapsed check after parsing is not a deadline, and a
worker's unchecked output must not become unbounded parent memory or evidence.
All controlled workers below are tiny, newly authored, trusted test scripts.
"""

import base64
import builtins
import io
import json
import os
from pathlib import Path
import sys
from time import monotonic

import pytest

from freightrec.ingest import pdftext
from test_ingest_round2 import INVOICE, _pdf


def _request(raw=None, seconds=5):
    raw = _pdf([INVOICE]) if raw is None else raw
    return {"raw_pdf_b64": base64.b64encode(raw).decode("ascii"),
            "max_bytes": 8_000_000, "max_pages": 100,
            "max_codepoints": 500_000, "max_seconds": seconds}


def _controlled_worker(monkeypatch, tmp_path, body):
    script = tmp_path / "owned_pdf_boundary_worker.py"
    script.write_text("import sys, time\nsys.stdin.buffer.read()\n" + body,
                      encoding="utf-8", newline="\n")
    monkeypatch.setattr(pdftext, "_worker_command",
                        lambda: [sys.executable, "-I", "-B", "-u", str(script)])
    return script


@pytest.fixture
def owned_processes(monkeypatch):
    """Capture and clean only the processes this exact test invocation creates."""
    created = []
    original = pdftext.subprocess.Popen

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        created.append((process, args, kwargs))
        return process

    monkeypatch.setattr(pdftext.subprocess, "Popen", spawn)
    yield created
    for process, _, _ in created:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)


def test_default_worker_is_own_source_with_required_resource_guard(owned_processes):
    """what_bug_this_catches: the default must parse in the owned guarded worker."""
    result = pdftext._run_worker(_request(), timeout_seconds=5, max_stdout_bytes=1_204_096)
    assert result["pages"] == [INVOICE]
    assert result["parser_profile"].endswith("-isolated-v2")
    guard = result["guard"]
    assert guard["kind"] == ("windows-job" if os.name == "nt" else "linux-rlimit")
    assert type(guard["memory_bytes"]) is int and 0 < guard["memory_bytes"] <= 536_870_912
    assert type(guard["cpu_seconds"]) is int and 0 < guard["cpu_seconds"] <= 6
    if os.name == "nt":
        assert guard["process_limit"] == 1
    assert len(owned_processes) == 1
    process, args, kwargs = owned_processes[0]
    command = args[0]
    assert Path(command[0]).resolve() == Path(sys.executable).resolve()
    assert all(flag in command for flag in ("-I", "-B", "-u"))
    assert Path(command[-1]).resolve() == Path(pdftext.__file__).with_name("_pdf_worker.py").resolve()
    assert not kwargs.get("shell", False)
    assert kwargs["env"] is not None
    assert set(kwargs["env"]) <= {"SystemRoot", "SYSTEMROOT", "LANG", "LC_ALL"}
    assert process.poll() is not None


def test_parent_deadline_actually_terminates_owned_blocked_worker(monkeypatch, tmp_path, owned_processes):
    """what_bug_this_catches: a parser blocked inside extraction must be killed."""
    _controlled_worker(monkeypatch, tmp_path, "time.sleep(10)\n")
    started = monotonic()
    with pytest.raises(ValueError, match="^pdf_elapsed_limit$"):
        pdftext.extract_pdf_pages(b"%PDF-1.4\nowned-boundary-control", max_seconds=1)
    elapsed = monotonic() - started
    assert 0.5 <= elapsed < 8, f"deadline returned after {elapsed:.3f}s"
    assert len(owned_processes) == 1
    assert owned_processes[0][0].poll() is not None


@pytest.mark.parametrize(("stream", "size"), [("stdout", 2_000_000), ("stderr", 32_768)])
def test_noisy_owned_worker_is_killed_on_bounded_output(monkeypatch, tmp_path, owned_processes, stream, size):
    """what_bug_this_catches: waiting/communicate can accumulate unlimited output."""
    _controlled_worker(monkeypatch, tmp_path,
                       f"sys.{stream}.buffer.write(b'x' * {size})\n"
                       f"sys.{stream}.buffer.flush()\ntime.sleep(10)\n")
    with pytest.raises(ValueError, match="^pdf_worker_output_limit$"):
        pdftext.extract_pdf_pages(b"%PDF-1.4\nowned-noise-control")
    assert len(owned_processes) == 1
    assert owned_processes[0][0].poll() is not None


_GUARD = {"kind": "windows-job" if os.name == "nt" else "linux-rlimit",
          "memory_bytes": 536_870_912, "cpu_seconds": 6,
          **({"process_limit": 1} if os.name == "nt" else {})}
_OK = {"status": "ok", "pages": ["native text"],
       "parser_profile": "pdfplumber-0.11.10-isolated-v2", "guard": _GUARD}


@pytest.mark.parametrize("payload", [
    b"not-json",
    b'{"status":"refused","reason_code":"pdf_guard_unavailable","extra":1}',
    b'{"status":"ok","status":"refused","reason_code":"pdf_guard_unavailable"}',
    json.dumps({**_OK, "pages": ["one", "two"]}).encode(),
    json.dumps({**_OK, "pages": [17]}).encode(),
    json.dumps({**_OK, "pages": [""]}).encode(),
    json.dumps({**_OK, "parser_profile": "arbitrary-profile"}).encode(),
    json.dumps({**_OK, "guard": {**_GUARD, "memory_bytes": True}}).encode(),
    json.dumps({**_OK, "guard": {**_GUARD, "cpu_seconds": 99}}).encode(),
    json.dumps({**_OK, "guard": {**_GUARD, "memory_bytes": float("nan")}}).encode(),
    json.dumps({**_OK, "untrusted": "extra"}).encode(),
])
def test_malformed_or_unqualified_worker_result_refuses(monkeypatch, tmp_path, payload):
    """what_bug_this_catches: worker text is data, never a trusted verified flag."""
    _controlled_worker(monkeypatch, tmp_path, f"sys.stdout.buffer.write({payload!r})\n")
    with pytest.raises(ValueError, match="^pdf_worker_protocol_invalid$"):
        # Protocol controls get scheduling slack; the separate deadline case
        # still proves actual parent termination with a one-second bound.
        pdftext.extract_pdf_pages(b"%PDF-1.4\nowned-protocol-control", max_seconds=15)


def test_worker_declared_guard_setup_refusal_is_preserved(monkeypatch, tmp_path):
    """what_bug_this_catches: unavailable mandatory guard cannot fall back in-process."""
    payload = b'{"status":"refused","reason_code":"pdf_guard_unavailable"}'
    _controlled_worker(monkeypatch, tmp_path, f"sys.stdout.buffer.write({payload!r})\n")
    with pytest.raises(ValueError, match="^pdf_guard_unavailable$"):
        pdftext.extract_pdf_pages(b"%PDF-1.4\nowned-guard-control")


def test_actual_worker_guard_failure_precedes_pdf_import(monkeypatch):
    """what_bug_this_catches: guard failure must stop before untrusted PDF parsing.

    The guard is replaced with a refusal here, so no process limit is applied to
    the pytest/parent process. No actual PDF parsing takes place in this unit case.
    """
    from freightrec.ingest import _pdf_worker as worker

    calls = []

    def refuse(memory_bytes, cpu_seconds):
        calls.append((memory_bytes, cpu_seconds))
        raise worker.ResourceGuardError("controlled guard setup failure")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "pdfplumber":
            pytest.fail("parser imported before failed mandatory guard")
        return original_import(name, *args, **kwargs)

    def forbidden_parse(*args, **kwargs):
        pytest.fail("PDF parse function called after mandatory guard failure")

    output_bytes = io.BytesIO()
    input_stream = io.TextIOWrapper(io.BytesIO(json.dumps(_request()).encode()), encoding="utf-8")
    output_stream = io.TextIOWrapper(output_bytes, encoding="utf-8", write_through=True)
    with monkeypatch.context() as local:
        local.setattr(worker, "establish_limits", refuse)
        local.setattr(worker, "parse_pdf", forbidden_parse)
        local.setattr(worker.sys, "stdin", input_stream)
        local.setattr(worker.sys, "stdout", output_stream)
        local.setattr(builtins, "__import__", guarded_import)
        worker.main()
        output_stream.flush()
        payload = json.loads(output_bytes.getvalue())
    assert calls == [(536_870_912, 6)]
    assert payload == {"status": "refused", "reason_code": "pdf_guard_unavailable"}
