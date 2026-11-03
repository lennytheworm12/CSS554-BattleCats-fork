# Fresh home coordinates for returning workers

Main's king writes its X/Y location, but workers only remember kings they have
seen. A distant carrier can keep heading toward the old location after its
king evades a cat. A newborn can also spend turns scanning for a king behind it.

This feature lets workers read a fresh home location when they have no locally
verified king. It is extracted from the complete Sprint 2 bot without changing
the collection threshold, navigation, evasion scoring or spawn budget. Food
management and combat can build on this signal in later PRs.

## Read the code in this order

1. `KingSignal.publish`: the king calls it at the end of `RatKing.takeTurn`,
   after evasion and spawning, so the message describes its final location.
2. `KingSignal.read`: validate the timestamp and map bounds. If the published
   tile is visible, require a friendly king there and use its current center.
3. `BabyRat.rememberKing`: retain the existing local king checks first, then
   accept a valid publication when no local king was verified. The existing
   return route and transfer code use that location.

`KingSignal` owns shared slots **0 = X, 1 = Y, 2 = timestamp**. Future features
must allocate other slots. Engine 1.2.6 permits only kings to write shared
memory; workers only read. This protocol assumes the current single-king bot,
not multiple independently publishing kings.

## Protocol and policy choices

Shared values must be between 0 and 1023 (engine rule). The timestamp is
`round / 2 + 1`, using integer division. Two-round buckets fit the engine's
2,000-round game; zero marks an unpublished message, including at map origin.

The maximum accepted decoded age is **3 rounds**, an experimental freshness
window inherited from the full bot. Because the timestamp rounds down to an
even round, actual accepted age is at most 3 rounds for an even publication
and 2 for an odd one. Future timestamps and older messages are rejected.

The publisher clears the timestamp before writing X/Y, then publishes the new
timestamp last. An interrupted writer leaves either its previous complete
message or no published message. A reader also discards its result if its
engine round changes during the read, including local validation. This guards
against a bytecode pause that spans a later king publication. The read is
bounded and does not retry within the turn.

An invalid or stale message does **not** erase a previously remembered home
outside vision. That existing fallback remains until local evidence disproves
it or a valid new message replaces it. A worker with no known home retains the
existing bounded scan behavior. Freshness is evidence of recent publication,
not a guarantee the king remains alive or stationary after publication.

## Test and try it

With JDK 21, run from the repository root:

```powershell
.\gradlew.bat clean test verify
.\gradlew.bat run
```

Use `./gradlew` on macOS/Linux. Unit tests cover remote delivery, a moving home,
local sightings taking priority, stale-message fallbacks, timestamp/map bounds,
king publication after evasion, and interrupted readers/writers with recovery.
These scenario worlds exercise public methods; engine matches separately
check the assembled bot. Reports are at `build/reports/tests/test/index.html`.

The two remote-delivery scenarios failed before wiring in this feature. The
two reader-interruption scenarios also failed against the earlier full-bot
protocol before adding the round guard. No retries, food policy, bites, traps,
PvP or scouting changes are bundled with this extraction.

## Isolated comparison - November 2, 2026

- Tested candidate: `d66075361eca250e13a3187557e9e5ed91b521ca`.
- Recorded team-main baseline: `fc3b3ed27439f6844e770dada8302ea9800360ef`.
- JDK 21, engine 1.2.6; DefaultSmall, DefaultMedium, DefaultLarge,
  cheesefarm, minimaze, safelycontained and pipes, both starting sides and
  one fixed seed per map. All **14/14 games completed**.
- Clean **37 tests** pass (36 team scenarios and one example test), as does
  the engine verifier. Later evidence commits leave the tested bot unchanged.

Before publication, main advanced to `6f1d01e6b7df5ecc905478456e8492477ce510a4`
by merging coverage PR #10. This branch includes that merge. Main's bot code
and tests are identical to the recorded baseline; the candidate's bot code
and tests are identical to the tested candidate. The 14 games below are
historical results against the recorded revision, not a new simulation after
the coverage merge. A fresh clean `test jacocoTestReport
jacocoTestCoverageVerification verify` passes all 37 tests, the 21% gate and
engine verification: **217/239 production lines covered (90.79%)**.

| Measurement | Home signal | Main |
| --- | ---: | ---: |
| Wins | 10 | 4 |
| Deliveries at actual match ends | 100,500 | 57,600 |
| Deliveries at round 1,000 (10 games reach it) | 54,980 | 32,080 |

Five outcomes are coin flips: this bot wins three and main wins two. Excluding
those outcomes, the result is **7-2**. Main still wins DefaultLarge-A by king
destruction and minimaze-A on points; minimaze-A deliveries are 3,760 / 3,840.
Both pipes games end at round 155 with zero deliveries, so their coin-flip wins
do not demonstrate a collection benefit.

The fixed-round delivery gain is **71.4%** in the ten-game round-1,000 cohort.
Actual-end totals combine different match lengths. These controlled results
support better home guidance against this recorded main, not a general win
rate or proof of economic strength against the stronger opponent pool. That
pool was not rerun for this extraction. King food and spending policies are
still the baseline policies.

All recorded replay checkpoints are cooperative. These sampled states do not
establish behavior after a PvP transition or against combat-enabled opponents.

A local replay audit records zero candidate exception deaths and zero turns
at or above the applicable unit bytecode limit; the maximum recorded candidate
turn uses 5,594 bytecodes. This is a budget check, not a before/after performance
claim. All 28 log/replay hashes match the run manifest.

The [per-game CSV](king-home-signal-results.csv) records both sides' final
metrics and seeds. Source/JAR hashes, raw checkpoint CSV, logs, replays and the
auxiliary audit remain locally in `matches/sprint2-fresh-home-20261102/`;
generated files are not part of a clone. The full checkpoint CSV has SHA-256
`f90a9630ed1f54a7bc055363e79745b32e1e043577bea7d2a68bfcb82babf60f`.

To repeat with JDK 21 and Python 3.10+:

```powershell
.\gradlew.bat sim -PsimPreset=full -PsimCandidate=d66075361eca250e13a3187557e9e5ed91b521ca -PsimBaseline=fc3b3ed27439f6844e770dada8302ea9800360ef -PsimOffline=true
```
