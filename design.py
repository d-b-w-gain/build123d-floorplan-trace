from __future__ import annotations

import base64
import math
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

try:
    import build123d as bd
except ModuleNotFoundError:
    bd = None


# Build123D concept floor plan from the provided real-estate plan trace.
# Source coordinates are in metres; Build123D geometry is generated in mm.

MM_PER_METRE = 1000.0
SHOW_FURNITURE = True
SHOW_PRESENTATION_DETAILS = False


def m(value: float) -> float:
    return value * MM_PER_METRE


external_wall_thickness = m(0.15)
internal_wall_thickness = m(0.10)
wall_height = m(2.4)
floor_thickness = m(0.08)
room_plate_thickness = m(0.025)
garage_wall_height = m(2.4)
door_height = m(2.05)
door_thickness = m(0.04)
window_sill_height = m(0.9)
window_height = m(0.9)

Point = tuple[float, float]
Colour = tuple[float, float, float, float]


def colour(r: float, g: float, b: float, a: float = 1.0) -> Colour:
    return (r, g, b, a)


EXTERIOR_CLADDING = colour(0.61, 0.72, 0.76, 1)
EXTERIOR_TRIM = colour(0.88, 0.91, 0.91, 1)
ROOF_METAL = colour(0.56, 0.60, 0.60, 1)
GARAGE_DOOR_COLOUR = colour(0.66, 0.67, 0.66, 1)
FRONT_SECURITY_DOOR = colour(0.18, 0.20, 0.20, 1)
INTERIOR_DOOR = colour(0.52, 0.31, 0.17, 1)
FOUNDATION_STONE = colour(0.58, 0.45, 0.32, 1)
CONCRETE = colour(0.50, 0.49, 0.45, 1)
TIMBER_FLOOR = colour(0.55, 0.33, 0.18, 1)
NEW_CARPET = colour(0.72, 0.69, 0.64, 1)
RENOVATED_WET_AREA = colour(0.82, 0.88, 0.90, 1)
WARM_INTERIOR_WALL = colour(0.92, 0.90, 0.85, 1)
KITCHEN_CABINET = colour(0.74, 0.52, 0.31, 1)
BENCHTOP = colour(0.95, 0.95, 0.91, 1)
WHITE_FIXTURE = colour(1.00, 1.00, 0.98, 1)

ROOM_COLOURS = {
    "living": TIMBER_FLOOR,
    "bedroom": NEW_CARPET,
    "wet": RENOVATED_WET_AREA,
    "alfresco": colour(0.61, 0.67, 0.56, 1),
    "garage": CONCRETE,
    "service": colour(0.78, 0.80, 0.76, 1),
}

WINDOW_GLASS_COLOUR = colour(0.25, 0.72, 1.00, 0.35)


@dataclass(frozen=True)
class FootprintSpec:
    label: str
    points: tuple[Point, ...]
    height: float
    z_bottom: float
    color: Colour


@dataclass(frozen=True)
class WallRunSpec:
    key: str
    label: str
    start: Point
    end: Point
    thickness: float
    height: float
    color: Colour
    is_external: bool = False


@dataclass(frozen=True)
class OpeningSpec:
    label: str
    wall_key: str
    start: float
    end: float
    kind: str
    panel_color: Colour


@dataclass(frozen=True)
class FixtureSpec:
    label: str
    points: tuple[Point, ...]
    height: float
    z_bottom: float
    color: Colour


@dataclass(frozen=True)
class BoxSpec:
    label: str
    width: float
    depth: float
    height: float
    center: tuple[float, float, float]
    color: Colour


def rect_points(x1: float, y1: float, x2: float, y2: float) -> tuple[Point, ...]:
    return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))


FLOORPLAN_IMAGE = "floorplan.png"
FLOORPLAN_PIXEL_WIDTH = 633
FLOORPLAN_PIXEL_HEIGHT = 625
PIXELS_PER_METRE = 45.0
PIXEL_ORIGIN_X = 18.0
PIXEL_ORIGIN_Y = 620.0
ALFRESCO_BOUNDARY_HEIGHT = m(0.12)


def pt(x: float, y: float) -> Point:
    return ((x - PIXEL_ORIGIN_X) / PIXELS_PER_METRE, (PIXEL_ORIGIN_Y - y) / PIXELS_PER_METRE)


def px(value: float) -> float:
    return value / PIXELS_PER_METRE


def px_points(*points: tuple[float, float]) -> tuple[Point, ...]:
    return tuple(pt(x, y) for x, y in points)


def px_rect(x1: float, y1: float, x2: float, y2: float) -> tuple[Point, ...]:
    return px_points((x1, y2), (x2, y2), (x2, y1), (x1, y1))


def to_pixel(point: Point) -> tuple[float, float]:
    return (
        point[0] * PIXELS_PER_METRE + PIXEL_ORIGIN_X,
        PIXEL_ORIGIN_Y - point[1] * PIXELS_PER_METRE,
    )


HOUSE_OUTLINE: tuple[Point, ...] = px_points(
    (19, 139),
    (373, 139),
    (373, 237),
    (412, 277),
    (412, 354),
    (347, 354),
    (347, 518),
    (282, 518),
    (282, 560),
    (300, 560),
    (300, 620),
    (62, 620),
    (62, 518),
    (19, 518),
)

ALFRESCO_OUTLINE: tuple[Point, ...] = px_points(
    (149, 31),
    (373, 31),
    (373, 139),
    (19, 139),
    (19, 91),
    (149, 91),
)

GARAGE = {
    "x1_px": 479,
    "y1_px": 4,
    "x2_px": 625,
    "y2_px": 620,
    "label": "Garage 15.6m x 3.3m",
}
GARAGE_X1 = pt(GARAGE["x1_px"], GARAGE["y2_px"])[0]
GARAGE_Y1 = pt(GARAGE["x1_px"], GARAGE["y2_px"])[1]
GARAGE_X2 = pt(GARAGE["x2_px"], GARAGE["y1_px"])[0]
GARAGE_Y2 = pt(GARAGE["x2_px"], GARAGE["y1_px"])[1]


SLABS: tuple[FootprintSpec, ...] = (
    FootprintSpec("House floor plate - traced external outline", HOUSE_OUTLINE, floor_thickness, 0.0, WARM_INTERIOR_WALL),
    FootprintSpec("Alfresco covered slab - traced L shape", ALFRESCO_OUTLINE, floor_thickness, 0.0, ROOM_COLOURS["alfresco"]),
    FootprintSpec("Garage slab 15.6m x 3.3m", rect_points(GARAGE_X1, GARAGE_Y1, GARAGE_X2, GARAGE_Y2), floor_thickness, 0.0, ROOM_COLOURS["garage"]),
)

ROOMS: tuple[FootprintSpec, ...] = (
    FootprintSpec("Living 5.1m x 2.3m", px_points((62, 518), (282, 518), (282, 560), (300, 560), (300, 620), (62, 620)), room_plate_thickness, floor_thickness, ROOM_COLOURS["living"]),
    FootprintSpec("Bedroom 3.7m x 2.7m", px_rect(19, 363, 149, 518), room_plate_thickness, floor_thickness, ROOM_COLOURS["bedroom"]),
    FootprintSpec("Bedroom 1 robe", px_rect(149, 363, 178, 518), room_plate_thickness, floor_thickness, ROOM_COLOURS["service"]),
    FootprintSpec("Bedroom 2.7m x 2.2m", px_rect(19, 253, 149, 363), room_plate_thickness, floor_thickness, ROOM_COLOURS["bedroom"]),
    FootprintSpec("Bedroom 2 robe band", px_rect(19, 239, 149, 253), room_plate_thickness, floor_thickness, ROOM_COLOURS["service"]),
    FootprintSpec("WC", px_rect(19, 139, 74, 239), room_plate_thickness, floor_thickness, ROOM_COLOURS["wet"]),
    FootprintSpec("Laundry", px_rect(74, 139, 149, 239), room_plate_thickness, floor_thickness, ROOM_COLOURS["wet"]),
    FootprintSpec("Bathroom traced from plan", px_rect(149, 239, 241, 316), room_plate_thickness, floor_thickness, ROOM_COLOURS["wet"]),
    FootprintSpec("Kitchen", px_points((149, 139), (373, 139), (373, 237), (296, 237), (296, 213), (241, 213), (241, 237), (149, 237)), room_plate_thickness, floor_thickness, ROOM_COLOURS["living"]),
    FootprintSpec("Dining 3.7m x 2.7m", px_points((241, 237), (373, 237), (412, 277), (412, 354), (347, 354), (347, 363), (178, 363), (178, 316), (241, 316)), room_plate_thickness, floor_thickness, ROOM_COLOURS["living"]),
    FootprintSpec("Lounge 3.9m x 3.6m", px_points((178, 363), (347, 363), (347, 518), (178, 518)), room_plate_thickness, floor_thickness, ROOM_COLOURS["living"]),
    FootprintSpec("Alfresco 4.8m x 2.5m plus left covered return", ALFRESCO_OUTLINE, room_plate_thickness, floor_thickness, ROOM_COLOURS["alfresco"]),
    FootprintSpec("Garage 15.6m x 3.3m", rect_points(GARAGE_X1, GARAGE_Y1, GARAGE_X2, GARAGE_Y2), room_plate_thickness, floor_thickness, ROOM_COLOURS["garage"]),
)

WALL_RUNS: tuple[WallRunSpec, ...] = (
    # Alfresco roof/slab boundary from the image. Low in 3D, full weight in the debug trace.
    WallRunSpec("alfresco_top", "Alfresco top boundary", pt(149, 31), pt(373, 31), external_wall_thickness, ALFRESCO_BOUNDARY_HEIGHT, EXTERIOR_CLADDING, True),
    WallRunSpec("alfresco_right", "Alfresco right boundary", pt(373, 31), pt(373, 139), external_wall_thickness, ALFRESCO_BOUNDARY_HEIGHT, EXTERIOR_CLADDING, True),
    WallRunSpec("alfresco_rear_house", "Alfresco rear house boundary", pt(19, 139), pt(373, 139), external_wall_thickness, ALFRESCO_BOUNDARY_HEIGHT, EXTERIOR_CLADDING, True),
    WallRunSpec("alfresco_left_lower", "Alfresco left lower boundary", pt(19, 91), pt(19, 139), external_wall_thickness, ALFRESCO_BOUNDARY_HEIGHT, EXTERIOR_CLADDING, True),
    WallRunSpec("alfresco_left_top", "Alfresco left top boundary", pt(19, 91), pt(149, 91), external_wall_thickness, ALFRESCO_BOUNDARY_HEIGHT, EXTERIOR_CLADDING, True),
    WallRunSpec("alfresco_step", "Alfresco step boundary", pt(149, 31), pt(149, 91), external_wall_thickness, ALFRESCO_BOUNDARY_HEIGHT, EXTERIOR_CLADDING, True),
    # External house outline.
    WallRunSpec("rear_wall", "Rear wall to alfresco", pt(19, 139), pt(373, 139), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("kitchen_east", "Kitchen east external wall", pt(373, 139), pt(373, 237), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("dining_angle", "Dining angled north-east wall", pt(373, 237), pt(412, 277), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("dining_east", "Dining east external wall", pt(412, 277), pt(412, 354), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("dining_south_return", "Dining south return wall", pt(412, 354), pt(347, 354), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("lounge_east", "Lounge east external wall", pt(347, 354), pt(347, 518), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("lounge_front_exterior", "Lounge front exposed wall", pt(347, 518), pt(282, 518), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("living_entry_left", "Living right return upper", pt(282, 518), pt(282, 560), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("living_entry_top", "Living right return notch", pt(282, 560), pt(300, 560), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("living_east", "Living east external wall", pt(300, 560), pt(300, 620), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("front_wall", "Living front wall", pt(62, 620), pt(300, 620), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("living_west", "Living west external wall", pt(62, 518), pt(62, 620), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("bed_front_return", "Bedroom/front step external wall", pt(19, 518), pt(62, 518), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("west_wall", "West external wall", pt(19, 139), pt(19, 518), external_wall_thickness, wall_height, EXTERIOR_CLADDING, True),
    # Internal house walls.
    WallRunSpec("living_lounge_wall", "Living to lounge wall", pt(62, 518), pt(300, 518), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bed1_top_wall", "Bedroom 1 top wall", pt(19, 363), pt(178, 363), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bed1_robe_east", "Bedroom 1 / lounge wall behind robe", pt(178, 363), pt(178, 518), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bed2_right_wall", "Bedroom 2 right wall", pt(149, 253), pt(149, 363), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("wc_laundry_wall", "WC to laundry wall", pt(74, 139), pt(74, 239), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("wet_area_south", "WC/Laundry south wall", pt(19, 239), pt(149, 239), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("laundry_east_wall", "Laundry east wall", pt(149, 139), pt(149, 239), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("kitchen_dining_west_wall", "Kitchen to dining west wall segment", pt(149, 237), pt(241, 237), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("kitchen_dining_east_wall", "Kitchen to dining east wall segment", pt(296, 237), pt(373, 237), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bath_south", "Bathroom south wall", pt(149, 316), pt(241, 316), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bath_west", "Bathroom west wall", pt(149, 239), pt(149, 316), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bath_east", "Bathroom east wall", pt(241, 239), pt(241, 316), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    WallRunSpec("bath_north", "Bathroom north wall", pt(149, 239), pt(241, 239), internal_wall_thickness, wall_height, WARM_INTERIOR_WALL),
    # Detached garage.
    WallRunSpec("garage_front", "Garage roller-door wall", pt(479, 620), pt(625, 620), external_wall_thickness, garage_wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("garage_west", "Garage west wall", pt(479, 4), pt(479, 620), external_wall_thickness, garage_wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("garage_north", "Garage rear wall", pt(479, 4), pt(625, 4), external_wall_thickness, garage_wall_height, EXTERIOR_CLADDING, True),
    WallRunSpec("garage_east", "Garage east wall", pt(625, 4), pt(625, 620), external_wall_thickness, garage_wall_height, EXTERIOR_CLADDING, True),
)

DOORS: tuple[OpeningSpec, ...] = (
    OpeningSpec("Kitchen to alfresco door", "rear_wall", px(145), px(187), "door", INTERIOR_DOOR),
    OpeningSpec("Front entry door to outside", "living_entry_left", px(4), px(38), "door", FRONT_SECURITY_DOOR),
    OpeningSpec("Living to lounge west opening", "living_lounge_wall", px(119), px(160), "door", INTERIOR_DOOR),
    OpeningSpec("Living to lounge east opening", "living_lounge_wall", px(184), px(224), "door", INTERIOR_DOOR),
    OpeningSpec("Bedroom 1 door", "bed1_robe_east", px(4), px(42), "door", INTERIOR_DOOR),
    OpeningSpec("Bedroom 2 pocket door", "bed2_right_wall", px(68), px(106), "door", INTERIOR_DOOR),
    OpeningSpec("WC pocket door to laundry", "wc_laundry_wall", px(30), px(72), "door", INTERIOR_DOOR),
    OpeningSpec("Laundry pocket door to kitchen", "laundry_east_wall", px(52), px(92), "door", INTERIOR_DOOR),
    OpeningSpec("Garage roller door", "garage_front", px(13), px(138), "door", GARAGE_DOOR_COLOUR),
    OpeningSpec("Garage pedestrian door", "garage_west", px(191), px(234), "door", GARAGE_DOOR_COLOUR),
)

WINDOWS: tuple[OpeningSpec, ...] = (
    OpeningSpec("Laundry rear window", "rear_wall", px(68), px(110), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Kitchen rear sink window", "rear_wall", px(192), px(260), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Kitchen rear right window", "rear_wall", px(300), px(328), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Kitchen east window", "kitchen_east", px(26), px(70), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Dining east window", "dining_east", px(31), px(72), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Bedroom 2 west window", "west_wall", px(146), px(203), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Bedroom 1 west window", "west_wall", px(316), px(374), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Living front west window", "front_wall", px(3), px(73), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Living front middle window", "front_wall", px(80), px(146), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Living front east window", "front_wall", px(151), px(235), "window", WINDOW_GLASS_COLOUR),
    OpeningSpec("Garage west window", "garage_west", px(57), px(91), "window", WINDOW_GLASS_COLOUR),
)

OPENINGS: tuple[OpeningSpec, ...] = DOORS + WINDOWS

FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec("Bedroom 1 robe", px_rect(149, 398, 178, 508), m(2.1), 0.0, ROOM_COLOURS["service"]),
    FixtureSpec("Bedroom 2 robe band", px_rect(25, 240, 145, 252), m(2.1), 0.0, ROOM_COLOURS["service"]),
    FixtureSpec("Kitchen rear cabinet run", px_rect(210, 145, 365, 164), m(0.90), 0.0, KITCHEN_CABINET),
    FixtureSpec("Kitchen rear light benchtop", px_rect(210, 145, 365, 164), m(0.06), m(0.90), BENCHTOP),
    FixtureSpec("Kitchen cooktop bench", px_rect(149, 202, 242, 224), m(0.90), 0.0, KITCHEN_CABINET),
    FixtureSpec("Kitchen right appliance bench", px_rect(297, 201, 366, 224), m(0.90), 0.0, BENCHTOP),
    FixtureSpec("Bathroom bath", px_rect(150, 241, 195, 304), m(0.55), 0.0, WHITE_FIXTURE),
    FixtureSpec("Bathroom vanity/toilet line", px_rect(195, 241, 240, 315), m(0.90), 0.0, WHITE_FIXTURE),
    FixtureSpec("Laundry washer and tub run", px_rect(83, 204, 142, 229), m(0.90), 0.0, WHITE_FIXTURE),
    FixtureSpec("WC pan marker", px_rect(33, 205, 52, 228), m(0.45), 0.0, WHITE_FIXTURE),
)

PRESENTATION_SURFACES: tuple[FootprintSpec, ...] = (
    FootprintSpec("Front verandah corrugated roof", px_rect(62, 518, 300, 620), m(0.08), wall_height + m(0.08), ROOF_METAL),
    FootprintSpec("Alfresco veranda roof", ALFRESCO_OUTLINE, m(0.08), wall_height + m(0.05), ROOF_METAL),
    FootprintSpec("Garage corrugated roof", px_rect(472, 0, 632, 624), m(0.08), garage_wall_height + m(0.12), ROOF_METAL),
)

PRESENTATION_BOXES: tuple[BoxSpec, ...] = (
    BoxSpec("Front verandah west post", m(0.12), m(0.12), wall_height, (m(0.92), m(0.44), wall_height / 2.0), EXTERIOR_TRIM),
    BoxSpec("Front verandah east post", m(0.12), m(0.12), wall_height, (m(5.32), m(0.44), wall_height / 2.0), EXTERIOR_TRIM),
    BoxSpec("Alfresco post north-west", m(0.12), m(0.12), wall_height, (m(2.05), m(12.85), wall_height / 2.0), EXTERIOR_TRIM),
    BoxSpec("Alfresco post north-east", m(0.12), m(0.12), wall_height, (m(6.75), m(12.85), wall_height / 2.0), EXTERIOR_TRIM),
)


def require_build123d():
    if bd is None:
        raise RuntimeError("build123d is required to create CAD geometry")
    return bd


def bd_colour(value: Colour):
    return require_build123d().Color(*value)


def box_part(label: str, width: float, depth: float, height: float, center: tuple[float, float, float], color: Colour | None = None):
    cad = require_build123d()
    with cad.BuildPart() as box:
        cad.Box(width, depth, height)
    part = box.part.moved(cad.Location(center))
    part.label = label
    if color is not None:
        part.color = bd_colour(color)
    return part


def footprint_part(spec: FootprintSpec | FixtureSpec):
    cad = require_build123d()
    points_mm = [(m(x), m(y)) for x, y in spec.points]
    with cad.BuildPart() as footprint:
        with cad.BuildSketch(cad.Plane.XY):
            cad.Polygon(*points_mm, align=None)
        cad.extrude(amount=spec.height)
    part = footprint.part.moved(cad.Location((0, 0, spec.z_bottom)))
    part.label = spec.label
    part.color = bd_colour(spec.color)
    return part


def wall_between(
    label: str,
    p1: Point,
    p2: Point,
    thickness: float,
    height: float,
    color: Colour | None = None,
    z_bottom: float = 0.0,
):
    x1, y1 = p1
    x2, y2 = p2
    dx = m(x2 - x1)
    dy = m(y2 - y1)
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))
    center = (m((x1 + x2) / 2.0), m((y1 + y2) / 2.0), z_bottom + height / 2.0)
    cad = require_build123d()
    with cad.BuildPart() as wall:
        cad.Box(length, thickness, height)
    part = wall.part.moved(cad.Location(center, (0, 0, angle)))
    part.label = label
    if color is not None:
        part.color = bd_colour(color)
    return part


def opening_panel(label: str, p1: Point, p2: Point, height: float, z_bottom: float, thickness: float, color: Colour):
    return wall_between(label, p1, p2, thickness, height, color, z_bottom=z_bottom)


def door_panel(label: str, p1: Point, p2: Point, color: Colour = INTERIOR_DOOR):
    return opening_panel(label, p1, p2, door_height, 0.0, door_thickness, color)


def window_panel(label: str, p1: Point, p2: Point):
    return opening_panel(label, p1, p2, window_height, window_sill_height, m(0.035), WINDOW_GLASS_COLOUR)


def wall_length(run: WallRunSpec) -> float:
    return math.hypot(run.end[0] - run.start[0], run.end[1] - run.start[1])


def point_at(run: WallRunSpec, distance: float) -> Point:
    length = wall_length(run)
    if length <= 0:
        raise ValueError(f"Wall run has zero length: {run.key}")
    t = distance / length
    return (
        run.start[0] + (run.end[0] - run.start[0]) * t,
        run.start[1] + (run.end[1] - run.start[1]) * t,
    )


def openings_by_wall() -> dict[str, list[OpeningSpec]]:
    grouped: dict[str, list[OpeningSpec]] = {run.key: [] for run in WALL_RUNS}
    for opening in OPENINGS:
        grouped[opening.wall_key].append(opening)
    for items in grouped.values():
        items.sort(key=lambda item: item.start)
    return grouped


def validate_plan_data() -> None:
    walls = {run.key: run for run in WALL_RUNS}
    for opening in OPENINGS:
        if opening.wall_key not in walls:
            raise ValueError(f"{opening.label} references missing wall {opening.wall_key}")
        if opening.kind not in {"door", "window"}:
            raise ValueError(f"{opening.label} has unsupported opening kind {opening.kind}")
        length = wall_length(walls[opening.wall_key])
        if opening.start < 0 or opening.end > length or opening.start >= opening.end:
            raise ValueError(
                f"{opening.label} span {opening.start:.2f}-{opening.end:.2f}m "
                f"does not fit wall {opening.wall_key} length {length:.2f}m"
            )


def wall_parts(run: WallRunSpec, wall_openings: list[OpeningSpec]):
    parts = []
    cursor = 0.0
    run_color = run.color
    header_color = EXTERIOR_TRIM if run.is_external else WARM_INTERIOR_WALL

    for opening in wall_openings:
        if opening.start - cursor > 0.01:
            parts.append(
                wall_between(
                    f"{run.label} segment {cursor:.2f}-{opening.start:.2f}",
                    point_at(run, cursor),
                    point_at(run, opening.start),
                    run.thickness,
                    run.height,
                    run_color,
                )
            )

        op_start = point_at(run, opening.start)
        op_end = point_at(run, opening.end)
        if opening.kind == "window":
            parts.append(wall_between(f"{opening.label} sill wall", op_start, op_end, run.thickness, window_sill_height, run_color))
            header_height = run.height - window_sill_height - window_height
            if header_height > 0:
                parts.append(
                    wall_between(
                        f"{opening.label} header wall",
                        op_start,
                        op_end,
                        run.thickness,
                        header_height,
                        run_color,
                        z_bottom=window_sill_height + window_height,
                    )
                )
        elif run.height > door_height:
            parts.append(
                wall_between(
                    f"{opening.label} header",
                    op_start,
                    op_end,
                    run.thickness,
                    run.height - door_height,
                    header_color,
                    z_bottom=door_height,
                )
            )

        cursor = opening.end

    length = wall_length(run)
    if length - cursor > 0.01:
        parts.append(
            wall_between(
                f"{run.label} segment {cursor:.2f}-{length:.2f}",
                point_at(run, cursor),
                point_at(run, length),
                run.thickness,
                run.height,
                run_color,
            )
        )
    return parts


def opening_parts(opening: OpeningSpec, wall_lookup: dict[str, WallRunSpec]):
    run = wall_lookup[opening.wall_key]
    p1 = point_at(run, opening.start)
    p2 = point_at(run, opening.end)
    if opening.kind == "door":
        return [door_panel(opening.label, p1, p2, opening.panel_color)]
    return [window_panel(opening.label, p1, p2)]


def make_floor_plan():
    validate_plan_data()
    parts = []

    parts.extend(footprint_part(slab) for slab in SLABS)
    parts.extend(footprint_part(room) for room in ROOMS)

    grouped_openings = openings_by_wall()
    for run in WALL_RUNS:
        parts.extend(wall_parts(run, grouped_openings[run.key]))

    wall_lookup = {run.key: run for run in WALL_RUNS}
    for opening in OPENINGS:
        parts.extend(opening_parts(opening, wall_lookup))

    if SHOW_FURNITURE:
        parts.extend(footprint_part(fixture) for fixture in FIXTURES)

    if SHOW_PRESENTATION_DETAILS:
        parts.extend(footprint_part(surface) for surface in PRESENTATION_SURFACES)
        for box in PRESENTATION_BOXES:
            parts.append(box_part(box.label, box.width, box.depth, box.height, box.center, box.color))
        parts.append(wall_between("Front sandstone foundation skirt", (0.9, 0.0), (5.35, 0.0), external_wall_thickness, m(0.32), FOUNDATION_STONE))
        parts.append(wall_between("West low foundation/skirt", (0.0, 2.4), (0.0, 10.2), external_wall_thickness, m(0.22), FOUNDATION_STONE))

    return require_build123d().Compound(children=parts, label="Traced floor plan - Build123D massing")


def svg_colour(color: Colour) -> str:
    r, g, b, _a = color
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


def svg_opacity(color: Colour) -> str:
    return f"{color[3]:.2f}"


def polygon_centroid(points: tuple[Point, ...]) -> Point:
    x = sum(point[0] for point in points) / len(points)
    y = sum(point[1] for point in points) / len(points)
    return x, y


def write_debug_svg(path: str | Path = "floorplan_trace_debug.svg") -> Path:
    validate_plan_data()
    output_path = Path(path)

    def poly_points(points: tuple[Point, ...]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (to_pixel(point) for point in points))

    image_path = Path(__file__).with_name(FLOORPLAN_IMAGE)
    image_href = ""
    if image_path.exists():
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        image_href = f"data:image/png;base64,{encoded}"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{FLOORPLAN_PIXEL_WIDTH}" height="{FLOORPLAN_PIXEL_HEIGHT}" viewBox="0 0 {FLOORPLAN_PIXEL_WIDTH} {FLOORPLAN_PIXEL_HEIGHT}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    if image_href:
        lines.append(
            f'<image href="{image_href}" x="0" y="0" width="{FLOORPLAN_PIXEL_WIDTH}" height="{FLOORPLAN_PIXEL_HEIGHT}" opacity="0.55"/>'
        )

    for room in ROOMS:
        cx, cy = polygon_centroid(room.points)
        label_x, label_y = to_pixel((cx, cy))
        lines.append(
            f'<polygon points="{poly_points(room.points)}" fill="{svg_colour(room.color)}" '
            f'fill-opacity="0.22" stroke="#ffffff" stroke-width="0.8"/>'
        )
        lines.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" font-family="Arial" font-size="8" '
            f'text-anchor="middle" fill="#222222">{escape(room.label.split(" - ")[0])}</text>'
        )

    grouped = openings_by_wall()
    for run in WALL_RUNS:
        stroke = "#ff00a8" if run.is_external else "#ff7a00"
        stroke_width = 4.5 if run.is_external else 3.0
        p1 = to_pixel(run.start)
        p2 = to_pixel(run.end)
        lines.append(
            f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" '
            f'stroke="{stroke}" stroke-opacity="0.75" stroke-width="{stroke_width:.1f}" stroke-linecap="square"/>'
        )
        for opening in grouped[run.key]:
            p1 = point_at(run, opening.start)
            p2 = point_at(run, opening.end)
            px1 = to_pixel(p1)
            px2 = to_pixel(p2)
            color = "#1d5edb" if opening.kind == "door" else "#00e5ff"
            opening_width = stroke_width + 4 if opening.kind == "door" else stroke_width + 1
            lines.append(
                f'<line x1="{px1[0]:.1f}" y1="{px1[1]:.1f}" x2="{px2[0]:.1f}" y2="{px2[1]:.1f}" '
                f'stroke="{color}" stroke-opacity="0.95" stroke-width="{opening_width:.1f}" stroke-linecap="square"/>'
            )

    if SHOW_FURNITURE:
        for fixture in FIXTURES:
            lines.append(
                f'<polygon points="{poly_points(fixture.points)}" fill="{svg_colour(fixture.color)}" '
                f'fill-opacity="{svg_opacity(fixture.color)}" stroke="#333333" stroke-width="0.6"/>'
            )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> int:
    if "--svg" in sys.argv:
        try:
            target = sys.argv[sys.argv.index("--svg") + 1]
        except IndexError:
            target = "floorplan_trace_debug.svg"
        path = write_debug_svg(target)
        print(f"Wrote {path}")
        return 0

    if bd is None:
        print("build123d is not installed in this Python environment; CAD geometry was not generated.")
        return 1

    return 0


if bd is not None and not (__name__ == "__main__" and "--svg" in sys.argv):
    building = make_floor_plan()
else:
    building = None

if building is not None and "show_object" in locals():
    show_object(building)

if __name__ == "__main__":
    raise SystemExit(main())
