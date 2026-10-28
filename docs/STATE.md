# SQLite state location

Construction source only; runtime behavior is unverified.

`freightrec.state_policy.validate_state_path(path, *, forbidden_roots=()) -> Path`
is the single shared validator. It returns a resolved path or raises ValueError.
Constructors call it before opening SQLite and use the returned path. Supply other
known source/product checkout roots as absolute paths in `forbidden_roots`; this
module always excludes its own source checkout, derived from its file location.
It creates no file or directory and reads no environment or credentials.

Use an absolute local ordinary path, for example `C:\freightrec-state\review.db`.
OneDrive and `OneDrive - <organization>` folder components are refused both before
and after path resolution. Relative paths, `:memory:`, SQLite URI strings, UNC,
Win32 device/extended paths, alternate data streams and nonordinary Windows
components are refused. Existing targets must be regular files. Missing parent
directories are permitted only below a resolvable existing directory; callers own
subsequent directory setup. Dangling links, resolution loops, permission failures
and invalid forbidden roots refuse. Native pathlib resolves existing symlink and
junction ancestors before containment checks; no filesystem scans occur.

A bounded GetDriveTypeW call checks only the supplied Windows drive root and
refuses remote, unknown, missing-root or unavailable results. It does not prove
SQLite writability on local media.

This policy targets native Windows ordinary local paths; native POSIX absolute
paths can also be validated by the same source. It does not identify cloud folders renamed away from OneDrive, POSIX mount-backed remote
filesystems or concurrent path replacement. It is a storage-placement guard,
not an atomic open or authorization boundary. Callers must avoid adversarial
path mutation between validation and SQLite open.

Deferred validation: Windows symlink/junction aliases and escape attempts, UNC and
reserved-name behavior, dangling links/loops, permissions, mapped drives, missing
parents and actual SQLite integration. No imports, tests or database creation ran
under Dirty Mode. Other checkout roots require caller-provided knowledge.
