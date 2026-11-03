# Unit tests and coverage

Use JDK 21 and the checked-in Gradle wrapper. From the repository root on Windows:

```powershell
.\gradlew.bat clean test jacocoTestReport jacocoTestCoverageVerification verify
```

On macOS/Linux, replace `.\gradlew.bat` with `./gradlew`. The first run downloads
test and coverage dependencies. Later runs can reuse Gradle's local cache.

Use `clean` when recording coverage, especially after changing branches, so
obsolete compiled classes do not enter the package-wide denominator. For quick
iteration on the same source tree, omitting `clean` is fine.

`test` runs the JUnit tests in `test/`. It also generates a JaCoCo report. The
explicit report task in the command makes that step visible to a reader;
Gradle runs each task only once. `jacocoTestCoverageVerification` checks the
coverage floor. `verify` separately checks that the bot package is valid for the
Battlecode engine. `check` runs the tests, coverage report and coverage gate;
it does not replace the engine verifier or simulation comparisons.

## Reading the reports

Open these files after a successful run:

| Report | Default location | What it shows |
| --- | --- | --- |
| Unit test results | `build/reports/tests/test/index.html` | Test names, failures and totals |
| Coverage for the team bot | `build/reports/jacoco/test/html/index.html` | Covered and missed lines and branches by class |
| Machine-readable coverage | `build/reports/jacoco/test/jacocoTestReport.xml` | Exact coverage counters for tooling |

If you use `-PlocalBuildDir=...`, substitute that build directory in these paths.
Reports are generated outputs; do not commit them. For the sprint demo, open
the HTML reports and keep the corresponding command output with the tested
commit identity.

The coverage denominator includes **every compiled class in `battlecats`**,
including classes no test executes. This is the package included in the
submission ZIP. It excludes the bundled example opponents, Battlecode engine
dependency and test code. Both the HTML report and the gate use this same
scope. Do not exclude hard-to-test production classes to increase the percentage.

The course requires line coverage **strictly above 20%**. Our build requires
**at least 21%** across the complete package, giving a clear margin above that
requirement. This is a test control, not a game strategy setting. Branch coverage
is reported to reveal missing decisions but has no percentage gate. Passing the
floor is a minimum submission check; it does not establish strategy quality.

JaCoCo is pinned to 0.8.12 for reproducible results and Java 21 support; see its
[official release history](https://www.jacoco.org/jacoco/trunk/doc/changes.html).

## Adding useful tests

Keep tests deterministic and independent of live matches. Prefer small fake
collaborators or pure decision inputs over mocks that assert call sequences.
Each changed policy should cover its intended result and relevant boundaries:
no target, unavailable action, insufficient cheese, occupied terrain, dangerous
movement, and returning to collection after the threat passes. A corrected bug
needs a regression case that would fail before the fix.

Tests should explain the gameplay decision in their names. Keep experimental
thresholds distinct from engine rules, and describe the reason for a threshold
near its production definition. Do not copy strategy code into tests or assert
the same calculation without checking its externally observable result.

## Match validation is separate

Unit-test coverage records execution by the test JVM. Local engine simulations
are separate processes and are **not included** in this coverage percentage.
Use simulations to check performance, compatibility, bytecode limits and actual
game behavior. Keep exact baseline and candidate commits, map names, starting
sides, completion status and regressions with each comparison. See the
[repository README](../README.md) for simulation commands and output.
