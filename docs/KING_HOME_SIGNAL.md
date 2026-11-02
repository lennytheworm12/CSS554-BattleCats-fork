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
