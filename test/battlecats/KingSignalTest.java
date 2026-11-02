package battlecats;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import battlecode.common.Direction;
import battlecode.common.GameActionException;
import battlecode.common.GameActionExceptionType;
import battlecode.common.GameConstants;
import battlecode.common.MapLocation;
import battlecode.common.RobotController;
import battlecode.common.RobotInfo;
import battlecode.common.Team;
import battlecode.common.UnitType;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;

/** Public protocol scenarios with real visibility and the engine's king-only write restriction. */
public class KingSignalTest {
  private static final MapLocation HOME = new MapLocation(7, 10);

  @Test
  public void readerPausedBetweenSharedReadsRejectsTheCrossRoundSnapshot() throws Exception {
    for (int pauseAfter = 1; pauseAfter <= 3; pauseAfter++) {
      int[] shared = publishHome(HOME, 100);
      World worker = new World(UnitType.BABY_RAT, shared);
      worker.pauseAfterReads = pauseAfter;

      assertNull("Paused after shared read " + pauseAfter, KingSignal.read(worker.rc));

      // A later complete publication can be used on the worker's next attempt.
      shared[2] = worker.round / 2 + 1;
      assertEquals(new MapLocation(6, 11), KingSignal.read(worker.rc));
    }
  }

  @Test
  public void readerPausedDuringLocalValidationRejectsTheCrossRoundSnapshot() throws Exception {
    MapLocation visibleHome = new MapLocation(12, 10);
    World worker = new World(UnitType.BABY_RAT, publishHome(visibleHome, 100));
    worker.robots.add(robot(Team.A, UnitType.RAT_KING, visibleHome));
    worker.pauseDuringSensing = true;

    assertNull(KingSignal.read(worker.rc));
  }

  @Test
  public void freshBroadcastGuidesAWorkerWhoseKingIsBehindItsVision() throws Exception {
    int[] shared = publishHome(HOME, 100);
    World worker = new World(UnitType.BABY_RAT, shared);
    assertFalse(worker.visible(HOME));

    assertEquals(HOME, KingSignal.read(worker.rc));

    assertEquals("Reading a remote home must not attempt local sensing", 0, worker.senseCalls);
    assertEquals("Baby Rats may read shared memory but must never write it", 0, worker.writes);
  }

  @Test
  public void unpublishedMemoryDoesNotInventAHomeAtTheMapOrigin() throws Exception {
    World worker = new World(UnitType.BABY_RAT, new int[GameConstants.SHARED_ARRAY_SIZE]);

    assertNull(KingSignal.read(worker.rc));

    assertEquals(0, worker.senseCalls);
    assertEquals(0, worker.writes);
  }

  @Test
  public void acceptsTheFreshnessBoundaryAndRejectsTheNextRound() throws Exception {
    for (int age = 0; age <= 4; age++) {
      World worker = new World(UnitType.BABY_RAT, publishHome(HOME, 100));
      worker.round = 100 + age;

      MapLocation actual = KingSignal.read(worker.rc);

      assertEquals("Age in decoded rounds=" + age, age <= 3 ? HOME : null, actual);
    }
  }

  @Test
  public void oddRoundPublicationUsesItsTwoRoundBucketForFreshness() throws Exception {
    int[] shared = publishHome(HOME, 101);
    World worker = new World(UnitType.BABY_RAT, shared);
    worker.round = 103;
    assertEquals(HOME, KingSignal.read(worker.rc));

    worker.round = 104;

    assertNull("A stamp for round 101 decodes to round 100 and is now stale",
        KingSignal.read(worker.rc));
  }

  @Test
  public void rejectsATimestampFromAFutureBucket() throws Exception {
    World worker = new World(UnitType.BABY_RAT, publishHome(HOME, 104));
    worker.round = 103;

    assertNull(KingSignal.read(worker.rc));

    assertEquals(0, worker.senseCalls);
  }

  @Test
  public void timestampsRemainLegalAcrossTheSharedValueAndGameRoundBoundaries() throws Exception {
    int[] rounds = {0, 1, 1023, 1024, 1999, 2000};
    for (int round : rounds) {
      int[] shared = publishHome(HOME, round);
      assertTrue("A published stamp must differ from the unpublished marker", shared[2] > 0);
      for (int slot = 0; slot < 3; slot++) {
        assertTrue("Shared value must remain legal at round " + round,
            shared[slot] >= 0 && shared[slot] <= GameConstants.COMM_ARRAY_MAX_VALUE);
      }
      World worker = new World(UnitType.BABY_RAT, shared);
      worker.round = round;

      assertEquals("Round " + round, HOME, KingSignal.read(worker.rc));
    }
  }

  @Test
  public void rejectsCoordinatesBeyondEitherMapDimensionBeforeTryingToSense() throws Exception {
    MapLocation[] invalidHomes = {
      new MapLocation(24, 10), new MapLocation(7, 24), new MapLocation(1023, 1023)
    };
    for (MapLocation home : invalidHomes) {
      int[] shared = publishHome(HOME, 100);
      // These values are legal shared memory, but cannot identify a tile on this 24-by-24 map.
      shared[0] = home.x;
      shared[1] = home.y;
      World worker = new World(UnitType.BABY_RAT, shared);

      assertNull("Out-of-map home " + home, KingSignal.read(worker.rc));

      assertEquals(0, worker.senseCalls);
    }
  }

  @Test
  public void visibleFriendlyKingSuppliesItsCurrentCenterWhenTheBroadcastTouchesItsEdge()
      throws Exception {
    MapLocation oldCenter = new MapLocation(12, 10);
    MapLocation currentCenter = new MapLocation(12, 11);
    World worker = new World(UnitType.BABY_RAT, publishHome(oldCenter, 100));
    worker.robots.add(robot(Team.A, UnitType.RAT_KING, currentCenter));
    assertTrue(worker.visible(oldCenter));

    assertEquals(currentCenter, KingSignal.read(worker.rc));

    assertEquals(1, worker.senseCalls);
    assertEquals(0, worker.writes);
  }

  @Test
  public void rejectsAVisibleEmptyEnemyOrNonKingTileInsteadOfTrustingTheBroadcast()
      throws Exception {
    MapLocation visibleHome = new MapLocation(12, 10);
    RobotInfo[] occupants = {
      null,
      robot(Team.B, UnitType.RAT_KING, visibleHome),
      robot(Team.A, UnitType.BABY_RAT, visibleHome)
    };
    for (RobotInfo occupant : occupants) {
      World worker = new World(UnitType.BABY_RAT, publishHome(visibleHome, 100));
      if (occupant != null) {
        worker.robots.add(occupant);
      }

      assertNull(KingSignal.read(worker.rc));

      assertEquals(1, worker.senseCalls);
      assertEquals(0, worker.writes);
    }
  }

  @Test
  public void interruptedPublicationNeverExposesMixedCoordinates() throws Exception {
    for (int failAfter = 0; failAfter <= 3; failAfter++) {
      int[] shared = publishHome(HOME, 100);
      World king = new World(UnitType.RAT_KING, shared);
      king.location = new MapLocation(6, 11);
      king.round = 101;
      king.failAfter = failAfter;

      try {
        KingSignal.publish(king.rc);
        fail("Expected an interrupted publication after " + failAfter + " writes");
      } catch (GameActionException expected) {
        assertEquals(GameActionExceptionType.CANT_DO_THAT, expected.getType());
      }

      World worker = new World(UnitType.BABY_RAT, shared);
      worker.round = 102;
      // Before any write the old complete message is valid; every partial update is unpublished.
      assertEquals("Interrupted after " + failAfter + " writes",
          failAfter == 0 ? HOME : null, KingSignal.read(worker.rc));

      king.failAfter = Integer.MAX_VALUE;
      king.round = 102;
      KingSignal.publish(king.rc);
      assertEquals("A later complete publication must recover", king.location,
          KingSignal.read(worker.rc));
    }
  }

  private static int[] publishHome(MapLocation home, int round) throws Exception {
    int[] shared = new int[GameConstants.SHARED_ARRAY_SIZE];
    World king = new World(UnitType.RAT_KING, shared);
    king.location = home;
    king.round = round;

    KingSignal.publish(king.rc);

    assertEquals(4, king.writes);
    assertEquals(home.x, shared[0]);
    assertEquals(home.y, shared[1]);
    return shared;
  }

  private static RobotInfo robot(Team team, UnitType type, MapLocation center) {
    return new RobotInfo(301, team, type, type.health, center, Direction.EAST, 0, 0, null);
  }

  private static final class World implements InvocationHandler {
    final RobotController rc;
    final UnitType type;
    final int[] shared;
    final List<RobotInfo> robots = new ArrayList<>();
    MapLocation location = new MapLocation(10, 10);
    int round = 100;
    int writes;
    int failAfter = Integer.MAX_VALUE;
    int senseCalls;
    int reads;
    int pauseAfterReads = Integer.MAX_VALUE;
    boolean pauseDuringSensing;

    World(UnitType type, int[] shared) {
      this.type = type;
      this.shared = shared;
      rc = (RobotController) Proxy.newProxyInstance(
          RobotController.class.getClassLoader(), new Class<?>[] {RobotController.class}, this);
    }

    boolean visible(MapLocation target) {
      return target.x >= 0 && target.y >= 0 && target.x < 24 && target.y < 24
          && location.isWithinDistanceSquared(target, type.visionConeRadiusSquared,
              Direction.EAST, type.visionConeAngle, type.usesBottomLeftLocationForDistance());
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws GameActionException {
      switch (method.getName()) {
        case "getLocation":
          return location;
        case "getRoundNum":
          return round;
        case "getMapWidth":
        case "getMapHeight":
          return 24;
        case "getTeam":
          return Team.A;
        case "getType":
          return type;
        case "readSharedArray":
          int result = shared[(Integer) args[0]];
          if (++reads == pauseAfterReads) {
            round++;
            shared[2] = 0;
            shared[0] = 6;
            shared[1] = 11;
          }
          return result;
        case "writeSharedArray":
          if (writes == failAfter) {
            throw new GameActionException(
                GameActionExceptionType.CANT_DO_THAT, "Injected interrupted publication");
          }
          int index = (Integer) args[0];
          int value = (Integer) args[1];
          if (type != UnitType.RAT_KING || index < 0 || index >= shared.length
              || value < 0 || value > GameConstants.COMM_ARRAY_MAX_VALUE) {
            throw new GameActionException(
                GameActionExceptionType.CANT_DO_THAT, "Illegal shared-memory write");
          }
          shared[index] = value;
          writes++;
          return null;
        case "canSenseLocation":
          return visible((MapLocation) args[0]);
        case "senseRobotAtLocation":
          MapLocation target = (MapLocation) args[0];
          assertTrue("Local sensing must respect the worker's real vision", visible(target));
          senseCalls++;
          if (pauseDuringSensing) {
            round++;
          }
          for (RobotInfo robot : robots) {
            for (MapLocation part : robot.getType().getAllTypeLocations(robot.getLocation())) {
              if (part.equals(target)) {
                return robot;
              }
            }
          }
          return null;
        default:
          throw new AssertionError("Unsupported controller operation: " + method.getName());
      }
    }
  }
}
