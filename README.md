# BattleCats — Battlecode 2026

Java bot for the course project, using **Battlecode engine 1.2.6** and the
scaffold's separately versioned **client 1.0.7**. Start development branches from
the latest `main` in the upstream team repository.

## Development workflow

Use the public team main as the reference and keep development branches local
or on your personal fork. The simulation mode fetches main without pushing any
branches. It uses upstream/main when configured, otherwise origin/main.

Read [ENGINEERING.md](ENGINEERING.md) for the shared engineering principles and
[CONTRIBUTING.md](CONTRIBUTING.md) for Java style, Battlecode guidance and
validation conventions for human and agent contributions. Codex uses
[AGENTS.md](AGENTS.md) to find this guidance; [CLAUDE.md](CLAUDE.md) imports the
same principles, workflow and guide for Claude Code.

For bot behavior changes, commit the candidate and run the full comparison with
`-PsimCandidate=HEAD`. Agent contributions also need a separate reviewer to
inspect the code and results before proposing a PR; human contributors can use
the PR for teammate review. Choose checks appropriate to other changes;
documentation-only PRs need link and diff checks rather than game simulations.

## Run and check

Install a 64-bit JDK 21 and set `JAVA_HOME` to its installation directory.
Use the checked-in Gradle wrapper; a separate Gradle installation is unnecessary.
The first run downloads Gradle and engine dependencies.

```powershell
.\gradlew.bat test jacocoTestCoverageVerification verify
.\gradlew.bat run
.\gradlew.bat zipForSubmit
```

See [tests and coverage](docs/TESTING.md) for the HTML report locations and the
Sprint 2 coverage requirement.

On macOS/Linux, use `./gradlew` instead. `run` compiles automatically and plays
`battlecats` against `examplefuncsplayer` on `DefaultSmall`. Replays are written
under `matches/`. `build` also downloads the graphical replay client under
`client/`; keep the client in that directory.

```powershell
.\gradlew.bat listMaps
.\gradlew.bat run -PteamB=testfuncsplayer -Pmaps=DefaultSmall
.\gradlew.bat run -PoutputVerbose=true
```

The submission task compiles and packages only Java sources under one top-level
`battlecats/` folder in `submission.zip`. It does not upload the ZIP.
Keep `engine_version.txt` at 1.2.6 unless the team agrees to change it.

## Easy simulations

Use a checkout containing `tools/simulate.py` and the `sim` Gradle task. These
commands require the testing-mode changes. Without them, use the original
`run` task for individual matches.

From the project folder containing `gradlew.bat`, save your Java edits and run
the quick comparison:

```powershell
.\gradlew.bat sim
```

Requires Python 3.10+ and the same JDK 21 used above; no extra Python packages
are needed. Gradle finds Python automatically, or you can specify an interpreter
with `"-PsimPython=C:\path\to\python.exe"`. On macOS/Linux use `./gradlew`.

The default snapshots saved local Java files, including new untracked files
under `src/`; no commit is needed for an experiment. It fetches `upstream/main`
as the baseline, or `origin/main` when no `upstream` remote exists, and runs
`battlecats` against that revision on **DefaultSmall and DefaultMedium, with
both starting sides** (four matches). The bots keep their original Java packages
and run from separate JARs. Each source snapshot is compiled and verified.
All matches run locally using the Battlecode engine, rather than on a website.

### Choose a branch or earlier iteration

List available versions or use the numbered picker for both bots:

```powershell
.\gradlew.bat simVersions
.\gradlew.bat sim -PsimSelect=true --console=plain
```

The list shows local branches, remote branches, tags, and the latest 12 reachable
commits, with dates, commit messages, and commit IDs. Listing and selection
refresh configured remotes unless `-PsimOffline=true` is set. Tags are labels
available locally, not a live list of releases on GitHub; offline remote refs
may also be outdated.

Choose the **candidate** you want to evaluate, then the **baseline** to compare
against. Candidate `0` means saved local Java edits; Enter accepts the displayed
default (saved edits versus main). A branch, tag, or commit choice uses its
committed files and excludes unsaved/uncommitted edits. Selection keeps your
current branch and files in place. EOF or Ctrl+C cancels rather than choosing
a version silently.

You can also name versions directly, including in scripts or terminals without
interactive input:

```powershell
.\gradlew.bat sim -PsimCandidate=origin/my-feature -PsimBaseline=upstream/main
.\gradlew.bat sim -PsimCandidate=HEAD~1 "-PsimLabel=Previous iteration against main"
```

Use an existing branch name from `simVersions`; `my-feature` is a placeholder.
Without an `upstream` remote, use `origin/main`. Local and remote branches can
differ; the list distinguishes them. Exact refs such as
`refs/heads/my-feature`, `refs/remotes/origin/my-feature`, and
`refs/tags/my-experiment` disambiguate similarly named versions.

Menu numbers and branch tips can change. Every run records the selected commit
IDs, dates, and descriptions. To repeat that exact iteration later, pass those
commit IDs to `simCandidate` and `simBaseline`. For saved edits, the manifest
records a source snapshot hash instead; commit the candidate before a final PR
comparison.

### Choose maps

Engine 1.2.6 includes **43 predefined maps**. The presets select a small suite:

| Preset | Maps | Matches |
| --- | --- | ---: |
| `quick` | `DefaultSmall`, `DefaultMedium` | 4 |
| `full` | `DefaultSmall`, `DefaultMedium`, `DefaultLarge`, `cheesefarm`, `minimaze`, `safelycontained`, `pipes` | 14 |

Both starting sides run on each map. **`full` means the expanded seven-map
suite, not all 43 maps**; it is not an exhaustive tournament evaluation. The
original `gradlew run` command defaults to `DefaultSmall` only.

List every available map, then select names with `simMaps`:

```powershell
.\gradlew.bat listMaps
.\gradlew.bat sim -PsimMaps=DefaultLarge,minimaze,pipes
```

For a custom map, place `MyMap.map26` in the project's `maps/` folder and use
`-PsimMaps=MyMap` (without the extension). The simulator saves a copy of that
map with the run so later edits do not alter its recorded input.

```powershell
# Full comparison: seven maps, both sides (14 matches).
.\gradlew.bat sim -PsimPreset=full

# Choose maps and the local bot package you are developing.
.\gradlew.bat sim -PsimPackage=mybot -PsimMaps=DefaultSmall,cheesefarm

# Final comparison: commit changes first, then test that exact revision.
.\gradlew.bat sim -PsimPreset=full -PsimCandidate=HEAD
```

Each run creates a fresh `matches/sim-.../` folder with `summary.md`,
`pr-summary.md`, `results.csv`, source snapshots, exact baseline/candidate identities in
`manifest.json`, and `.bc26` replays plus logs for each match. Load a replay in
the Battlecode graphical client's replay viewer to inspect a run. The summary
shows delivered cheese, wins and their reasons, end rounds, and map regressions.
Final totals can reflect different match durations; strict round 1,000 results
include only matches that reach that round. Failed or interrupted runs retain
completed cases and are labeled incomplete/failed rather than a successful suite.

### Edit, run, inspect, repeat

1. Edit and save files under `src/battlecats/`, or select your own package with
   `-PsimPackage=mybot`. Unsaved editor changes are not included.
2. Run `sim` for a quick check, or `sim -PsimPreset=full` for the seven-map suite.
3. Open `summary.md` in the new output folder printed by the command. Check the
   completion status, deliveries and win reasons, then each map's regressions.
4. Open a case's `.bc26` replay in the Battlecode client's replay viewer to see
   its behavior; use the matching `.log` for errors or bot messages.
5. Save another edit and rerun. Each run gets a new folder. Before proposing a
   PR, commit the candidate and use `-PsimCandidate=HEAD` for exact revisions.

### Commit and PR notes

Use a descriptive message for each meaningful commit: what behavior changed
and why. A push simply publishes commits; it does not need a separate changelog
entry. Keep experiments on their own branch and make unrelated strategy changes
separate comparisons.

For a PR, use the generated `pr-summary.md` as the starting point, add the
change's rationale and actual review/test status, and retain the exact tested
commit IDs, map coverage, and known regressions. The note labels saved edits,
partial/failed runs, and pending review explicitly; generating it does not
approve the code. If code changes after the comparison, test the new candidate
before attaching the old results to it. The PR template prompts for this evidence.

Other options: `-PsimBaseline=origin/main` chooses a baseline ref;
`-PsimBaselinePackage=examplefuncsplayer` selects its bot;
`-PsimOutput=matches/my-test` chooses a **new** output folder;
`-PsimPrepareOnly=true` only snapshots, compiles, and verifies;
`"-PsimLabel=Short experiment description"` names a run in its reports;
`-PsimOffline=true` skips fetching and uses the cached baseline, which may be
outdated. Saved snapshots include all Java sources under `src/`, so unrelated
Java compile errors also stop a run. This mode does not compile Scala bots.
Runs save their artifacts locally and refresh remote refs when fetching main.
For direct use and additional options, run
`python tools/simulate.py --help`.

## Team bot at this branch's main baseline

The testing-tools branch starts from team main `f6cb13a`; it does not include
the separate experimental 80-cheese/60-round Baby Rat policy.

- `src/battlecats/RobotPlayer.java` runs the turn loop and selects the behavior
  for each unit type. Each robot keeps its own behavior instance and memory.
- `BabyRat.java` scans for a friendly king near spawn, explores, remembers
  visible cheese, picks it up, returns to a friendly king, transfers the whole
  load, and resumes searching. Targets are rechecked when visible. A missing
  king is forgotten and a nearby replacement can be discovered.
- `Navigation.java` turns toward the desired move and follows obstacles when
  a direct move is blocked. Exploration uses changing waypoints and scans.
- `RatKing.java` stays stationary and spawns when cheese exceeds the current
  rat cost plus its 100-cheese reserve, with no four-baby lifetime cap. It
  publishes its x/y coordinates in shared slots 0/1; this Baby Rat still
  discovers kings through local sensing.
- `src/examplefuncsplayer/` and `src/testfuncsplayer/` remain available as local
  opponents. The classmate's test-player implementation is preserved.

Baby Rats do **not** receive a global list of cheese. In v1.2.6 their sensing
cone is 90 degrees with radius squared 20 (about 4.47 tiles), and cheese is
discovered through visible map information. Walls do not occlude that cone.
The collector remembers a target outside its current field of view, then checks
whether cheese is still there when it becomes visible again.

This is a basic collector, not an optimal path planner. It does not implement
combat, traps, king promotion, global map sharing, or cat avoidance. Carried
cheese slows movement. This baseline starts returning when cargo is strictly
greater than 20; two 20-cheese piles normally trigger a return at 40. If a king disappears,
the collector searches for another; rapidly moving kings can make delivery less
reliable than the stationary baseline. Collection and delivery use the same
logic in cooperation and backstabbing.

## Sources and build support

- [Upstream team repository](https://github.com/Victor-Ramirez-Garcia/CSS554-BattleCats)
- [Official scaffold](https://github.com/battlecode/battlecode26-scaffold)
- [Game specification 1.2.6](https://releases.battlecode.org/specs/battlecode26/1.2.6/specs.pdf)
- [API documentation 1.2.6](https://releases.battlecode.org/javadoc/battlecode26/1.2.6/index.html)

The Gradle 8.10 wrapper JAR and distribution use verified official checksums.
`verify` checks the compiled JAR to avoid the engine's Windows folder-path issue.
For synced-directory build problems, use a writable local output directory:

```powershell
.\gradlew.bat "-PlocalBuildDir=$env:TEMP\battlecats-local-build" test verify run
```

The upstream AGPL license remains in `LICENSE`.
