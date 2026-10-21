"""Readable summaries of paired simulation metrics from authoritative replays.

Only complete candidate/baseline pairs contribute to totals. Keep every input
row in results.csv so an interrupted run can still be inspected.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import os
from pathlib import Path
import re
from urllib.parse import quote


FIELDS = [
    "Case", "Map", "CandidateSide", "Role", "Checkpoint", "Round", "Side",
    "Team", "JavaPackage", "Package", "Seed", "DeliveredCheese", "ReserveCheese", "Kings", "BabyRats",
    "CatDamage", "Cooperation", "Winner", "WinType", "FinalRound",
    "LastKingAliveRound", "BytecodeStatus", "BytecodeCSV",
]
BYTECODE_TYPES = (("BabyRat", "Baby Rat"), ("RatKing", "Rat King"))
BYTECODE_COUNTERS = ("Turns", "BytecodesTotal", "BytecodesMax", "BytecodeLimit", "BudgetHits")
FIELDS += [prefix + counter for prefix, _ in BYTECODE_TYPES for counter in BYTECODE_COUNTERS]


def _bytecode_values(row: dict, prefix: str) -> tuple[dict | None, str]:
    """Validate cumulative counters without inventing zeros for older readers."""
    raw = {key: row.get(prefix + key) for key in BYTECODE_COUNTERS}
    missing = [value is None or value == "" for value in raw.values()]
    status = str(row.get("BytecodeStatus", ""))
    if status and status != "AVAILABLE":
        return None, "unavailable"
    if all(missing):
        return None, "invalid" if status == "AVAILABLE" else "missing"
    if any(missing) or status != "AVAILABLE":
        return None, "invalid"
    if any(isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value))
           for value in raw.values()):
        return None, "invalid"
    values = {key: int(value) for key, value in raw.items()}
    turns, total, peak, limit, hits = (values[key] for key in BYTECODE_COUNTERS)
    if (limit <= 0 or hits > turns or peak > total or total > turns * peak
            or (not turns and (total or peak or hits))
            or bool(hits) != (peak >= limit)
            or (hits and total < peak + (hits - 1) * limit)
            or total > hits * peak + (turns - hits) * min(peak, limit - 1)):
        return None, "invalid"
    return values, "valid"


def _bytecodes(final: list[tuple[dict, dict]]) -> list[dict]:
    """Use FINAL once per match and retain matched measurement coverage by type."""
    result = []
    for prefix, label in BYTECODE_TYPES:
        valid = []
        missing = invalid = 0
        for pair in final:
            checked = [_bytecode_values(row, prefix) for row in pair]
            statuses = {status for _, status in checked}
            if "invalid" in statuses:
                invalid += 1
            elif "missing" in statuses or "unavailable" in statuses:
                missing += 1
            elif checked[0][0]["BytecodeLimit"] != checked[1][0]["BytecodeLimit"]:
                invalid += 1
            else:
                valid.append([values for values, _ in checked])
        limits = {pair[0]["BytecodeLimit"] for pair in valid}
        # An aggregate percentage has no single meaning across changed budgets.
        conflicting = len(limits) > 1
        if conflicting:
            invalid += len(valid)
            valid = []
        for index, role in enumerate(("candidate", "baseline")):
            samples = [pair[index] for pair in valid]
            result.append(dict(
                role=role, unit=label, measured=len(valid), expected=len(final),
                missing=missing, invalid=invalid, conflicting=conflicting,
                turns=sum(value["Turns"] for value in samples),
                total=sum(value["BytecodesTotal"] for value in samples),
                peak=max((value["BytecodesMax"] for value in samples), default=0),
                limit=samples[0]["BytecodeLimit"] if samples else None,
                hits=sum(value["BudgetHits"] for value in samples)))
    return result


def _bytecode_reasons(final: list[tuple[dict, dict]]) -> Counter:
    reasons = Counter()
    for pair in final:
        for reason in {str(row.get("BytecodeStatus", "")) for row in pair} - {"", "AVAILABLE"}:
            reasons[reason] += 1
    return reasons


def _bytecode_cells(value: dict) -> list[str]:
    identity = [value["role"].title(), value["unit"], f"{value['measured']}/{value['expected']}"]
    if not value["measured"]:
        return identity + ["unavailable"] * 7
    turns, limit = value["turns"], value["limit"]
    if not turns:
        return identity + ["0", "n/a (no robot turns)", "n/a", f"{limit:,}", "n/a", "n/a", "n/a"]
    average = value["total"] / turns
    return identity + [f"{turns:,}", f"{average:,.1f}", f"{value['peak']:,}", f"{limit:,}",
                       f"{average / limit * 100:.1f}%", f"{value['peak'] / limit * 100:.1f}%",
                       f"{value['hits']:,} ({value['hits'] / turns * 100:.1f}%)"]


def _bytecode_lines(final: list[tuple[dict, dict]]) -> list[str]:
    metrics = _bytecodes(final)
    lines = ["## Executed bytecodes per robot turn", "",
             "Full-match measurements use complete FINAL pairs only, including startup. "
             "Averages are robot-turn weighted: total executed bytecodes divided by recorded robot turns; "
             "peaks are individual robot turns. These are engine replay counters, not Java file sizes.", "",
             "| Role | Unit | Measured pairs | Robot turns | Average / turn | Peak / turn | Turn budget | Average budget | Peak budget | Budget reached turns |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    lines.extend("| " + " | ".join(_bytecode_cells(value)) + " |" for value in metrics)
    lines.extend(["", "Measurement coverage requires valid counters and the same recorded engine budget for both roles in each pair. "
                  "Missing or invalid measurements are excluded from both roles; unavailable does not mean zero usage.", ""])
    for value in metrics[::2]:
        if value["missing"] or value["invalid"]:
            note = " (conflicting engine budgets)" if value["conflicting"] else ""
            lines.append(f"{value['unit']} excluded pairs: {value['missing']} missing or unavailable, {value['invalid']} invalid{note}.")
    for reason, count in sorted(_bytecode_reasons(final).items()):
        lines.append(f"Unavailable replay measurements ({count} complete pairs): {_escape(reason)}.")
    lines.extend(["", "Budget reached counts recorded turns at or above the engine budget; it does not prove a forced yield. "
                  "Bytecode counters in [results.csv](results.csv) are cumulative through each checkpoint; "
                  "adding checkpoint rows would count turns repeatedly. Per-case `*-bytecodes.csv` files retain individual turn measurements.", ""])
    lines.extend(["When the replay cannot support reliable turn measurements, its bytecode CSV contains only a header "
                  "and the reason is reported above.", ""])
    return lines


def _number(row: dict, key: str) -> int:
    return int(row[key])


def _escape(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("|", "&#124;")
            .replace("[", "&#91;").replace("]", "&#93;")
            .replace("\r", " ").replace("\n", " ").replace("`", "&#96;"))


def _pairs(rows: list[dict], checkpoint: str) -> list[tuple[dict, dict]]:
    cases = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("Checkpoint") == checkpoint and row.get("Role") in ("candidate", "baseline"):
            cases[str(row["Case"])][row["Role"]].append(row)
    result = []
    for case in sorted(cases):
        roles = cases[case]
        if len(roles["candidate"]) != 1 or len(roles["baseline"]) != 1:
            continue
        candidate, baseline = roles["candidate"][0], roles["baseline"][0]
        # A pair must describe one match at the same actual checkpoint.
        if any(str(candidate.get(key)) != str(baseline.get(key))
               for key in ("Map", "CandidateSide", "Round", "Seed", "FinalRound", "Winner", "WinType")):
            continue
        round_number = _number(candidate, "Round")
        final_round = _number(candidate, "FinalRound")
        if checkpoint == "FINAL" and round_number != final_round:
            continue
        if checkpoint == "ROUND_1000" and (round_number != 1000 or final_round < 1000):
            continue
        if checkpoint == "COMMON_1000" and round_number != min(1000, final_round):
            continue
        result.append((candidate, baseline))
    return result


def _totals(pairs: list[tuple[dict, dict]]) -> tuple[int, int]:
    return tuple(sum(_number(pair[index], "DeliveredCheese") for pair in pairs)
                 for index in (0, 1))


def _change(candidate: int, baseline: int) -> str:
    # Neither 0/0 nor an increase from zero establishes a finite percentage gain.
    return f"{(candidate / baseline - 1) * 100:+.1f}%" if baseline else "n/a (baseline 0)"


def _winner(pair: tuple[dict, dict]) -> str:
    winner = str(pair[0].get("Winner", ""))
    if winner in ("candidate", "baseline"):
        return winner
    # Legacy replay readers used unique team package labels. Never resolve a
    # winner through shared Java package names: both jars may use battlecats.
    packages = {str(row.get("Package", "")) for row in pair}
    for role, row in zip(("candidate", "baseline"), pair):
        if len(packages) == 2 and winner == str(row.get("Package", "")):
            return role
    for role, row in zip(("candidate", "baseline"), pair):
        if winner == str(row.get("Side", "")):
            return role
    return "unknown"


def _wins(pairs: list[tuple[dict, dict]]) -> Counter:
    return Counter(_winner(pair) for pair in pairs)


def _version(manifest: dict, role: str) -> dict:
    nested = manifest.get(role, {})
    if not isinstance(nested, dict):
        nested = {}
    versions = manifest.get("versions", {})
    version = versions.get(role, {}) if isinstance(versions, dict) else {}
    return {**nested, **version} if isinstance(version, dict) else nested


def _identity(manifest: dict, role: str) -> str:
    nested = _version(manifest, role)
    ref = manifest.get(role + "_ref") or nested.get("ref")
    commit = manifest.get(role + "_commit") or nested.get("commit") or nested.get("sha")
    snapshot = (manifest.get(role + "_snapshot_sha256") or nested.get("snapshot_sha256")
                or (manifest.get("working_tree_sha256") if role == "candidate" else None)
                or (manifest.get("candidate_source_sha256") if role == "candidate" else None))
    parts = []
    if ref:
        parts.append(str(ref))
    if commit:
        parts.append("commit " + str(commit))
    if snapshot:
        parts.append("source snapshot SHA-256 " + str(snapshot))
    return _escape("; ".join(parts) if parts else "not recorded")


def _version_label(manifest: dict, role: str) -> str:
    version = _version(manifest, role)
    return _escape("; ".join(str(version[key]) for key in ("subject", "date")
                             if version.get(key)))


def _run_status(summary: dict, manifest: dict) -> str:
    status = str(manifest.get("status", "")).upper()
    return status if status in ("FAILED", "CANCELLED", "RUNNING", "PREPARED") else (
        "Complete" if summary["complete"] else "INCOMPLETE")


def _pr_identity(manifest: dict, role: str) -> str:
    version = _version(manifest, role)
    commit = manifest.get(role + "_commit") or version.get("commit") or version.get("sha")
    identity = _identity(manifest, role)
    if role == "candidate" and not commit:
        identity = "**UNCOMMITTED snapshot — exploratory, not a final PR comparison**; " + identity
    label = _version_label(manifest, role)
    return identity + (f"; {label}" if label else "")


def _metadata(manifest: dict, case: str) -> dict:
    cases = manifest.get("cases", {})
    if isinstance(cases, dict):
        value = cases.get(case, {})
        return value if isinstance(value, dict) else {}
    if isinstance(cases, list):
        for value in cases:
            if isinstance(value, dict) and str(value.get("case", value.get("Case", value.get("id")))) == case:
                return value
    return {}


def _file_link(output: Path, value, label: str) -> str:
    if not value:
        return "n/a"
    path = Path(str(value))
    if path.is_absolute():
        try:
            path = Path(os.path.relpath(path, output))
        except ValueError:  # Different Windows drive: no relative link possible.
            return _escape(value)
    return f"[{label}]({quote(path.as_posix(), safe='/.-_')})"


def _case_links(output: Path, manifest: dict, row: dict) -> str:
    case = str(row["Case"])
    metadata = _metadata(manifest, case)
    links = []
    for suffix, key in (("bc26", "replay"), ("log", "log")):
        value = (row.get(key.title()) or metadata.get(key) or metadata.get(key + "_path"))
        if not value and (output / (case + "." + suffix)).is_file():
            value = case + "." + suffix
        links.append(_file_link(output, value, key))
    bytecodes = row.get("BytecodeCSV") or metadata.get("bytecodes")
    if bytecodes:
        label = "bytecodes" if row.get("BytecodeStatus") == "AVAILABLE" else "bytecodes (header only)"
        links.append(_file_link(output, bytecodes, label))
    return " / ".join(links)


def _summary(rows: list[dict], expected_cases: int) -> dict:
    final = _pairs(rows, "FINAL")
    strict = _pairs(rows, "ROUND_1000")
    common = _pairs(rows, "COMMON_1000")
    wins = _wins(final)
    return dict(final=final, strict=strict, common=common, wins=wins,
                complete=len(final) == expected_cases, expected=expected_cases)


def print_summary(rows: list[dict], expected_cases: int) -> None:
    """Print a short terminal summary; early endings never stand in for round 1000."""
    summary = _summary(rows, expected_cases)
    status = "Complete" if summary["complete"] else "INCOMPLETE"
    print(f"{status}: {len(summary['final'])}/{expected_cases} complete match pairs.")
    for label, key in (("Final", "final"), ("Strict round 1000", "strict"),
                       ("Common checkpoint min(1000, end)", "common")):
        pairs = summary[key]
        candidate, baseline = _totals(pairs)
        print(f"{label}: {len(pairs)} pairs; delivered candidate {candidate:,}, "
              f"baseline {baseline:,}; change {_change(candidate, baseline)}.")
    wins = summary["wins"]
    print(f"Wins: candidate {wins['candidate']}, baseline {wins['baseline']}, "
          f"unknown {wins['unknown']}. See summary.md for end rounds and win reasons.")
    for value in _bytecodes(summary["final"]):
        cells = _bytecode_cells(value)
        print(f"Bytecodes {cells[0]} / {cells[1]}: {cells[2]} measured pairs; "
              f"{cells[3]} robot turns; average {cells[4]} ({cells[7]} of budget), "
              f"peak {cells[5]} ({cells[8]} of budget); budget reached {cells[9]}.")
    for reason, count in sorted(_bytecode_reasons(summary["final"]).items()):
        print(f"Bytecodes unavailable for {count} complete pairs: {reason}.")


def _write_pr_summary(output: Path, rows: list[dict], manifest: dict, summary: dict) -> None:
    """Draft evidence for a PR; strategy rationale and review remain human decisions."""
    final, strict = summary["final"], summary["strict"]
    expected, complete = summary["expected"], len(final)
    status = _run_status(summary, manifest)
    maps = manifest.get("maps") or sorted({str(row["Map"]) for row in rows})
    cases = manifest.get("cases", [])
    planned_sides = {str(case["side"]) for case in cases
                     if isinstance(case, dict) and case.get("side")} if isinstance(cases, list) else set()
    sides = sorted(planned_sides or {str(row["CandidateSide"]) for row in rows})
    lines = ["# Simulation evidence for PR", "",
             f"**{status}: {complete}/{expected} complete match pairs.**", "",
             f"Baseline: {_pr_identity(manifest, 'baseline')}", "",
             f"Candidate: {_pr_identity(manifest, 'candidate')}", "",
             f"Preset: {_escape(manifest.get('preset', 'not recorded'))}; "
             f"engine: {_escape(manifest.get('engine_version', 'not recorded'))}; "
             f"candidate starting sides: {_escape(', '.join(sides) or 'not recorded')}", "",
             f"Maps: {_escape(', '.join(str(name) for name in maps) or 'not recorded')}", ""]
    if manifest.get("label"):
        lines[2:2] = [f"Experiment: {_escape(manifest['label'])}", ""]
    if manifest.get("error"):
        lines.extend([f"Run error: {_escape(manifest['error'])}", ""])
    if status != "Complete":
        lines.extend(["This run is not a completed comparison. Partial totals do not establish an overall improvement; "
                      "missing, duplicate, or inconsistent pairs are excluded.", ""])
    lines.extend(["| Delivered cheese | Complete pairs | Candidate | Baseline | Change |",
                  "| --- | ---: | ---: | ---: | ---: |"])
    for label, pairs in (("Final", final), ("Fixed round 1000", strict)):
        candidate, baseline = _totals(pairs)
        lines.append(f"| {label} | {len(pairs)}/{expected} | {candidate:,} | {baseline:,} | {_change(candidate, baseline)} |")
    lines.extend(["", "Delivered cheese is not the engine's match points. Final totals use actual end rounds; "
                  "fixed round 1000 excludes earlier endings. A zero baseline has no defined percentage change.", ""])
    lines.extend(_bytecode_lines(final))
    wins = summary["wins"]
    reasons = defaultdict(Counter)
    for pair in final:
        reasons[str(pair[0].get("WinType", "unknown"))][_winner(pair)] += 1
    reason_labels = []
    for reason in sorted(reasons):
        counts = reasons[reason]
        reason_labels.append(f"{_escape(reason)}: {counts['candidate']}/{counts['baseline']}/{counts['unknown']}")
    coin_flips = sum(sum(counts.values()) for reason, counts in reasons.items() if "COIN" in reason.upper())
    lines.extend([f"Wins (candidate/baseline/unknown): **{wins['candidate']}/{wins['baseline']}/{wins['unknown']}** "
                  f"across {complete} completed matches. Reasons (same order): "
                  + ("; ".join(reason_labels) or "none recorded") + ".", "",
                  f"Coin-flip outcomes: **{coin_flips}**; included in wins and do not demonstrate a strategy advantage.", ""])
    by_map = defaultdict(list)
    for pair in final:
        by_map[str(pair[0]["Map"])].append(pair)
    regressions = [(name, pairs, *_totals(pairs)) for name, pairs in sorted(by_map.items())
                   if _totals(pairs)[0] < _totals(pairs)[1]]
    lines.extend(["## Per-map regressions", ""])
    if regressions:
        lines.extend(["| Map | Complete pairs | Candidate | Baseline | Change |",
                      "| --- | ---: | ---: | ---: | ---: |"])
        for name, pairs, candidate, baseline in regressions:
            lines.append(f"| {_escape(name)} | {len(pairs)} | {candidate:,} | {baseline:,} | {_change(candidate, baseline)} |")
    else:
        lines.append("No lower final-delivery total was observed among completed map pairs. This is not proof of general improvement.")
    lines.extend(["", "Full per-map results, starting-side coverage, end rounds, replays and logs: "
                  "[summary.md](summary.md); all recorded checkpoints: [results.csv](results.csv).", ""])
    hashes = manifest.get("jar_hashes")
    verified = isinstance(hashes, dict) and all(
        isinstance(hashes.get(role), str) and re.fullmatch(r"[0-9a-fA-F]{64}", hashes[role])
        for role in ("candidate", "baseline"))
    lines.append("Build evidence: both snapshots compiled and passed the bot verifier (both JAR hashes recorded). "
                 "Unit-test status is not recorded here." if verified else
                 "Build evidence: compilation/verifier completion is not recorded for both snapshots. "
                 "Unit-test status is not recorded here.")
    phases = {str(row.get("Cooperation", "")).lower() for row in rows}
    phase_note = ("All reported checkpoints were in cooperation; this does not establish behavior after a PvP transition."
                  if phases == {"true"} else
                  "Cooperation flags are checkpoint samples in results.csv; no full-match or PvP coverage is assumed.")
    lines.extend(["", f"Limits: these selected maps, sides and one matchup do not establish an optimal strategy. {phase_note}", "",
                  "## Change and rationale", "", "Pending: describe the intended change and explain any strategy constants.", "",
                  "## Code review", "", "Pending: independent review of scope, code and these results; this generated note is not approval.", ""])
    (output / "pr-summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_report(output: Path, rows: list[dict], manifest: dict, expected_cases: int) -> None:
    """Write results.csv, summary.md and pr-summary.md without changing sources or saved replays."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(FIELDS + [key for row in rows for key in row]))
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    summary = _summary(rows, expected_cases)
    final = summary["final"]
    complete = len(final)
    status = _run_status(summary, manifest)
    lines = ["# Simulation comparison", "", f"**{status}: {complete}/{expected_cases} complete match pairs.**", "",
             f"Baseline: {_identity(manifest, 'baseline')}", "",
             f"Candidate: {_identity(manifest, 'candidate')}", ""]
    for role in ("baseline", "candidate"):
        label = _version_label(manifest, role)
        if label:
            lines.extend([f"{role.title()} version: {label}", ""])
    for key, label in (("label", "Experiment"), ("preset", "Preset"), ("engine_version", "Engine")):
        if manifest.get(key) is not None:
            lines.extend([f"{label}: {_escape(manifest[key])}", ""])
    for role in ("candidate", "baseline"):
        packages = sorted({str(row.get("JavaPackage") or row.get("Package"))
                           for row in rows if row.get("Role") == role
                           and (row.get("JavaPackage") or row.get("Package"))})
        manifest_packages = manifest.get("packages", {})
        if not isinstance(manifest_packages, dict):
            manifest_packages = {}
        package = (", ".join(packages) or str(manifest_packages.get(role)
                   or manifest.get(role + "_package", "not recorded")))
        lines.extend([f"{role.title()} simulation package: {_escape(package)}", ""])
    if manifest.get("error"):
        lines.extend([f"Run error: {_escape(manifest['error'])}", ""])
    if not summary["complete"]:
        lines.extend(["Results are partial. Missing, duplicate, or inconsistent team pairs are excluded from totals. "
                      "Inspect run logs for unfinished or failed cases; partial totals do not establish an overall improvement.", ""])

    lines.extend(["## Delivered cheese", "",
                  "Engine replays supply the delivery totals and match outcomes. No collection totals are inferred from bot logs.", "",
                  "| Measurement | Complete pairs | Candidate | Baseline | Change |",
                  "| --- | ---: | ---: | ---: | ---: |"])
    for label, key in (("Final", "final"), ("Strict round 1000", "strict"),
                       ("Common checkpoint: min(1000, end)", "common")):
        pairs = summary[key]
        candidate, baseline = _totals(pairs)
        lines.append(f"| {label} | {len(pairs)}/{expected_cases} | {candidate:,} | {baseline:,} | {_change(candidate, baseline)} |")
    lines.extend(["", "Final totals use each match's actual end round; match durations can differ. "
                  "Strict round 1000 includes only matches with a recorded round 1000. "
                  "The common checkpoint uses round 1000 or the earlier match end, so it mixes times and is not a fixed-round comparison. "
                  "A zero baseline has no defined percentage change, including when both totals are zero.", ""])
    lines.extend(_bytecode_lines(final))

    wins = summary["wins"]
    candidate_wins = f"{wins['candidate']}/{complete}" if complete else "n/a (no completed pairs)"
    baseline_wins = f"{wins['baseline']}/{complete}" if complete else "n/a (no completed pairs)"
    lines.extend(["## Match outcomes", "",
                  f"Candidate wins: **{candidate_wins}**; baseline wins: **{baseline_wins}**; "
                  f"unresolved winner labels: **{wins['unknown']}**.", "",
                  "| Engine win reason | Candidate wins | Baseline wins | Unknown |",
                  "| --- | ---: | ---: | ---: |"])
    reasons = defaultdict(Counter)
    for pair in final:
        reasons[str(pair[0].get("WinType", "unknown"))][_winner(pair)] += 1
    for reason in sorted(reasons):
        counts = reasons[reason]
        lines.append(f"| {_escape(reason)} | {counts['candidate']} | {counts['baseline']} | {counts['unknown']} |")
    coin_flips = sum(sum(counts.values()) for reason, counts in reasons.items()
                     if "COIN" in reason.upper())
    lines.extend(["", f"Coin-flip outcomes: **{coin_flips}**. They are included in the win count and do not demonstrate a strategy advantage.", ""])
    if final:
        rounds = [_number(pair[0], "FinalRound") for pair in final]
        lines.extend([f"Completed matches ended between rounds **{min(rounds)} and {max(rounds)}**; "
                      f"**{sum(number < 1000 for number in rounds)}** ended before round 1000.", ""])
    observed_phases = {str(row.get("Cooperation", "")).lower() for row in rows}
    if observed_phases == {"true"}:
        lines.extend(["All reported replay checkpoints were in cooperation. These samples do not establish behavior after a PvP transition.", ""])
    elif observed_phases:
        lines.extend(["Cooperation flags for individual replay checkpoints are recorded in results.csv; "
                      "aggregate results combine the reported phases.", ""])

    lines.extend(["## Final deliveries by map", "",
                  "Maps with fewer than two starting sides are not a complete side-swapped comparison.", "",
                  "| Map | Complete pairs | Candidate starting sides | Candidate | Baseline | Change | Candidate wins |",
                  "| --- | ---: | --- | ---: | ---: | ---: | ---: |"])
    maps = defaultdict(list)
    for pair in final:
        maps[str(pair[0]["Map"])].append(pair)
    for map_name in sorted(maps):
        pairs = maps[map_name]
        candidate, baseline = _totals(pairs)
        sides = ", ".join(sorted({str(pair[0]["CandidateSide"]) for pair in pairs}))
        lines.append(f"| {_escape(map_name)} | {len(pairs)} | {_escape(sides)} | {candidate:,} | {baseline:,} | "
                     f"{_change(candidate, baseline)} | {_wins(pairs)['candidate']}/{len(pairs)} |")

    lines.extend(["", "## Completed cases", "",
                  "| Case | Candidate side | End round | Winner | Win reason | Delivered candidate / baseline | Replay / log / bytecodes |",
                  "| --- | --- | ---: | --- | --- | ---: | --- |"])
    for pair in final:
        row = pair[0]
        candidate, baseline = _totals([pair])
        lines.append(f"| {_escape(row['Case'])} | {_escape(row['CandidateSide'])} | {_number(row, 'FinalRound')} | "
                     f"{_winner(pair)} | {_escape(row.get('WinType', 'unknown'))} | {candidate:,} / {baseline:,} | "
                     f"{_case_links(output, manifest, row)} |")
    lines.extend(["", "Use the saved source identities and the same maps, seeds, sides, and engine version when comparing runs. "
                  "Differences in strategy outside the intended change can affect both deliveries and wins.", ""])
    (output / "summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    _write_pr_summary(output, rows, manifest, summary)
