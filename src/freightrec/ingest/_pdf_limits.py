"""Required resource limits for a dedicated PDF worker, never its parent.

The worker calls ``establish_limits`` before importing or invoking a PDF parser.
These are per-process resource guards, not a security sandbox. Windows CPU time
is user time; the parent separately enforces elapsed wall time and output bounds.
"""

import os
import sys


MAX_MEMORY_BYTES = 512 * 1024 * 1024
MAX_CPU_SECONDS = 31


class ResourceGuardError(RuntimeError):
    """At least one required worker-local resource guard could not be installed."""


# A Windows job with KILL_ON_JOB_CLOSE must remain open for the worker's entire
# lifetime. These are raw Win32 handles; Python does not close them implicitly.
_WINDOWS_JOB_HANDLE = None
_ESTABLISHED = None
_REQUESTED = None


def establish_limits(memory_bytes: int, cpu_seconds: int) -> dict:
    """Limit only the current dedicated worker or refuse before PDF parsing.

    Call this in the newly created parse worker, never in the application,
    test runner or agent. Both memory and CPU guards are mandatory. Repeating
    the same request is harmless; changing an established guard is refused.
    """
    global _ESTABLISHED, _REQUESTED
    if (type(memory_bytes) is not int or not 0 < memory_bytes <= MAX_MEMORY_BYTES
            or type(cpu_seconds) is not int or not 0 < cpu_seconds <= MAX_CPU_SECONDS):
        raise ResourceGuardError("invalid_resource_limits")
    request = (memory_bytes, cpu_seconds)
    if _ESTABLISHED is not None:
        if request != _REQUESTED:
            raise ResourceGuardError("resource_guard_already_established")
        return dict(_ESTABLISHED)
    try:
        if os.name == "nt":
            result = _windows_limits(memory_bytes, cpu_seconds)
        elif sys.platform.startswith("linux"):
            result = _linux_limits(memory_bytes, cpu_seconds)
        else:
            raise ResourceGuardError("unsupported_resource_guard_platform")
    except ResourceGuardError:
        raise
    except Exception as exc:
        # Do not expose OS paths, inherited environment, or arbitrary exception
        # text through the worker's data protocol.
        raise ResourceGuardError("resource_guard_setup_failed") from exc
    _REQUESTED = request
    _ESTABLISHED = dict(result)
    return dict(result)


def _linux_limits(memory_bytes: int, cpu_seconds: int) -> dict:
    import resource

    if not hasattr(resource, "RLIMIT_AS") or not hasattr(resource, "RLIMIT_CPU"):
        raise ResourceGuardError("linux_resource_primitives_unavailable")

    def bounded_limit(resource_kind, requested):
        _, current_hard = resource.getrlimit(resource_kind)
        if current_hard == resource.RLIM_INFINITY:
            effective = requested
        elif type(current_hard) is int and current_hard >= 0:
            effective = min(requested, current_hard)
        else:
            raise ResourceGuardError("linux_resource_limit_unavailable")
        # A zero inherited hard cap cannot support an operational guarded parse.
        if effective <= 0:
            raise ResourceGuardError("linux_resource_limit_unavailable")
        resource.setrlimit(resource_kind, (effective, effective))
        actual_soft, actual_hard = resource.getrlimit(resource_kind)
        if actual_soft != effective or actual_hard != effective:
            raise ResourceGuardError("linux_resource_limit_not_applied")
        return effective

    # If the second operation fails, the first may already be more restrictive.
    # The caller must stop; it must never fall back to parsing after that failure.
    memory_limit = bounded_limit(resource.RLIMIT_AS, memory_bytes)
    cpu_limit = bounded_limit(resource.RLIMIT_CPU, cpu_seconds)
    return {"kind": "linux-rlimit", "memory_bytes": memory_limit,
            "cpu_seconds": cpu_limit}


def _windows_limits(memory_bytes: int, cpu_seconds: int) -> dict:
    import ctypes
    from ctypes import wintypes

    global _WINDOWS_JOB_HANDLE

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = (
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD))
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ResourceGuardError("windows_job_create_failed")
    assigned = False
    try:
        limits = EXTENDED_LIMIT_INFORMATION()
        # PROCESS_TIME, ACTIVE_PROCESS, PROCESS_MEMORY, KILL_ON_JOB_CLOSE.
        limits.BasicLimitInformation.LimitFlags = 0x00000002 | 0x00000008 | 0x00000100 | 0x00002000
        limits.BasicLimitInformation.PerProcessUserTimeLimit = cpu_seconds * 10_000_000
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = memory_bytes
        # JobObjectExtendedLimitInformation = 9. The kernel copies this buffer.
        if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ResourceGuardError("windows_job_limits_failed")
        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            raise ResourceGuardError("windows_job_assignment_failed")
        assigned = True
        _WINDOWS_JOB_HANDLE = job
        actual = EXTENDED_LIMIT_INFORMATION()
        returned = wintypes.DWORD()
        if not kernel32.QueryInformationJobObject(
                job, 9, ctypes.byref(actual), ctypes.sizeof(actual), ctypes.byref(returned)):
            raise ResourceGuardError("windows_job_verification_failed")
        if (returned.value != ctypes.sizeof(actual)
                or actual.BasicLimitInformation.LimitFlags & limits.BasicLimitInformation.LimitFlags
                != limits.BasicLimitInformation.LimitFlags
                or actual.BasicLimitInformation.PerProcessUserTimeLimit != cpu_seconds * 10_000_000
                or actual.BasicLimitInformation.ActiveProcessLimit != 1
                or actual.ProcessMemoryLimit != memory_bytes):
            raise ResourceGuardError("windows_job_limits_not_applied")
    finally:
        # Closing an assigned KILL_ON_JOB_CLOSE job here would kill this worker
        # before it could return the parse/refusal protocol. Keep it open until
        # process exit; close only a job that never acquired this worker.
        if not assigned:
            kernel32.CloseHandle(job)
    return {"kind": "windows-job", "memory_bytes": memory_bytes,
            "cpu_seconds": cpu_seconds, "process_limit": 1}
