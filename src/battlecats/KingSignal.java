package battlecats;

import battlecode.common.GameActionException;
import battlecode.common.MapLocation;
import battlecode.common.RobotController;
import battlecode.common.RobotInfo;
import battlecode.common.UnitType;

/** Fresh home coordinates for this bot's single king; only the king publishes. */
public final class KingSignal {
  private static final int X_SLOT = 0;
  private static final int Y_SLOT = 1;
  private static final int STAMP_SLOT = 2;
  // Experimental freshness window: accept the previous king turn plus timestamp quantization.
  private static final int MAX_AGE_ROUNDS = 3;

  private KingSignal() {}

  /** Publishes after king movement. Engine 1.2.6 only permits kings to write shared memory. */
  public static void publish(RobotController rc) throws GameActionException {
    // A bytecode pause between coordinate writes must not expose a mixed home as fresh.
    rc.writeSharedArray(STAMP_SLOT, 0);
    rc.writeSharedArray(X_SLOT, rc.getLocation().x);
    rc.writeSharedArray(Y_SLOT, rc.getLocation().y);
    // Shared values are at most 1023. Two-round buckets fit all 2000 game rounds;
    // zero remains an unpublished marker, including when the king stands at (0,0).
    rc.writeSharedArray(STAMP_SLOT, rc.getRoundNum() / 2 + 1);
  }

  /** Returns a fresh, valid home, or null. A visible tile takes precedence over the broadcast. */
  public static MapLocation read(RobotController rc) throws GameActionException {
    int round = rc.getRoundNum();
    int stamp = rc.readSharedArray(STAMP_SLOT);
    if (stamp == 0) {
      return null;
    }
    int age = round - 2 * (stamp - 1);
    if (age < 0 || age > MAX_AGE_ROUNDS) {
      return null;
    }
    int x = rc.readSharedArray(X_SLOT);
    int y = rc.readSharedArray(Y_SLOT);
    if (x >= rc.getMapWidth() || y >= rc.getMapHeight()) {
      return null;
    }
    MapLocation location = new MapLocation(x, y);
    if (rc.canSenseLocation(location)) {
      RobotInfo robot = rc.senseRobotAtLocation(location);
      location = robot != null && robot.getTeam() == rc.getTeam()
              && robot.getType() == UnitType.RAT_KING
          ? robot.getLocation() : null;
    }
    // A paused reader can resume after the king starts another publication. Discard that read.
    return rc.getRoundNum() == round ? location : null;
  }
}
