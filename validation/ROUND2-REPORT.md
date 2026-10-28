# Round 2 native validation â€” builder evidence

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

## Isolated PDF worker â€” later source and actual checks

DL2 candidate294e7d530cb052a7fa14032e2ad895f96b5de981 adds a fixed owned parser process, parent wall deadline including startup, bounded request/stdout/stderr and strict result protocol, and required OS guards before parser import. Windows uses queried own-process Job limits; Linux uses verified address-space/CPU limits. No unsafe parent fallback or shell/user command hook. Profile is a new immutable pdfplumber-<version>-isolated-v2 edition. This does not provide a complete malicious-code/OS sandbox or hard real-time scheduling guarantee.

Owner source/ingestion scope passed83distinct tests plus one affected-case repeat, with Medium0047 source review PASS. Its prior malformed-protocol classification timeout is retained; only that framing-control test allowance changed15s, productiondefault5s and actual1s parent-kill control stayed unchanged. INT merged sourceb7166da20bfb304c5aeabf3caae1b7112727a944 and ran the full native suite: **329passed/0fail/0skip**,33.47s, artifact runtime-state/INT-pdf-final-fe9f99c10a00496eae76b50b390b6fbe.

Linux verification retained two additional negative setup observations at the SAME source, test assertions and default5s limit:

- Windows-bind Linux venv:323pass/1fail/5Windows-only skips. The first owned valid worker exceeded its parent deadline and was correctly killed. Artifact runtime-state/INT-linux-pdf-final-9844a7b8e49c4744b8d7e67e2e8000f6. Cold bind-filesystem startup cost is plausible, not a general causal/performance proof.
- First staged local venv:317pass/1fail/11skip and6dependency-import warnings; native extensions could not map from that app mount. Artifact runtime-state/INT-linux-pdf-localfs-7ff048fa1a4d45448c1cab637798329b. This is a failed setup/run, not a qualified six-test dependency omission.

Corrected setup explicitly enabled executable native-library mappings on the APP tmpfs and required a successful pdfplumber0.11.10 dependency preflight. The existing pinned Linux venv was copied to /app/.venv, no new download/install or source/test/default-limit change. **324passed/5Windows-only skips/0fail**,45.45s, sourceb7166da, same cached image, network NONE. Artifact runtime-state/INT-linux-pdf-execfs-ccc136fab77e43a6b67b19c25394b24a; staging script digest6887b92ed956968a24bc6d12e60785b903d16af3d34fb0b2642ec3a9c032c455. The Windows-only cases passed natively. This qualifies the stated environment/checks, not every cold/slow filesystem or host load. Resource bounds may safely refuse a valid PDF that exceeds its selected deadline.

All own containers are absent and m13freight/pdfguard released; source/venvs/artifacts remain. No named volumes, host ports, pulls, external model calls or credential use. Selected controlled worker kill/overflow and guard-before-parser behavior executed on both platforms; destructive resource exhaustion/broad hostile-PDF qualification remains unexecuted.

## Original PDF CLI bridge â€” later revision

DL4 candidate121fc3677bc3c3a188704d6d48627f06b40137e7 adds canonical bundles.py hydration: original JSON strings remain compatible; invoice descriptors must contain exactly media_type/template_id/data_base64, with strict canonical base64 and size/type bounds. Actual guarded extraction and SAME resolver bind raw PDF SHA/profile/pages/quotes to typed invoice fields. No caller evidence/verified hook, reconstructed JSON original or guard relaxation. Stateful hydration failures still retire prior contexts before refusal.

Owner final affected scope62passed across two commands, with the rehashed descriptor+field_values bypass reproduced as4failures before a High repair/review closure. Old JSON recording remains compatible; PDF frozen recording is explicitly unsupported in that version and all consumers fail closed. This was an allowed bounded-scope choice, not an unsupported benchmark pass.

ONE owner actual native CLI module report at candidate121fc36 exited0/stderr0; three findings and69PDF pointer occurrences resolved against original961byte builder PDF SHA34d575ccb33b2efe1ed046baed4ffffaeb5c1ffb082e81c9895180f4c2a4c198, profilepdfplumber-0.11.10-isolated-v2. Root runtime-state/DL4-pdf-process-e91d23a362f44658b9f11e8a11ac5ced retains original bytes/report/raw streams/receipt. No review actor or approved draft.

INT integrated5d831a56534aaddfe60bcf4d5a8eecc0ff0b81ff and executed complete native suite: **375passed/0fail/0skip**,48.46s, runtime-state/INT-pdf-cli-076362f0ea644bfbaac1e338280e1029. No current-revision Linux bridge result is inferred from the earlier guarded-parser Linux run.

## Historical remaining source path before final v2

DL4 now owns a separate P8 follow-up for explicit versioned original-PDF frozen observation capture/replay across the same A0/A1/A2 observations, preserving strict old JSON format validation and keeping reference labels outside product replay. That future source is not covered by the results above. Independent role endpoints and corpus/human/live gates remain pending; no benchmark claim follows from these builder checks.


## Final selected builder validation — 2026-10-28

DL4 original-observation v2 candidate a32a71c845d8a7c4dde210639bfa12fbcb0599ae accepted and merged at ae415e13b6486123d9d2ebead8b03a1f31600f0f. Explicit freeze_original_bundle_recording uses freightrec-observation-v2-originals with exact original PDF/JSON bytes, canonical guarded hydration, central source/runtime edition checks and detached product input. Legacy v1 JSON remains compatible and refuses PDF. Nested metadata-label leakage found by Medium0053 was repaired; fresh High0055 PASS covered64 targeted cases. Owner128new+22oldPDF+6JSON, repaired59 and reviewer64 are separately attributed overlapping checks, not a final expanded-suite total.

INT final full suite at the merged source: **559passed/0fail/0skip native Windows**,164.52s, Python3.12.13; **554passed/0fail/5Windows-only skips offline Linux**,234.27s. Native artifact runtime-state/INT-observations-final-e0b3c6a11db5461baa4fbfc0149739f2; Linux artifact runtime-state/INT-linux-final-v2-757517f61de3458c8c8abe966c3e167e. These are builder regressions, not independent benchmark evidence. Linux used the same cached image sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 and existing pinned venv staged on exec-enabled app tmpfs with mandatory pdfplumber preflight. Default worker5s unchanged; no network, pulls, host ports, privileged mode, credential/home/socket mount or named volume. Earlier failed attempts remain recorded above. Own final container verified absent with14.85GiB free RAM; m13freight/finalv2 claim released. No other container stopped.

Fresh wheel built offline with pinned setuptools80.9.0/wheel0.45.1; source4df042facf064db160a2de4bc8fccd1db0211169 adds ignore metadata only beyond tested ae415e1. Wheel freight_invoice_reconciler-0.1.0-py3-none-any.whl SHA256 ac83aa1aaa3753625e48b85d6445e4e755ecc6988f4975f743316dae650ef761. Fresh OUTER .venv-wheel-round2 installed hash-locked dependencies and own wheel OFFLINE. Outside-checkout isolated import verified installed site-packages and evaluation absent. Installed freightrec.exe status and original-PDF report each exit0/stderr0. Three findings and69PDF pointer occurrences verified against original SHA34d575ccb33b2efe1ed046baed4ffffaeb5c1ffb082e81c9895180f4c2a4c198. No human-approved draft. Artifact runtime-state/INT-wheel-final-d728b2dede4f4c169a46c2462334b564/smoke/receipt-corrected.json pins commands/raw hashes. Initial proof HELPER failed because it concatenated three separate JSON pre blocks; corrected per-block parser passed against SAME unchanged report. Negative helper/raw streams retained; successful installed report was not rerun or overwritten.

Selected implementation grants are exhausted; all DLs AVAILABLE with no active new source grant. Dirty Mode remains active with explicit ROUND2 local-runtime relaxation until Roy closes it. Independent nonlineage authors/oracle/custodian/auditor endpoints, untouched independent corpora/custody, actual human sessions, admission, broad hostile/security/load qualification and live model campaign remain pending. Current INT/DLs/descendants cannot fill independent roles. No SKIP_M13, release, scientific accuracy/savings or human-independent claim. A3/Jev not_run; A4 not_run_guardrail. No key/account/endpoint supplied, no credential files read, no remotes/push/publication. Actual testing spendUSD0.00 of cumulativeUSD40 ceiling; no midnight reset; placeholder inventory unchanged. Preserve all branches/worktrees/venvs/artifacts.
