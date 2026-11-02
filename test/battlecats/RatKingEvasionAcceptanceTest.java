package battlecats;

import battlecode.common.*;
import org.junit.Test;
import java.lang.reflect.*;
import java.util.*;
import static org.junit.Assert.*;

/** Minimal acceptance coverage for the rat king's evasion helpers. */
public class RatKingEvasionAcceptanceTest {
    private static final MapLocation KING = new MapLocation(10, 10);
    private static final MapLocation CAT_WEST = new MapLocation(7, 10);
    private static final MapLocation ALLY_NEAR = new MapLocation(10, 11);
    private static final MapLocation ALLY_FAR = new MapLocation(15, 15);

  @Test
  public void publishesItsFinalLocationAfterEvadingACat() throws Exception {
    World world = world(robot(UnitType.CAT, CAT_WEST, Team.NEUTRAL));

    new RatKing().takeTurn(world.rc);

    assertEquals(1, world.moves);
    assertEquals(world.location.x, world.shared[0]);
    assertEquals(world.location.y, world.shared[1]);
    assertEquals("Round 100 is published in two-round bucket 51", 51, world.shared[2]);
  }

  @Test
  public void neutralCatTriggersTheExistingEvasionPolicy() throws Exception {
    World world = world(robot(UnitType.CAT, CAT_WEST, Team.NEUTRAL));

    new RatKing().takeTurn(world.rc);

    assertEquals("The visible neutral cat must trigger an escape move", 1, world.moves);
    assertTrue(world.location.distanceSquaredTo(CAT_WEST) > KING.distanceSquaredTo(CAT_WEST));
  }

    /* SPEC: Enemy threats trigger evasion.
       VALUE: The king moves farther from a sensed cat.
       SCENARIO: An enemy cat is west of the king.
       PREVENTS: Remaining exposed to an enemy attack. */
    @Test public void avoidEnemyThreatsMovesFromEnemyCat() throws Exception {
        World world = world(enemy(UnitType.CAT, CAT_WEST));
        new RatKing().takeTurn(world.rc);
        assertTrue(world.location.distanceSquaredTo(CAT_WEST) > 9);
    }

    /* SPEC: Threat avoidance is inactive without enemy threats.
       VALUE: The king remains stationary.
       SCENARIO: Only a friendly unit is sensed.
       PREVENTS: Unnecessary movement. */
    @Test public void avoidEnemyThreatsDoesNotMoveWithoutEnemyThreats() throws Exception {
        World world = world(friend(UnitType.BABY_RAT, ALLY_NEAR));
        new RatKing().takeTurn(world.rc);
        assertEquals(KING, world.location);
        assertEquals(0, world.moves);
    }

    /* SPEC: Friendly baby-rat allies are discovered.
       VALUE: A nearby friendly baby rat is returned.
       SCENARIO: A friendly baby rat is sensed.
       PREVENTS: Losing valid cheese-delivery allies. */
    @Test public void findNearbyBabyRatAlliesReturnsFriendlyBabyRats() throws Exception {
        World world = world(friend(UnitType.BABY_RAT, ALLY_NEAR));
        assertEquals(1, findAllies(world).size());
    }

    /* SPEC: Invalid units are excluded from the ally list.
       VALUE: Enemy baby rats and non-baby units are rejected.
       SCENARIO: An enemy baby rat and enemy cat are sensed.
       PREVENTS: Maintaining delivery range to the wrong unit. */
    @Test public void findNearbyBabyRatAlliesRejectsInvalidAllies() throws Exception {
        World world = world(enemy(UnitType.BABY_RAT, ALLY_NEAR), enemy(UnitType.CAT, ALLY_FAR));
        assertTrue(findAllies(world).isEmpty());
    }

    /* SPEC: Nearby allies are within delivery range.
       VALUE: A legal transfer tile is accepted.
       SCENARIO: The candidate is adjacent to a friendly baby rat.
       PREVENTS: Rejecting valid cheese delivery. */
    @Test public void withinDeliveryRangeAcceptsNearbyAlly() throws Exception {
        World world = world();
        assertTrue(withinDeliveryRange(world, new MapLocation(11, 10),
                Collections.singletonList(friend(UnitType.BABY_RAT, ALLY_NEAR))));
    }

    /* SPEC: Distant allies are outside delivery range.
       VALUE: An invalid transfer tile is rejected.
       SCENARIO: The candidate is far from the friendly baby rat.
       PREVENTS: Claiming delivery is possible when it is not. */
    @Test public void withinDeliveryRangeRejectsDistantAlly() throws Exception {
        World world = world();
        assertFalse(withinDeliveryRange(world, KING,
                Collections.singletonList(friend(UnitType.BABY_RAT, ALLY_FAR))));
    }

    /* SPEC: Threat vision identifies visible tiles.
       VALUE: A tile in front of an enemy cat is visible.
       SCENARIO: The candidate is east of an east-facing cat.
       PREVENTS: Failing to evade a visible threat. */
    @Test public void isInThreatVisionAcceptsVisibleTile() throws Exception {
        assertTrue(isInThreatVision(new MapLocation(10, 10), enemy(UnitType.CAT, CAT_WEST)));
    }

    /* SPEC: Threat vision rejects distant tiles.
       VALUE: A tile outside the cone is not visible.
       SCENARIO: The candidate is far from the enemy cat.
       PREVENTS: Evasion from non-threatening locations. */
    @Test public void isInThreatVisionRejectsDistantTile() throws Exception {
        assertFalse(isInThreatVision(new MapLocation(0, 0), enemy(UnitType.CAT, CAT_WEST)));
    }

    @SuppressWarnings("unchecked")
    private static List<RobotInfo> findAllies(World world) throws Exception {
        Method method = RatKing.class.getDeclaredMethod("findNearbyBabyRatAllies", RobotController.class);
        method.setAccessible(true);
        return (List<RobotInfo>) method.invoke(new RatKing(), world.rc);
    }
    private static boolean withinDeliveryRange(World world, MapLocation location, List<RobotInfo> allies) throws Exception {
        Method method = RatKing.class.getDeclaredMethod("withinDeliveryRange", MapLocation.class, List.class);
        method.setAccessible(true);
        return (Boolean) method.invoke(new RatKing(), location, allies);
    }
    private static boolean isInThreatVision(MapLocation location, RobotInfo threat) throws Exception {
        Method method = RatKing.class.getDeclaredMethod("isInThreatVision", MapLocation.class, RobotInfo.class);
        method.setAccessible(true);
        return (Boolean) method.invoke(new RatKing(), location, threat);
    }
    private static RobotInfo enemy(UnitType type, MapLocation location) { return robot(type, location, Team.B); }
    private static RobotInfo friend(UnitType type, MapLocation location) { return robot(type, location, Team.A); }
    private static RobotInfo robot(UnitType type, MapLocation location, Team team) {
        return new RobotInfo(location.x * 100 + location.y, team, type, 1, location, Direction.EAST, 0, 0, null);
    }
    private static World world(RobotInfo... robots) {
        World world = new World();
        Collections.addAll(world.robots, robots);
        return world;
    }

    private static final class World implements InvocationHandler {
        final RobotController rc;
        final List<RobotInfo> robots = new ArrayList<>();
        MapLocation location = KING;
        int moves;
        final int[] shared = new int[GameConstants.SHARED_ARRAY_SIZE];
        World() { rc = (RobotController) Proxy.newProxyInstance(RobotController.class.getClassLoader(), new Class<?>[]{RobotController.class}, this); }
        public Object invoke(Object proxy, Method method, Object[] args) {
            switch (method.getName()) {
                case "getLocation": return location;
                case "getTeam": return Team.A;
                case "getType": return UnitType.RAT_KING;
                case "getRoundNum": return 100;
                case "getAllCheese": case "getCurrentRatCost": return 0;
                case "senseNearbyRobots": {
                    Team requested = args != null && args.length > 1 ? (Team) args[1] : null;
                    return robots.stream().filter(r -> (requested == null || r.getTeam() == requested) && location.distanceSquaredTo(r.getLocation()) <= 100).toArray(RobotInfo[]::new);
                }
                case "canMove": return true;
                case "move": location = location.add((Direction) args[0]); moves++; return null;
                case "writeSharedArray": shared[(Integer) args[0]] = (Integer) args[1]; return null;
                case "setIndicatorString": return null;
                default: return method.getReturnType() == boolean.class ? false : method.getReturnType() == int.class ? 0 : null;
            }
        }
    }
}
