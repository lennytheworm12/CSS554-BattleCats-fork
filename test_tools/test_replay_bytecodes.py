"""Engine-backed replay fixtures; skipped when JDK 21 / engine 1.2.6 are absent."""

from __future__ import annotations

import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sim_runtime import REPLAY_READER, locate_engine, locate_jdk


# Use the engine's actual FlatBuffers builders, including struct-valued unions.
FIXTURE = r"""
import battlecode.schema.*;
import com.google.flatbuffers.FlatBufferBuilder;
import java.nio.file.*;
import java.util.zip.*;
public class BytecodeReplayFixture {
    static int turn(FlatBufferBuilder b, int id, int used, byte action, int value) {
        int types = 0, actions = 0;
        if (action != Action.NONE) {
            int payload = action == Action.SpawnAction
                ? SpawnAction.createSpawnAction(b, value, 1, 1, 0, 0, (byte)1, RobotType.RAT)
                : action == Action.RatNap ? RatNap.createRatNap(b, value)
                : action == Action.ThrowRat ? ThrowRat.createThrowRat(b, value, 0)
                : UpgradeToRatKing.createUpgradeToRatKing(b, value);
            actions = Turn.createActionsVector(b, new int[]{payload});
            types = Turn.createActionsTypeVector(b, new byte[]{action});
        }
        return Turn.createTurn(b, id, 100, 0, 0, 0, 0, used, 1, 1, 0, types, actions, true);
    }
    static int round(FlatBufferBuilder b, int number, int[] turns) {
        int ids = Round.createTeamIdsVector(b, new int[]{1,2});
        int kings = Round.createTeamAliveRatKingsVector(b, new int[]{1001,1001});
        int cheese = Round.createTeamCheeseTransferredVector(b, new int[]{40,60});
        int babies = Round.createTeamAliveBabyRatsVector(b, new int[]{2,0});
        int turnsVector = Round.createTurnsVector(b, turns);
        Round.startRound(b);
        Round.addRoundId(b, number); Round.addTeamIds(b, ids);
        Round.addTeamAliveRatKings(b, kings); Round.addTeamCheeseTransferred(b, cheese);
        Round.addTeamAliveBabyRats(b, babies); Round.addTurns(b, turnsVector);
        return EventWrapper.createEventWrapper(b, Event.Round, Round.endRound(b));
    }
    public static void main(String[] args) throws Exception {
        String mode = args[0]; FlatBufferBuilder b = new FlatBufferBuilder(4096);
        int a = TeamData.createTeamData(b, b.createString("A"), b.createString("battlecats"), (byte)1);
        int c = TeamData.createTeamData(b, b.createString("B"), b.createString("battlecats"), (byte)2);
        int teams = GameHeader.createTeamsVector(b, new int[]{a,c});
        int baby = RobotTypeMetadata.createRobotTypeMetadata(b, RobotType.RAT, 0,0,0,0,0,0,0,0,17500);
        int king = RobotTypeMetadata.createRobotTypeMetadata(b, RobotType.RAT_KING, 0,0,0,0,0,0,0,0,20000);
        int metadata = GameHeader.createRobotTypeMetadataVector(b,
            mode.equals("metadata") ? new int[]{king} : new int[]{baby,king});
        int header = EventWrapper.createEventWrapper(b, Event.GameHeader,
            GameHeader.createGameHeader(b, b.createString("1.2.6"), teams, metadata, 0));
        InitialBodyTable.startSpawnActionsVector(b, 3);
        SpawnAction.createSpawnAction(b, 33, 1,1,0,0,(byte)0,RobotType.CAT);
        SpawnAction.createSpawnAction(b, 22, 1,1,0,0,(byte)2,RobotType.RAT_KING);
        SpawnAction.createSpawnAction(b, 11, 1,1,0,0,(byte)1,RobotType.RAT);
        int bodies = InitialBodyTable.createInitialBodyTable(b, b.endVector());
        GameMap.startGameMap(b); GameMap.addInitialBodies(b, bodies); GameMap.addRandomSeed(b, 42);
        int map = GameMap.endGameMap(b);
        int match = EventWrapper.createEventWrapper(b, Event.MatchHeader, MatchHeader.createMatchHeader(b, map, 2000));
        int r100 = round(b, 100, new int[]{
            turn(b,11,100,Action.SpawnAction,12), turn(b,22,200,Action.NONE,0),
            turn(b,12,300,Action.NONE,0), turn(b,33,0,Action.NONE,0)});
        int r101 = round(b,101,new int[]{turn(b,11,17502,Action.UpgradeToRatKing,11),
            turn(b,22,0,Action.NONE,0),turn(b,12,10,Action.NONE,0)});
        int r102 = round(b,102,mode.equals("duplicate")
            ? new int[]{turn(b,11,400,Action.NONE,0),turn(b,11,400,Action.NONE,0)}
            : new int[]{turn(b,mode.equals("unknown") ? 99 : 11,400,
                mode.equals("carry") ? Action.RatNap : mode.equals("throw") ? Action.ThrowRat : Action.NONE,12)});
        int footer = EventWrapper.createEventWrapper(b, Event.MatchFooter,
            MatchFooter.createMatchFooter(b,(byte)1,WinType.COIN_FLIP,102,0,0));
        int events = GameWrapper.createEventsVector(b,new int[]{header,match,r100,r101,r102,footer});
        b.finish(GameWrapper.createGameWrapper(b,events,0,0));
        try (var out = new GZIPOutputStream(Files.newOutputStream(Path.of(args[1])))) {
            out.write(b.sizedByteArray());
        }
    }
}
"""


class ReplayBytecodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.jdk, cls.engine = locate_jdk(None), locate_engine(None)
        except (RuntimeError, OSError) as error:
            raise unittest.SkipTest(str(error)) from error
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        (cls.root / "SimulationReplayMetrics.java").write_text(REPLAY_READER, encoding="utf-8")
        (cls.root / "BytecodeReplayFixture.java").write_text(FIXTURE, encoding="utf-8")
        suffix = ".exe" if sys.platform == "win32" else ""
        cls.java = str(cls.jdk / "bin" / ("java" + suffix))
        import os
        cls.classpath = os.pathsep.join([str(cls.root), str(cls.engine)])
        cls.run_command([str(cls.jdk / "bin" / ("javac" + suffix)), "--release", "21",
                         "-cp", str(cls.engine), "-d", str(cls.root),
                         str(cls.root / "SimulationReplayMetrics.java"),
                         str(cls.root / "BytecodeReplayFixture.java")])

    @staticmethod
    def run_command(argv):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def read_fixture(self, mode="normal", side="A"):
        replay = self.root / (mode + side + ".bc26")
        metrics, turns = replay.with_suffix(".csv"), replay.with_suffix(".turns.csv")
        self.run_command([self.java, "-cp", self.classpath, "BytecodeReplayFixture", mode, str(replay)])
        self.run_command([self.java, "-cp", self.classpath, "SimulationReplayMetrics",
                          str(replay), str(metrics), "100", side, str(turns)])
        with metrics.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        with turns.open(newline="", encoding="utf-8") as handle:
            samples = list(csv.DictReader(handle))
        return rows, samples

    def test_spawn_promotion_budget_overshoot_and_checkpoint_copies(self):
        rows, samples = self.read_fixture()
        start = next(row for row in rows if row["Checkpoint"] == "ROUND_100" and row["Side"] == "A")
        final = next(row for row in rows if row["Checkpoint"] == "FINAL" and row["Side"] == "A")
        self.assertEqual("AVAILABLE", final["BytecodeStatus"])
        self.assertEqual(("2", "400", "300"), tuple(start[k] for k in
                         ("BabyRatTurns", "BabyRatBytecodesTotal", "BabyRatBytecodesMax")))
        self.assertEqual(("4", "17912", "17502", "17500", "1"), tuple(final[k] for k in
                         ("BabyRatTurns", "BabyRatBytecodesTotal", "BabyRatBytecodesMax",
                          "BabyRatBytecodeLimit", "BabyRatBudgetHits")))
        self.assertEqual(("1", "400", "20000"), tuple(final[k] for k in
                         ("RatKingTurns", "RatKingBytecodesTotal", "RatKingBytecodeLimit")))
        promoted = [row for row in samples if row["RobotId"] == "11"]
        self.assertEqual(["BABY_RAT", "BABY_RAT", "RAT_KING"], [r["UnitType"] for r in promoted])
        self.assertEqual(7, len(samples))  # Neutral cat records are excluded.
        self.assertEqual("0", next(r for r in samples if r["RobotId"] == "22" and r["Round"] == "101")["BytecodesUsed"])

    def test_side_swap_changes_role_without_using_shared_package_name(self):
        _, samples = self.read_fixture(side="B")
        self.assertEqual({"baseline"}, {r["Team"] for r in samples if r["Side"] == "A"})
        self.assertEqual({"candidate"}, {r["Team"] for r in samples if r["Side"] == "B"})

    def test_ambiguous_or_unattributable_samples_never_become_usage(self):
        for mode in ("duplicate", "unknown", "metadata", "carry", "throw"):
            with self.subTest(mode=mode):
                rows, samples = self.read_fixture(mode)
                self.assertEqual([], samples)
                for row in rows:
                    self.assertTrue(row["BytecodeStatus"].startswith("UNAVAILABLE"))
                    self.assertEqual("", row["BabyRatTurns"])
                    self.assertEqual("", row["RatKingBytecodesTotal"])
                self.assertEqual("40", next(r for r in rows if r["Side"] == "A")["DeliveredCheese"])


if __name__ == "__main__":
    unittest.main()
