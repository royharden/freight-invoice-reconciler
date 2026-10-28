"""PDF parsing runs only in an owned, bounded worker; no parent parser fallback."""

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Thread
from time import monotonic, sleep

MAX_BYTES = 8_000_000
MAX_REQUEST_BYTES = 10_670_000
MEMORY_BYTES = 512 * 1024 * 1024
STDERR_BYTES = 8_192
REFUSALS = frozenset({
    "invalid_pdf_limits", "source_byte_limit", "invalid_pdf_header",
    "pdf_adapter_unavailable", "pdf_parser_version_unavailable",
    "pdf_encryption_state_unavailable", "encrypted_pdf_refused", "page_limit",
    "unsupported_multipage_pdf", "pdf_native_text_required", "page_text_limit",
    "pdf_elapsed_limit", "malformed_pdf", "pdf_guard_unavailable",
    "pdf_resource_limit", "pdf_worker_request_invalid",
})


def _worker_command() -> list[str]:
    # Fixed current interpreter and checked-out sibling source; no caller path,
    # shell, editable-package lookup or inherited PYTHONPATH is consulted.
    return [sys.executable, "-I", "-B", "-u", str(Path(__file__).resolve().with_name("_pdf_worker.py"))]


def _worker_environment() -> dict[str, str]:
    # Windows' loader needs its system directory. Never copy the full environment
    # or look up credentials. POSIX needs no inherited application variables.
    return {"SystemRoot": os.environ.get("SystemRoot", r"C:\Windows")} if os.name == "nt" else {}


def _strict_result(raw: bytes, request: dict) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("pdf_worker_protocol_invalid")
            result[key] = value
        return result

    def reject_number(_):
        raise ValueError("pdf_worker_protocol_invalid")

    try:
        result = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=pairs,
                            parse_float=reject_number, parse_constant=reject_number)
        if type(result) is not dict:
            raise ValueError
        if result.get("status") == "refused":
            if set(result) != {"status", "reason_code"} or result["reason_code"] not in REFUSALS:
                raise ValueError
            raise _WorkerRefusal(result["reason_code"])
        if set(result) != {"status", "pages", "parser_profile", "guard"} or result["status"] != "ok":
            raise ValueError
        pages, guard = result["pages"], result["guard"]
        if (type(pages) is not list or len(pages) != 1 or type(pages[0]) is not str
                or not pages[0].strip() or len(pages[0]) > min(request["max_codepoints"], 200_000)):
            raise ValueError
        profile = result["parser_profile"]
        if type(profile) is not str or not re.fullmatch(r"pdfplumber-[A-Za-z0-9.+_-]{1,60}-isolated-v2", profile):
            raise ValueError
        if (type(guard) is not dict or not {"kind", "memory_bytes", "cpu_seconds"} <= set(guard)
                or set(guard) - {"kind", "memory_bytes", "cpu_seconds", "process_limit"}):
            raise ValueError
        expected_kind = "windows-job" if os.name == "nt" else "linux-rlimit"
        if guard["kind"] != expected_kind:
            raise ValueError
        for key, maximum in (("memory_bytes", MEMORY_BYTES), ("cpu_seconds", request["max_seconds"] + 1)):
            if type(guard[key]) is not int or not 0 < guard[key] <= maximum:
                raise ValueError
        if os.name == "nt" and (type(guard.get("process_limit")) is not int or guard["process_limit"] != 1):
            raise ValueError
        if "process_limit" in guard and (type(guard["process_limit"]) is not int or guard["process_limit"] != 1):
            raise ValueError
        return result
    except _WorkerRefusal as exc:
        raise ValueError(str(exc)) from exc
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise ValueError("pdf_worker_protocol_invalid") from exc


class _WorkerRefusal(Exception):
    pass


def _run_worker(request: dict, *, timeout_seconds: int, max_stdout_bytes: int) -> dict:
    if (type(timeout_seconds) is not int or not 0 < timeout_seconds <= 30
            or type(max_stdout_bytes) is not int or not 0 < max_stdout_bytes <= 1_204_096):
        raise ValueError("invalid_pdf_limits")
    payload = json.dumps(request, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("source_byte_limit")
    started = monotonic()
    try:
        worker = subprocess.Popen(_worker_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=_worker_environment(), close_fds=True,
                                  bufsize=0, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except OSError as exc:
        raise ValueError("pdf_worker_unavailable") from exc
    overflow, io_error = Event(), Event()
    stdout = bytearray()

    def read_stream(stream, limit, destination=None):
        count = 0
        try:
            while chunk := stream.read(16_384):
                count += len(chunk)
                if count > limit:
                    overflow.set()
                elif destination is not None:
                    destination.extend(chunk)
        except (OSError, ValueError):
            io_error.set()

    def write_request():
        try:
            view, offset = memoryview(payload), 0
            while offset < len(view):
                written = worker.stdin.write(view[offset:])
                if not written:
                    break
                offset += written
        except (OSError, ValueError):
            # A guard refusal may legitimately exit without reading the request.
            pass
        finally:
            try:
                worker.stdin.close()
            except (OSError, ValueError):
                pass

    threads = [Thread(target=read_stream, args=(worker.stdout, max_stdout_bytes, stdout), daemon=True),
               Thread(target=read_stream, args=(worker.stderr, STDERR_BYTES), daemon=True),
               Thread(target=write_request, daemon=True)]
    reason, started_threads = None, []
    try:
        for thread in threads:
            thread.start()
            started_threads.append(thread)
        while worker.poll() is None:
            if overflow.is_set():
                reason = "pdf_worker_output_limit"
                break
            if monotonic() - started >= timeout_seconds:
                reason = "pdf_elapsed_limit"
                break
            sleep(0.01)
        if reason is None and monotonic() - started >= timeout_seconds:
            reason = "pdf_elapsed_limit"
    except (OSError, RuntimeError):
        reason = "pdf_worker_io_error"
    finally:
        if worker.poll() is None:
            try:
                worker.kill()  # Only the process created above is ever terminated.
            except OSError:
                if worker.poll() is None:
                    reason = "pdf_worker_termination_failed"
        try:
            worker.wait(timeout=2)
        except subprocess.TimeoutExpired:
            reason = "pdf_worker_termination_failed"
        for thread in started_threads:
            thread.join(timeout=1)
        for stream in (worker.stdin, worker.stdout, worker.stderr):
            try:
                stream.close()
            except (OSError, ValueError):
                pass
    if reason is not None:
        raise ValueError(reason)
    if overflow.is_set():
        raise ValueError("pdf_worker_output_limit")
    if io_error.is_set() or any(thread.is_alive() for thread in threads):
        raise ValueError("pdf_worker_io_error")
    if worker.returncode != 0:
        raise ValueError("pdf_worker_failed")
    return _strict_result(bytes(stdout), request)


def extract_pdf_pages(raw_bytes: bytes, *, max_bytes: int = MAX_BYTES,
                      max_pages: int = 100, max_codepoints: int = 500_000,
                      max_seconds: int = 5) -> tuple[list[str], str]:
    limits = ((max_bytes, MAX_BYTES), (max_pages, 100), (max_codepoints, 500_000), (max_seconds, 30))
    if any(type(value) is not int or not 0 < value <= maximum for value, maximum in limits):
        raise ValueError("invalid_pdf_limits")
    if not isinstance(raw_bytes, bytes) or not 0 < len(raw_bytes) <= max_bytes:
        raise ValueError("source_byte_limit")
    if not raw_bytes.startswith(b"%PDF-"):
        raise ValueError("invalid_pdf_header")
    request = {"raw_pdf_b64": base64.b64encode(raw_bytes).decode("ascii"), "max_bytes": max_bytes,
               "max_pages": max_pages, "max_codepoints": max_codepoints, "max_seconds": max_seconds}
    result = _run_worker(request, timeout_seconds=max_seconds,
                         max_stdout_bytes=min(max_codepoints, 200_000) * 6 + 4096)
    return result["pages"], result["parser_profile"]
