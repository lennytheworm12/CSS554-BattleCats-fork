package battlecats;

import battlecode.common.*;
import org.junit.Test;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.*;

import static org.junit.Assert.*;

/** Behavioral scenarios; the controller exposes only the engine's real vision cone. */
public class CollectorTest {
  @Test
  public void stalePublicationRetainsAPreviouslyKnownRemoteHome() throws Exception {
    World world = new World(at(16, 5), Direction.EAST);
    world.shared[0] = 4;
    world.shared[1] = 5;
    world.shared[2] = 1;
    world.rawCheese = 20;
    BabyRat baby = new BabyRat(world.id);
    world.takeTurn(baby);
    world.round = 10;
    world.shared[1] = 12;

    world.takeTurn(baby);

    assertEquals("A stale message must not replace the remembered delivery destination", at(14, 5),
        world.location);
    assertEquals(20, world.rawCheese);
  }

  @Test
  public void visibleKingTakesPriorityOverARemotePublication() throws Exception {
    World world = new World(at(16, 5), Direction.EAST);
    world.robots.add(king(101, Team.A, at(19, 5)));
    world.shared[0] = 4;
    world.shared[1] = 5;
    world.shared[2] = 1;
    world.rawCheese = 20;

    world.takeTurn(new BabyRat(world.id));

    assertEquals(20, world.delivered);
    assertEquals(Arrays.asList(101), world.recipientIds);
  }

  @Test
  public void stalePublicationLeavesTheExistingHomeScanInControl() throws Exception {
    World world = new World(at(16, 5), Direction.EAST);
    world.shared[0] = 4;
    world.shared[1] = 5;
    world.shared[2] = 1;
    world.round = 10;
    world.rawCheese = 20;

    world.takeTurn(new BabyRat(world.id));

    assertEquals(at(16, 5), world.location);
    assertEquals(1, world.turns);
    assertEquals(20, world.rawCheese);
  }

  @Test
  public void freshRemoteHomeStartsDeliveryWithoutScanningForTheKing() throws Exception {
    World world = new World(at(16, 5), Direction.EAST);
    world.robots.add(king(101, Team.A, at(4, 5)));
    world.shared[0] = 4;
    world.shared[1] = 5;
    world.shared[2] = 1;
    world.rawCheese = 20;

    world.takeTurn(new BabyRat(world.id));

    assertEquals("A full carrier should travel toward the remote home immediately", at(15, 5),
        world.location);
    assertEquals(20, world.rawCheese);
  }

  @Test
  public void freshPublicationUpdatesARememberedKingOutsideVision() throws Exception {
    World world = new World(at(16, 5), Direction.EAST);
    world.shared[0] = 4;
    world.shared[1] = 5;
    world.shared[2] = 1;
    world.rawCheese = 20;
    BabyRat baby = new BabyRat(world.id);
    world.takeTurn(baby);
    world.shared[1] = 12;
    world.shared[2] = world.round / 2 + 1;

    world.takeTurn(baby);

    assertEquals("The next delivery step must use the king's updated location", at(14, 6),
        world.location);
    assertEquals(20, world.rawCheese);
  }

  @Test
  public void depositsTwentyWithoutWaitingForAnotherPile() throws Exception {
    int[] startingLoads = {0, 19, 20, 21};
    for (int cargo : startingLoads) {
      World world = collectorWorld();
      world.rawCheese = cargo;
      MapLocation anotherPile = at(6, 5);
      world.cheese.put(anotherPile, 5);

      world.takeTurn(new BabyRat(world.id));

      boolean shouldReturn = cargo >= 20;
      assertEquals("Delivered from starting load " + cargo,
          shouldReturn ? cargo : 0, world.delivered);
      assertEquals("Cargo remaining from starting load " + cargo,
          shouldReturn ? 0 : cargo + 5, world.rawCheese);
      assertEquals("A returning worker leaves the other pile alone",
          shouldReturn ? Collections.emptyList() : Arrays.asList(anotherPile), world.pickups);
    }
  }

    @Test
    public void collectsDeliversAndStartsAnotherTrip() throws Exception {
        World world = collectorWorld();
        world.cheese.put(at(9, 4), 35);
        BabyRat baby = new BabyRat(world.id);

        runUntilDelivered(baby, world, 35, 35);
        assertEquals(0, world.rawCheese);
        assertEquals(Arrays.asList(at(9, 4)), world.pickups);

        // New cheese appears in the collector's view after its first delivery.
        world.cheese.put(at(10, 6), 25);
        assertTrue(world.visible(at(10, 6)));
        runUntilDelivered(baby, world, 60, 35);

        assertEquals(0, world.rawCheese);
        assertEquals(Arrays.asList(at(9, 4), at(10, 6)), world.pickups);
        assertEquals(2, world.transfers.size());
    }

    @Test
    public void newbornLooksBehindItForItsKingBeforeLeaving() throws Exception {
        World world = new World(at(7, 5), Direction.EAST);
        world.robots.add(king(101, Team.A, at(4, 5)));
        world.cheese.put(at(10, 5), 30);
        BabyRat baby = new BabyRat(world.id);
        assertFalse(world.visible(at(4, 5)));

        world.takeTurn(baby);
        assertEquals(at(7, 5), world.location);
        assertEquals(0, world.rawCheese);
        assertEquals(1, world.turns);

        for (int i = 0; i < 4 && world.kingSightings == 0; i++) {
            world.takeTurn(baby);
        }
        assertTrue("The newborn must discover its king outside its initial FOV", world.kingSightings > 0);
    }

    @Test
    public void replacesCheeseTargetWhenAnotherRatHasEmptiedIt() throws Exception {
        World world = collectorWorld();
        MapLocation depleted = at(9, 4);
        MapLocation replacement = at(7, 4);
        world.cheese.put(depleted, 20);
        BabyRat baby = new BabyRat(world.id);
        world.takeTurn(baby);
        assertEquals(0, world.rawCheese);

        world.cheese.remove(depleted);
        world.cheese.put(replacement, 15);
        assertTrue(world.visible(depleted));
        assertTrue(world.visible(replacement));
        world.takeTurn(baby);

        assertEquals(15, world.rawCheese);
        assertEquals(Arrays.asList(replacement), world.pickups);
    }

    @Test
    public void deliversAtReachableKingEdgeWithoutReachingItsCenter() throws Exception {
        World world = new World(at(5, 5), Direction.EAST);
        MapLocation center = at(9, 5);
        world.robots.add(king(101, Team.A, center));
        world.rawCheese = 40;
        BabyRat baby = new BabyRat(world.id);
        assertTrue(world.location.distanceSquaredTo(center) > GameConstants.CHEESE_TRANSFER_RADIUS_SQUARED);

        world.takeTurn(baby);

        assertEquals(40, world.delivered);
        assertEquals(at(5, 5), world.location);
        assertNotEquals(center, world.transfers.get(0));
    }

    @Test
    public void retainsCargoAndFindsAnotherFriendlyKingWhenHomeIsLost() throws Exception {
        World world = collectorWorld();
        world.cheese.put(at(9, 4), 30);
        BabyRat baby = new BabyRat(world.id);
        for (int i = 0; i < 15 && world.rawCheese == 0; i++) {
            world.takeTurn(baby);
        }
        assertEquals(30, world.rawCheese);

        world.robots.clear();
        world.robots.add(king(201, Team.B, at(8, 7)));
        RobotInfo replacement = king(102, Team.A, at(12, 5));
        world.robots.add(replacement);
        world.takeTurn(baby);
        assertEquals("Cargo must survive discovery that the old king is gone", 30, world.rawCheese);
        runUntilDelivered(baby, world, 30, 35);

        assertEquals(0, world.rawCheese);
        assertEquals(Arrays.asList(replacement.getID()), world.recipientIds);
    }

    @Test
    public void navigationDetoursAroundWall() throws Exception {
        World world = new World(at(4, 4), Direction.EAST);
        world.walls.addAll(Arrays.asList(at(5, 3), at(5, 4), at(5, 5)));
        Navigation navigation = new Navigation(world.id);
        MapLocation destination = at(8, 4);

        for (int i = 0; i < 20 && !world.location.equals(destination); i++) {
            navigation.moveToward(world.rc, destination);
            world.nextRound();
        }
        assertEquals(destination, world.location);
        assertTrue("The route must include a detour", world.moves > 4);
    }

    @Test
    public void triesDifferentCheeseAfterAnUnreachableTarget() throws Exception {
        World world = collectorWorld();
        MapLocation inaccessible = at(8, 4);
        MapLocation alternative = at(9, 5);
        world.cheese.put(inaccessible, 20);
        world.cheese.put(alternative, 25);
        for (Direction direction : Direction.values()) {
            if (direction != Direction.CENTER) world.walls.add(world.location.add(direction));
        }
        BabyRat baby = new BabyRat(world.id);

        for (int i = 0; i < 82; i++) world.takeTurn(baby);
        assertEquals(0, world.rawCheese);
        world.walls.clear();
        for (int i = 0; i < 8 && world.rawCheese == 0; i++) world.takeTurn(baby);

        assertEquals("An unreachable pile should not prevent trying another observed pile", 25, world.rawCheese);
        assertEquals(Arrays.asList(alternative), world.pickups);
        assertEquals(Integer.valueOf(20), world.cheese.get(inaccessible));
    }

    @Test
    public void navigationRecoversAfterTemporaryTrafficClears() throws Exception {
        World world = new World(at(5, 5), Direction.EAST);
        world.walls.addAll(Arrays.asList(at(6, 5), at(6, 4), at(5, 4), at(4, 4)));
        Navigation navigation = new Navigation(world.id);
        MapLocation destination = at(15, 5);
        navigation.moveToward(world.rc, destination);
        world.nextRound();
        world.walls.clear();

        for (int i = 0; i < 24 && !world.location.equals(destination); i++) {
            navigation.moveToward(world.rc, destination);
            world.nextRound();
        }
        assertEquals("Cleared traffic must not leave the rat walking in a cycle", destination, world.location);
    }

    private static World collectorWorld() {
        World world = new World(at(5, 5), Direction.EAST);
        world.robots.add(king(101, Team.A, at(8, 7)));
        return world;
    }

    private static void runUntilDelivered(BabyRat baby, World world, int total, int maxTurns) throws Exception {
        for (int i = 0; i < maxTurns && world.delivered < total; i++) {
            world.takeTurn(baby);
        }
        assertEquals("The collector must complete its cheese round trip", total, world.delivered);
    }

    private static MapLocation at(int x, int y) {
        return new MapLocation(x, y);
    }

    private static RobotInfo king(int id, Team team, MapLocation center) {
        return new RobotInfo(id, team, UnitType.RAT_KING, 600, center, Direction.EAST, 0, 0, null);
    }

    /** Minimal scenario world, not a second strategy implementation or an engine substitute. */
    private static final class World implements InvocationHandler {
        final int id = 2;
        final int size = 24;
        final Map<MapLocation, Integer> cheese = new LinkedHashMap<>();
        final Set<MapLocation> walls = new HashSet<>();
        final List<RobotInfo> robots = new ArrayList<>();
        final List<MapLocation> pickups = new ArrayList<>();
        final List<MapLocation> transfers = new ArrayList<>();
        final List<Integer> recipientIds = new ArrayList<>();
        final int[] shared = new int[GameConstants.SHARED_ARRAY_SIZE];
        final RobotController rc;
        MapLocation location;
        Direction direction;
        int round = 1;
        int rawCheese;
        int delivered;
        int turns;
        int moves;
        int kingSightings;
        boolean movementReady = true;
        boolean turningReady = true;
        boolean actionReady = true;

        World(MapLocation location, Direction direction) {
            this.location = location;
            this.direction = direction;
            rc = (RobotController) Proxy.newProxyInstance(RobotController.class.getClassLoader(),
                    new Class<?>[] {RobotController.class}, this);
        }

        void takeTurn(BabyRat baby) throws Exception {
            baby.takeTurn(rc);
            nextRound();
        }

        void nextRound() {
            round++;
            movementReady = turningReady = actionReady = true;
        }

        boolean onMap(MapLocation target) {
            return target.x >= 0 && target.y >= 0 && target.x < size && target.y < size;
        }

        boolean visible(MapLocation target) {
            return onMap(target) && location.isWithinDistanceSquared(target,
                    UnitType.BABY_RAT.visionConeRadiusSquared, direction, UnitType.BABY_RAT.visionConeAngle, false);
        }

        RobotInfo robotAt(MapLocation target) {
            for (RobotInfo robot : robots) {
                for (MapLocation part : robot.getType().getAllTypeLocations(robot.getLocation())) {
                    if (part.equals(target)) return robot;
                }
            }
            return null;
        }

        MapInfo info(MapLocation target) {
            boolean wall = walls.contains(target);
            return new MapInfo(target, !wall, null, wall, false,
                    cheese.getOrDefault(target, 0), TrapType.NONE, false);
        }

        boolean canMove(Direction step) {
            MapLocation target = location.add(step);
            return movementReady && step != Direction.CENTER && onMap(target)
                    && !walls.contains(target) && robotAt(target) == null;
        }

        boolean canPickUp(MapLocation target) {
            return visible(target) && location.distanceSquaredTo(target) <= GameConstants.CHEESE_PICK_UP_RADIUS_SQUARED
                    && cheese.getOrDefault(target, 0) > 0;
        }

        boolean canTransfer(MapLocation target, int amount) {
            RobotInfo recipient = robotAt(target);
            return actionReady && visible(target) && amount > 0 && rawCheese >= amount
                    && location.distanceSquaredTo(target) <= GameConstants.CHEESE_TRANSFER_RADIUS_SQUARED
                    && recipient != null && recipient.getTeam() == Team.A;
        }

        @Override
        public Object invoke(Object proxy, Method method, Object[] args) {
            switch (method.getName()) {
                case "getID": return id;
                case "getRoundNum": return round;
                case "getMapWidth": case "getMapHeight": return size;
                case "getTeam": return Team.A;
                case "getType": return UnitType.BABY_RAT;
                case "getLocation": return location;
                case "getDirection": return direction;
                case "getRawCheese": return rawCheese;
                case "readSharedArray": return shared[(Integer) args[0]];
                case "isBeingCarried": case "isBeingThrown": return false;
                case "isMovementReady": return movementReady;
                case "canSenseLocation": return visible((MapLocation) args[0]);
                case "senseRobotAtLocation": {
                    MapLocation target = (MapLocation) args[0];
                    assertTrue("Code attempted to sense outside its FOV", visible(target));
                    return robotAt(target);
                }
                case "senseNearbyRobots": {
                    List<RobotInfo> visibleRobots = new ArrayList<>();
                    Team team = args == null || args.length < 2 ? null : (Team) args[1];
                    for (RobotInfo robot : robots) {
                        if (team != null && robot.getTeam() != team) continue;
                        for (MapLocation part : robot.getType().getAllTypeLocations(robot.getLocation())) {
                            if (visible(part)) {
                                visibleRobots.add(robot);
                                if (robot.getType() == UnitType.RAT_KING && robot.getTeam() == Team.A) kingSightings++;
                                break;
                            }
                        }
                    }
                    return visibleRobots.toArray(new RobotInfo[0]);
                }
                case "senseMapInfo": {
                    MapLocation target = (MapLocation) args[0];
                    assertTrue("Code attempted to sense outside its FOV", visible(target));
                    return info(target);
                }
                case "senseNearbyMapInfos": {
                    List<MapInfo> sensed = new ArrayList<>();
                    for (int x = 0; x < size; x++) {
                        for (int y = 0; y < size; y++) {
                            MapLocation target = at(x, y);
                            if (visible(target)) sensed.add(info(target));
                        }
                    }
                    return sensed.toArray(new MapInfo[0]);
                }
                case "canTurn": return turningReady && (args == null || args.length == 0 || args[0] != direction);
                case "turn":
                    assertTrue("Turn attempted during cooldown", turningReady);
                    assertNotEquals(direction, args[0]);
                    direction = (Direction) args[0];
                    turningReady = false;
                    turns++;
                    return null;
                case "canMove": return canMove((Direction) args[0]);
                case "move":
                    assertTrue("Move attempted into an occupied/walled tile or during cooldown", canMove((Direction) args[0]));
                    location = location.add((Direction) args[0]);
                    movementReady = false;
                    moves++;
                    return null;
                case "canPickUpCheese": return canPickUp((MapLocation) args[0]);
                case "pickUpCheese": {
                    MapLocation target = (MapLocation) args[0];
                    assertTrue("Illegal cheese pickup", canPickUp(target));
                    rawCheese += cheese.remove(target);
                    pickups.add(target);
                    return null;
                }
                case "canTransferCheese": return canTransfer((MapLocation) args[0], (Integer) args[1]);
                case "transferCheese": {
                    MapLocation target = (MapLocation) args[0];
                    int amount = (Integer) args[1];
                    assertTrue("Illegal cheese transfer", canTransfer(target, amount));
                    assertEquals("Collectors must deliver to kings", UnitType.RAT_KING, robotAt(target).getType());
                    rawCheese -= amount;
                    delivered += amount;
                    actionReady = false;
                    transfers.add(target);
                    recipientIds.add(robotAt(target).getID());
                    return null;
                }
                case "setIndicatorString": return null;
                default: throw new AssertionError("Unsupported controller operation: " + method.getName());
            }
        }
    }
}
