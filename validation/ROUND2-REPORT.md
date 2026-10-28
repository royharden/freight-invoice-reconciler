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

Separate-process CLI journey and Linux Docker parity are in progress and are not claimed by the312-test native result. Native wheel dependencies are installed; product console-script installation/fresh-checkout packaging is not yet claimed. Docker must use an existing cached image, explicit resource ledger, no host ports or home/socket/credential mounts, no image pulls, and no test-network access. Memory must exceed3GiB before each Docker/install step; an earlier1.63GiB sample correctly deferred Docker. Later resource eligibility does not erase that deferral history.

Independent nonlineage authors/oracle/custodian/stand-in endpoints and actual human independence remain pending. No heldout campaign,10k-draw corpus inference, model quality, savings or accuracy number is established by these builder tests. A3/Jev remain not_run; A4 not_run_guardrail. No license/publication/remote/push approval. Detailed private placeholder inventory and cost ledger are outside the product tree in ROUND2-HANDOFF.md and TESTING-SPEND.json.
