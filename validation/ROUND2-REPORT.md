# Round 2 native validation — builder evidence

Python3.12.13, pytest8.4.2, hash-pinned dependency edition in requirements-round2.txt. Actual tests ran against each owner's preserved checkout, then together against local master. No live model/API usage, credential reads, public release or independent scientific campaign. Current app testing spendUSD0 of USD40 ceiling.

## Pinned native results

| Scope | Candidate | Actually observed result |
|---|---|---|
| DL1 money/pricing/time/state | 1b8b84682405842ae473d6ff124b3c7457d9a956 |103 passed, then affected pricing37 passed with one added node;104 distinct tests across commands |
| DL2 sources/ingestion/reconciliation |9fcaa7b206b8fa50796b0c86a6fa3b4b649f0997|Initial65pass/1fail exposed evidence ordering; repaired and final88pass/0fail/0skip |
| DL3 SQLite/review/links/draft |ffd3d97f269fd8ebf05e2aa166ffbe157851038e|40 passed/0fail/0skip, actual SQLite and inert files |
| DL4 CLI/evaluation/provider/ledger |dc98b5115230be81de12120366d17ed3797d9bc1|80 distinct passing cases across four scoped commands; no single80-test command claimed |
| INT combined master |f802e32eabf822e7559e4a7b0c4c09504682f86d|311 passed/1failed; actual checkout in OneDrive triggered a legitimate refusal reason different from test regex |
| DL1 portable refusal assertion |9eb51bbdfed32680427ff879a9770122c97d75e0|25 affected state-policy tests passed; controlled outside-OneDrive source checks retained |
| INT repaired combined master |8ed0ba73401bee157f3225c3649a12bfb8a1968a|**312 passed,0failures,0errors,0skips**, pytest22.02s, JUnit suite21.812s |

INT's exact combined command: shared Python -m pytest -p no:cacheprovider -q -ra tests --basetemp NEW_OUTSIDE_SOURCE_PATH/pytest --junitxml NEW_OUTSIDE_SOURCE_PATH/junit.xml. PYTHONPATH selected the actual master src plus root; plugin autoload and bytecode writes disabled. No reused diagnostic directory. Each lane's exact commands/interpreter/import paths/reviewer attribution are retained in the private run READY packets; these reports are not independently authenticated benchmark evidence.

Retained INT diagnostics outside source:

- Negative run: C:\Worktrees\PortfolioBuilder\freight-invoice-reconciler\runtime-state\INT-combined-47773c71f44943d0859ef77537f5eaa1 (pytest.log,junit.xml,receipt.json).
- Repaired run: C:\Worktrees\PortfolioBuilder\freight-invoice-reconciler\runtime-state\INT-combined-repaired-f2af35fe02e346d6962adac7902a2a5e (pytest.log,junit.xml,receipt.json).

The evidence-order fix canonicalizes complete exact pointer identities and changes policy revision; it preserves every required source proof. The assertion repair changes tests only: production storage guards remain unchanged. Historical failures were retained, not overwritten as passes. Owner reviewer results were scoped source/test reviews, not independent H/O/J/auditor roles.

## Limits and remaining execution

Actual native PDF controls used original tiny builder PDFs; no broad hostile-file or hard CPU/memory isolation guarantee. Path tests cover selected actual Windows/timezone/symlink behavior and mocked mapped-drive refusal, not every junction/permission/race case. SQLite threads and injected transaction failures are bounded regressions, not production load qualification. Human-labelled unit fixtures exercise attribution branches only; real human sessions/review minutes are unmeasured.

Separate-process and Linux observations are recorded below and remain distinct from the312-test native result. An earlier1.63GiB sample correctly deferred Docker. Later resource eligibility does not erase that deferral history.

Independent nonlineage authors/oracle/custodian/stand-in endpoints and actual human independence remain pending. No heldout campaign,10k-draw corpus inference, model quality, savings or accuracy number is established by these builder tests. A3/Jev remain not_run; A4 not_run_guardrail. No license/publication/remote/push approval. Detailed private placeholder inventory and cost ledger are outside the product tree in ROUND2-HANDOFF.md and TESTING-SPEND.json.

## Additional observed checks

- Native process runner f58ba0fa47c8cee023388ed45fdc5716e64674d2, application basef802e32: ONE run,18processes (17CLI),4expected refusals,0unexpected exits, no human-approved draft. DL4 retained/rehashed57artifacts and41application source hashes. Root: C:\Worktrees\PortfolioBuilder\freight-invoice-reconciler\runtime-state\DL4-process-journey-4e13927bbd97443e89cb6558738cbcbd. Raw stream capture was corrected before execution after review; no earlier journey attempt is hidden.
- Historical native bootstrap warning: the wrapper/preflight emitted missing _distutils_hack startup diagnostics while still exiting0. Those raw streams are preserved; the run is not called warning-free. A subsequent INT fresh bootstrap exited0 with empty stderr and setuptools80.9.0/wheel0.45.1/module present, recorded at runtime-state/INT-bootstrap-dc854a46af1b46bbbb62177dde00253c. Cause and broader stability are not inferred from that observation.
- Native packaging: hash-pinned setuptools80.9.0/wheel0.45.1 installed after RAM guard; app installed editable OFFLINE from own source, no dependency resolution/build isolation. Actual installed freightrec.exe status exited0 and reported pending admission/A3/A4/benchmark state. This is an editable-entrypoint smoke, not a wheel/release/deployment qualification.
- Linux suite: source62f16200d98a73553cf8482a850e1e3480655a52, cached Python3.12.13-slim image sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36. **307passed,5skipped,0failures** in17.36s; the five skips are explicitly native Windows drive/DLL controls exercised by native312. Root runtime-state/INT-linux-d0675a3817514d068a131b7f0ea85674. Suite forced packaged tzdata lookup; no generic all-date/all-platform timezone guarantee.
- Linux process journey: same source/image, ONE run18processes/17CLI, same4expected refusals,0unexpected exits, no human-approved draft. Root runtime-state/INT-linux-journey-4e7f65d5830747458773c312d3e78c27, nested journey/journey.json. Process environment intentionally restricted; this is the selected journey, not full production environment parity.

Both Linux executions used network NONE, read-only root/source/venv, nonroot user, capped memory/CPU/pids, tmpfs and only a project artifact mount. No home/socket/credential mount, privileged mode, host port, image pull, or named volume. Pinned public wheel setup was a separate permitted package-only network step, with RAM6.33GiB; tests6.40GiB/journey6.95GiB before launch. Own ephemeral containers are gone and m13freight/round2 claim released; worktree/venvs/artifacts retained. No other container was stopped.

## Remaining required source boundary

The PDF adapter at these tested revisions has cooperative elapsed checks and cannot interrupt a blocked parser. A dedicated bounded worker fix is assigned to DL2 under ROUND2-PDF-BOUND-r1; **not implemented/validated by the results above**. Later source changes need their affected evidence recorded separately. This is a material ingestion limit, not a reason to reinterpret already executed small builder tests as hard resource qualification.
