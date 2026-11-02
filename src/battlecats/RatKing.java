package battlecats;

import battlecode.common.*;
import java.util.ArrayList;
import java.util.List;

/** Small stationary spawning baseline so the Baby Rat collector can run in matches. */
public class RatKing {
    private static final int strategic_reserve = 100;
   private int spawned;

    public void takeTurn(RobotController rc) throws GameActionException {
        rc.setIndicatorString("KING spawned=" + spawned);

        avoidEnemyThreats(rc);

        if (rc.getAllCheese() > rc.getCurrentRatCost() + strategic_reserve){
            MapLocation[] potentialSpawnLocations = rc.getAllLocationsWithinRadiusSquared(rc.getLocation(), 8);

            for (MapLocation loc : potentialSpawnLocations){
                if (rc.canBuildRat(loc)){
                    rc.buildRat(loc);
                    break;
                }
            }
        }
        KingSignal.publish(rc);
    }

    private void avoidEnemyThreats(RobotController rc) throws GameActionException {
        Team enemy = rc.getTeam() == Team.A ? Team.B : Team.A;
        // Cats belong to NEUTRAL, so an opponent-only query hides them from evasion.
        RobotInfo[] sensed = rc.senseNearbyRobots();
        List<RobotInfo> allies = findNearbyBabyRatAllies(rc);
        List<RobotInfo> threats = new ArrayList<>();
        for (RobotInfo robot : sensed) {
            if (robot.getType() == UnitType.CAT
                    || (robot.getTeam() == enemy && robot.getType() == UnitType.BABY_RAT)) {
                threats.add(robot);
            }
        }
        if (threats.isEmpty()) {
            return;
        }

        Direction safest = null;
        long safestDirectionScore = Long.MIN_VALUE;
        MapLocation here = rc.getLocation();
        for (Direction direction : Direction.values()) {
            if (direction == Direction.CENTER || !rc.canMove(direction)) continue;
            MapLocation directionLocation = here.add(direction);
            if (!allies.isEmpty() && !withinDeliveryRange(directionLocation, allies)) continue;
            long directionScore = 0;
            for (RobotInfo threat : threats) {
                boolean cat = threat.getType() == UnitType.CAT;
                long priority = cat ? 1_000_000L : 1L;
                if (isInThreatVision(directionLocation, threat)) directionScore -= cat ? 1_000_000_000L : 1_000L;
                directionScore += priority * directionLocation.distanceSquaredTo(threat.getLocation());
            }
            if (directionScore > safestDirectionScore) {
                safestDirectionScore = directionScore;
                safest = direction;
            }
        }
        if (safest != null) {
            rc.move(safest);
        }
    }

    private List<RobotInfo> findNearbyBabyRatAllies(RobotController rc) throws GameActionException {
        List<RobotInfo> allies = new ArrayList<>();
        for (RobotInfo robot : rc.senseNearbyRobots(-1, rc.getTeam())) {
            if (robot.getType() == UnitType.BABY_RAT) allies.add(robot);
        }
        return allies;
    }

    private boolean withinDeliveryRange(MapLocation location, List<RobotInfo> allies) {
        for (RobotInfo ally : allies) {
            if (location.distanceSquaredTo(ally.getLocation())
                    <= GameConstants.CHEESE_TRANSFER_RADIUS_SQUARED) return true;
        }
        return false;
    }

    private boolean isInThreatVision(MapLocation location, RobotInfo threat) {
        UnitType type = threat.getType();
        return threat.getLocation().isWithinDistanceSquared(location,
                type.visionConeRadiusSquared, threat.getDirection(),
                type.visionConeAngle, false);
    }
}
