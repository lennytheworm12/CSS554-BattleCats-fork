package battlecats;

import battlecode.common.*;

/** Sprint 1 collector: discover cheese, pick it up, return, and deliver. */
public class BabyRat {
    private static final int TARGET_TIMEOUT = 80;
    private static final int carryAmount = 20;
    private final Navigation navigation;
    private MapLocation kingLocation;
    private MapLocation cheeseTarget;
    private int targetRound;
    private MapLocation ignoredCheese;
    private int ignoreUntilRound;
    private int homeScans;
    private int deliveries;

    public BabyRat(int robotId) {
        navigation = new Navigation(robotId);
    }

    public void takeTurn(RobotController rc) throws GameActionException {
        if (rc.isBeingCarried() || rc.isBeingThrown()) {
            return;
        }
        rememberKing(rc);
        // A newborn inherits its king's facing; the king can initially be behind it.
        if (kingLocation == null && homeScans < 4) {
            rc.setIndicatorString("SCAN_HOME");
            if (rc.canTurn()) {
                rc.turn(rc.getDirection().rotateRight().rotateRight());
                homeScans++;
            }
            return;
        }
        // A full 20-cheese pickup must not wait indefinitely for a second pile.
        if (rc.getRawCheese() >= carryAmount) {
            returnCheese(rc);
            return;
        }
        findCheese(rc);
        if (cheeseTarget == null) {
            rc.setIndicatorString("SEARCH delivered=" + deliveries);
            navigation.explore(rc);
        } else {
            face(rc, cheeseTarget);
            if (!pickUp(rc)) {
                navigation.moveToward(rc, cheeseTarget);
                pickUp(rc);
            }
            rc.setIndicatorString((rc.getRawCheese() > 0 ? "RETURN" : "COLLECT")
                    + " delivered=" + deliveries);
        }
    }

    private void findCheese(RobotController rc) throws GameActionException {
        if (cheeseTarget != null && rc.getRoundNum() - targetRound >= TARGET_TIMEOUT) {
            ignoredCheese = cheeseTarget;
            ignoreUntilRound = rc.getRoundNum() + 40;
            cheeseTarget = null;
        }
        if (cheeseTarget != null && rc.canSenseLocation(cheeseTarget)
                && rc.senseMapInfo(cheeseTarget).getCheeseAmount() == 0) {
            cheeseTarget = null;
        }
        MapLocation closest = cheeseTarget;
        int bestDistance = closest == null ? Integer.MAX_VALUE : rc.getLocation().distanceSquaredTo(closest);
        for (MapInfo info : rc.senseNearbyMapInfos()) {
            if (info.getCheeseAmount() <= 0) {
                continue;
            }
            MapLocation location = info.getMapLocation();
            if (location.equals(ignoredCheese) && rc.getRoundNum() < ignoreUntilRound) {
                continue;
            }
            int distance = rc.getLocation().distanceSquaredTo(location);
            if (distance < bestDistance) {
                closest = location;
                bestDistance = distance;
            }
        }
        if (closest != null && !closest.equals(cheeseTarget)) {
            cheeseTarget = closest;
            targetRound = rc.getRoundNum();
        }
    }

    private boolean pickUp(RobotController rc) throws GameActionException {
        if (cheeseTarget != null && rc.canPickUpCheese(cheeseTarget)) {
            rc.pickUpCheese(cheeseTarget);
            cheeseTarget = null;
            return true;
        }
        return false;
    }

    private void returnCheese(RobotController rc) throws GameActionException {
        rc.setIndicatorString("RETURN raw=" + rc.getRawCheese() + " delivered=" + deliveries);
        if (kingLocation == null) {
            navigation.explore(rc);
            return;
        }
        face(rc, kingLocation);
        rememberKing(rc);
        if (deliver(rc)) {
            return;
        }
        if (kingLocation != null) {
            navigation.moveToward(rc, kingLocation);
            rememberKing(rc);
            deliver(rc);
        }
    }

    private boolean deliver(RobotController rc) throws GameActionException {
        int amount = rc.getRawCheese();
        if (kingLocation == null || amount == 0) {
            return false;
        }
        // Kings occupy 3x3: an edge may be reachable before the center is reachable.
        for (MapLocation part : UnitType.RAT_KING.getAllTypeLocations(kingLocation)) {
            if (rc.canTransferCheese(part, amount)) {
                rc.transferCheese(part, amount);
                deliveries++;
                rc.setIndicatorString("DELIVER amount=" + amount + " delivered=" + deliveries);
                System.out.println("DELIVER rat=" + rc.getID() + " cheese=" + amount);
                return true;
            }
        }
        return false;
    }

  private void rememberKing(RobotController rc) throws GameActionException {
    boolean locallyVerified = false;
    if (kingLocation != null && rc.canSenseLocation(kingLocation)) {
      RobotInfo king = rc.senseRobotAtLocation(kingLocation);
      if (king == null || king.getTeam() != rc.getTeam() || king.getType() != UnitType.RAT_KING) {
        kingLocation = null;
      } else {
        kingLocation = king.getLocation();
        locallyVerified = true;
      }
    }
    int nearest = kingLocation == null
        ? Integer.MAX_VALUE : rc.getLocation().distanceSquaredTo(kingLocation);
    for (RobotInfo robot : rc.senseNearbyRobots(-1, rc.getTeam())) {
      if (robot.getType() == UnitType.RAT_KING) {
        int distance = rc.getLocation().distanceSquaredTo(robot.getLocation());
        if (distance <= nearest) {
          kingLocation = robot.getLocation();
          nearest = distance;
          locallyVerified = true;
        }
      }
    }
    if (!locallyVerified) {
      MapLocation published = KingSignal.read(rc);
      if (published != null) {
        kingLocation = published;
      }
    }
  }

    private void face(RobotController rc, MapLocation location) throws GameActionException {
        if (!rc.getLocation().equals(location)) {
            Direction direction = rc.getLocation().directionTo(location);
            if (rc.canTurn(direction)) {
                rc.turn(direction);
            }
        }
    }
}
