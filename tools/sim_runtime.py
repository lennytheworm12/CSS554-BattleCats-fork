"""Runtime discovery and replay metrics for the Java simulation mode (engine 1.2.6)."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

ENGINE_VERSION = "1.2.6"
OPEN_PACKAGES = ('jdk.internal.misc', 'jdk.internal.math', 'jdk.internal.util', 'jdk.internal.access', 'sun.security.action')

# Teams are identified by numeric side, independently of their Java package.
REPLAY_READER = r"""import battlecode.schema.*;
import java.util.*;
import java.nio.*;
import java.nio.file.*;
import java.io.*;
import java.util.zip.*;
public class SimulationReplayMetrics {
    static final String BYTECODE_COLUMNS = "BytecodeStatus,BabyRatTurns,BabyRatBytecodesTotal,BabyRatBytecodesMax,BabyRatBytecodeLimit,BabyRatBudgetHits,RatKingTurns,RatKingBytecodesTotal,RatKingBytecodesMax,RatKingBytecodeLimit,RatKingBudgetHits";
    static class Stats {
        long turns, total, hits;
        int max, limit;
        Stats copy() { Stats s = new Stats(); s.turns = turns; s.total = total;
            s.hits = hits; s.max = max; s.limit = limit; return s; }
        void add(int used, int budget) {
            turns++; total += used; max = Math.max(max, used); limit = budget;
            if (used >= budget) hits++;
        }
    }
    record Unit(int team, byte type) {}
    record BytecodeTurn(int round, int id, int team, byte type, int used, int limit) {}
    // Engine 1.2.6's generated FlatBuffers union accessor accepts only Tables although these
    // payloads are Structs. Reset only the address, then use the generated
    // Struct accessor: treating their first bytes as a Table vtable is invalid.
    static class StructUnion extends com.google.flatbuffers.Table {
        @Override protected void __reset(int position, ByteBuffer buffer) {
            bb_pos = position; bb = buffer;
        }
        SpawnAction spawn() { return new SpawnAction().__assign(bb_pos, bb); }
        UpgradeToRatKing upgrade() { return new UpgradeToRatKing().__assign(bb_pos, bb); }
    }
    static class BytecodeTracker {
        final Map<Integer, Unit> units = new HashMap<>();
        final Map<Byte, Integer> limits = new HashMap<>();
        final Stats[][] stats = new Stats[3][2];
        final List<BytecodeTurn> turns = new ArrayList<>();
        String status = "AVAILABLE";
        int currentRound = -1;
        final Set<Integer> seen = new HashSet<>();
        BytecodeTracker() { for (int side = 0; side < 3; side++)
            for (int type = 0; type < 2; type++) stats[side][type] = new Stats(); }
        void unavailable(String reason) {
            if (status.equals("AVAILABLE")) status = "UNAVAILABLE: " + reason;
        }
        void metadata(byte type, int limit) {
            if (limit <= 0 || (limits.containsKey(type) && limits.get(type) != limit))
                unavailable("missing or inconsistent bytecode budget metadata");
            limits.put(type, limit);
            int index = typeIndex(type);
            if (index >= 0) for (int side = 1; side <= 2; side++) stats[side][index].limit = limit;
        }
        void header(GameHeader header) {
            for (int i = 0; i < header.robotTypeMetadataLength(); i++) {
                RobotTypeMetadata data = header.robotTypeMetadata(i);
                // Cats are engine-controlled and do not consume a team's budget.
                if (typeIndex(data.type()) >= 0) metadata(data.type(), data.bytecodeLimit());
            }
            if (!limits.containsKey(RobotType.RAT) || !limits.containsKey(RobotType.RAT_KING))
                unavailable("missing bytecode budget metadata");
        }
        static int typeIndex(byte type) {
            return type == RobotType.RAT ? 0 : type == RobotType.RAT_KING ? 1 : -1;
        }
        void spawn(int id, int team, byte type) {
            if (id <= 0 || team < 0 || team > 2 ||
                (type != RobotType.CAT && typeIndex(type) < 0) ||
                (typeIndex(type) >= 0 && team == 0)) {
                unavailable("unknown robot identity or type"); return;
            }
            if (units.putIfAbsent(id, new Unit(team, type)) != null)
                unavailable("duplicate robot spawn identity");
        }
        void initial(GameMap map) {
            InitialBodyTable bodies = map.initialBodies();
            if (bodies == null) { unavailable("missing initial robot identities"); return; }
            for (int i = 0; i < bodies.spawnActionsLength(); i++) {
                SpawnAction body = bodies.spawnActions(i);
                spawn(body.id(), body.team(), body.robotType());
            }
        }
        void accept(int round, int id, int used) {
            if (round != currentRound) {
                if (round <= currentRound) unavailable("non-increasing round order");
                currentRound = round; seen.clear();
            }
            // Carrying and throwing can emit extra replay state updates carrying
            // stale counters. They cannot safely be treated as executed turns.
            // Reject all bytecode statistics for such a match instead of guessing
            // which duplicate is the real execution. Cheese reports remain valid.
            if (!seen.add(id)) unavailable("duplicate robot turn in round " + round);
            Unit unit = units.get(id);
            if (unit == null) { unavailable("unknown robot identity " + id); return; }
            if (used < 0) { unavailable("negative bytecode count"); return; }
            int index = typeIndex(unit.type());
            if (index < 0) return;
            Integer limit = limits.get(unit.type());
            if (limit == null || limit <= 0) { unavailable("missing bytecode budget metadata"); return; }
            stats[unit.team()][index].add(used, limit);
            turns.add(new BytecodeTurn(round, id, unit.team(), unit.type(), used, limit));
        }
        void promote(int id) {
            Unit unit = units.get(id);
            if (unit == null || unit.type() != RobotType.RAT) {
                unavailable("unknown rat king promotion identity"); return;
            }
            units.put(id, new Unit(unit.team(), RobotType.RAT_KING));
        }
        void round(Round round) {
            for (int t = 0; t < round.turnsLength(); t++) {
                Turn turn = round.turns(t);
                // The engine fixes the budget before running a robot. A baby
                // promoted during this turn still has the baby budget this turn.
                accept(round.roundId(), turn.robotId(), turn.bytecodesUsed());
                if (turn.actionsLength() != turn.actionsTypeLength()) {
                    unavailable("inconsistent action vector"); continue;
                }
                for (int action = 0; action < turn.actionsLength(); action++) {
                    byte type = turn.actionsType(action);
                    // Even an unduplicated carrier update can be stale if its
                    // subject dies before its scheduled turn. Reject the whole
                    // replay's bytecode data as soon as carrying/throwing occurs.
                    if (type == Action.RatNap || type == Action.ThrowRat) {
                        unavailable("carrying or throwing replay state updates");
                    } else if (type == Action.SpawnAction) {
                        StructUnion payload = (StructUnion) turn.actions(new StructUnion(), action);
                        if (payload == null) unavailable("missing spawn payload");
                        else { SpawnAction spawn = payload.spawn();
                            spawn(spawn.id(), spawn.team(), spawn.robotType()); }
                    } else if (type == Action.UpgradeToRatKing) {
                        StructUnion payload = (StructUnion) turn.actions(new StructUnion(), action);
                        if (payload == null || payload.upgrade().phantom() != turn.robotId())
                            unavailable("ambiguous rat king promotion");
                        else promote(turn.robotId());
                    }
                }
            }
        }
        Stats[][] copyStats() {
            Stats[][] copy = new Stats[3][2];
            for (int side = 0; side < 3; side++) for (int type = 0; type < 2; type++)
                copy[side][type] = stats[side][type].copy();
            return copy;
        }
        void writeTurns(Path path, String[] packages) throws IOException {
            try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(path))) {
                out.println("Round,RobotId,Side,Team,UnitType,BytecodesUsed,BytecodeLimit");
                if (!status.equals("AVAILABLE")) return;
                for (BytecodeTurn turn : turns) out.printf(Locale.ROOT, "%d,%d,%s,%s,%s,%d,%d%n",
                    turn.round(), turn.id(), turn.team() == 1 ? "A" : "B", packages[turn.team()],
                    turn.type() == RobotType.RAT ? "BABY_RAT" : "RAT_KING", turn.used(), turn.limit());
            }
        }
    }
    static void snapshot(PrintWriter out, String label, Round round, String[] packages,
                         MatchFooter footer, boolean coop, int seed,
                         int finalRound, int[] lastKingAlive, BytecodeTracker tracker, Stats[][] stats) {
        for (int i = 0; i < round.teamIdsLength(); i++) {
            int id = round.teamIds(i), combined = round.teamAliveRatKings(i);
            out.printf(Locale.ROOT, "%s,%d,%s,%s,%d,%d,%d,%d,%d,%d,%s,%s,%s,%d,%d,%s",
                label, round.roundId(), id == 1 ? "A" : "B", packages[id],
                seed, round.teamCheeseTransferred(i), combined / 10, combined % 10,
                round.teamAliveBabyRats(i), round.teamCatDamage(i), coop,
                packages[footer.winner()], WinType.name(footer.winType()), finalRound, lastKingAlive[id], tracker.status);
            for (int type = 0; type < 2; type++) {
                Stats value = stats[id][type];
                if (tracker.status.equals("AVAILABLE")) out.printf(Locale.ROOT, ",%d,%d,%d,%d,%d",
                    value.turns, value.total, value.max, value.limit, value.hits);
                else out.print(",,,,,");
            }
            out.println();
        }
    }
    public static void main(String[] args) throws Exception {
        byte[] bytes;
        try (InputStream input = new GZIPInputStream(Files.newInputStream(Path.of(args[0])))) {
            bytes = input.readAllBytes();
        }
        GameWrapper game = GameWrapper.getRootAsGameWrapper(ByteBuffer.wrap(bytes));
        String[] packages = new String[3];
        MatchFooter footer = null;
        int seed = 0;
        Round last = null;
        int[] lastKingAlive = new int[3];
        boolean coop = true;
        Map<Integer, Round> rounds = new LinkedHashMap<>();
        Map<Integer, Boolean> phases = new HashMap<>();
        BytecodeTracker bytecodes = new BytecodeTracker();
        Map<Integer, Stats[][]> bytecodeSnapshots = new HashMap<>();
        Set<Integer> wanted = new HashSet<>();
        for (String token : args[2].split(",")) wanted.add(Integer.parseInt(token));
        wanted.add(1000);
        for (int i = 0; i < game.eventsLength(); i++) {
            EventWrapper event = game.events(i);
            if (event.eType() == Event.GameHeader) {
                GameHeader header = (GameHeader) event.e(new GameHeader());
                bytecodes.header(header);
                for (int t = 0; t < header.teamsLength(); t++) {
                    TeamData team = header.teams(t);
                    packages[team.teamId()] = ((team.teamId() == 1) == args[3].equals("A")) ? "candidate" : "baseline";
                }
            } else if (event.eType() == Event.MatchHeader) {
                GameMap map = ((MatchHeader) event.e(new MatchHeader())).map();
                seed = map.randomSeed();
                bytecodes.initial(map);
            } else if (event.eType() == Event.Round) {
                last = (Round) event.e(new Round());
                bytecodes.round(last);
                for (int team = 0; team < last.teamIdsLength(); team++)
                    if (last.teamAliveRatKings(team) % 10 > 0)
                        lastKingAlive[last.teamIds(team)] = last.roundId();
                if (last.turnsLength() > 0) coop = last.turns(last.turnsLength() - 1).isCooperation();
                if (wanted.contains(last.roundId())) {
                    rounds.put(last.roundId(), last);
                    phases.put(last.roundId(), coop);
                    bytecodeSnapshots.put(last.roundId(), bytecodes.copyStats());
                }
            } else if (event.eType() == Event.MatchFooter) {
                footer = (MatchFooter) event.e(new MatchFooter());
            }
        }
        if (last == null || footer == null) throw new IllegalStateException("Incomplete replay");
        Stats[][] finalBytecodes = bytecodes.copyStats();
        bytecodes.writeTurns(Path.of(args[4]), packages);
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(Path.of(args[1])))) {
            out.println("Checkpoint,Round,Side,Team,Seed,DeliveredCheese,ReserveCheese,Kings,BabyRats,CatDamage,Cooperation,Winner,WinType,FinalRound,LastKingAliveRound," + BYTECODE_COLUMNS);
            for (var entry : rounds.entrySet())
                snapshot(out, "ROUND_" + entry.getKey(), entry.getValue(), packages, footer,
                         phases.get(entry.getKey()), seed, last.roundId(), lastKingAlive, bytecodes, bytecodeSnapshots.get(entry.getKey()));
            Round common = rounds.containsKey(1000) ? rounds.get(1000) : last;
            snapshot(out, "COMMON_1000", common, packages, footer,
                     phases.getOrDefault(common.roundId(), coop), seed, last.roundId(), lastKingAlive, bytecodes,
                     bytecodeSnapshots.getOrDefault(common.roundId(), finalBytecodes));
            snapshot(out, "FINAL", last, packages, footer, coop, seed, last.roundId(), lastKingAlive, bytecodes, finalBytecodes);
        }
    }
}
"""


def locate_jdk(value: str | None) -> Path:
    candidates = [Path(value)] if value else []
    if os.environ.get("JAVA_HOME"):
        candidates.append(Path(os.environ["JAVA_HOME"]))
    if shutil.which("javac"):
        candidates.append(Path(shutil.which("javac")).resolve().parent.parent)
    if os.environ.get("LOCALAPPDATA"):
        candidates.extend(sorted((Path(os.environ["LOCALAPPDATA"]) / "Temp" / "battlecats-toolchain").glob("jdk-21*")))
    suffix = ".exe" if os.name == "nt" else ""
    for candidate in candidates:
        if (candidate / "bin" / ("java" + suffix)).is_file() and (candidate / "bin" / ("javac" + suffix)).is_file():
            return candidate.resolve()
    raise RuntimeError("JDK not found. Pass --java-home with the JDK 21 installation directory.")


def locate_engine(value: str | None) -> Path:
    if value:
        return Path(value).resolve(strict=True)
    cache = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
    matches = sorted((cache / "caches" / "modules-2" / "files-2.1" / "org.battlecode" /
                      "battlecode26-java" / ENGINE_VERSION).glob("*/*.jar"))
    if len(matches) != 1:
        raise RuntimeError("Engine JAR not found unambiguously. Run the project setup or pass --engine-jar.")
    return matches[0].resolve()
