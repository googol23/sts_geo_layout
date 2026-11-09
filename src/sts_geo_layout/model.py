"""XY projection of the v26a half-ladder placement rules. All distances are in mm."""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

import numpy as np
from sts_utils.sts_naming import MODULE_NAME_PATTERN, is_valid_label

MAX_SENSORS_PER_HALF_LADDER = 5
SENSOR_OVERLAP_MM = 4.6
SENSOR_OVERLAP_CM = 0.1 * SENSOR_OVERLAP_MM
# These are assembly sensor IDs, not C++ enum ordinals. Preserve the legacy ID-0
# alias; empty geometry slots are represented by None, never by SensorType(0).
STS_SENSOR_SIZE = {
    0: (62, 22),
    1: (62, 22),
    2: (62, 42),
    3: (62, 62),
    4: (62, 124),
}


@dataclass(frozen=True)
class SensorType:
    id: int

    def __post_init__(self):
        if not isinstance(self.id, int) or self.id not in STS_SENSOR_SIZE:
            raise ValueError(f"Unsupported sensor type: {self.id!r}")

    def size_xy(self) -> tuple[float, float]:
        return STS_SENSOR_SIZE[self.id]

    def __str__(self) -> str:
        width, height = self.size_xy()
        return f"k{width}_{height}"


@dataclass(frozen=True)
class LadderLayout:
    """Sensors ordered bottom-to-top; length is the support length, not the footprint.

    Modules are optional assembly provenance, in exactly the same order as sensors.
    Only layouts with mirrored sensor dimensions are supported. The model does not
    reproduce Z staggering, support solids, cables, or global geometry transforms.
    """

    sensor_types: Sequence[SensorType]
    cutout_size: float = 0
    length: float = 0
    module_names: Sequence[str] = ()
    half_ladder_offset_y: float | None = None

    def __post_init__(self):
        sensors = tuple(self.sensor_types)
        modules = tuple(self.module_names)
        object.__setattr__(self, "sensor_types", sensors)
        object.__setattr__(self, "module_names", modules)
        if not sensors or len(sensors) % 2:
            raise ValueError("A ladder requires a nonempty, even number of sensors")
        if len(sensors) > 2 * MAX_SENSORS_PER_HALF_LADDER:
            raise ValueError("A ladder supports at most five sensor slots per half")
        if any(not isinstance(sensor, SensorType) for sensor in sensors):
            raise TypeError("sensor_types must contain SensorType instances")
        for name in ("cutout_size", "length"):
            value = float(getattr(self, name))
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, value)
        offset = self.half_ladder_offset_y
        if offset is None:
            offset = (
                self.cutout_size / 2 if self.cutout_size > 0 else -SENSOR_OVERLAP_MM / 2
            )
        offset = float(offset)
        if not isfinite(offset):
            raise ValueError("half_ladder_offset_y must be finite")
        object.__setattr__(self, "half_ladder_offset_y", offset)
        sizes = [sensor.size_xy() for sensor in sensors]
        if sizes != sizes[::-1]:
            raise ValueError("Sensor dimensions must be mirror-symmetric bottom-to-top")
        if modules and (
            len(modules) != len(sensors) or len(set(modules)) != len(modules)
        ):
            raise ValueError("module_names must uniquely identify every sensor")
        if modules:
            positions = []
            for name in modules:
                if not isinstance(name, str) or not is_valid_label(
                    name, MODULE_NAME_PATTERN
                ):
                    raise ValueError(f"Invalid module name: {name}")
                slot = int(name[6])
                if slot >= MAX_SENSORS_PER_HALF_LADDER:
                    raise ValueError(
                        f"Module position {slot} is outside geometry slots 0..4: {name}"
                    )
                positions.append((name[5], slot))
            bottom = [slot for half, slot in positions if half == "B"]
            top = [slot for half, slot in positions if half == "T"]
            expected = [("B", slot) for slot in reversed(top)] + [
                ("T", slot) for slot in top
            ]
            if (
                len(top) != len(sensors) // 2
                or len(set(top)) != len(top)
                or top != sorted(top)
                or bottom != list(reversed(top))
                or positions != expected
            ):
                raise ValueError(
                    "module_names must pair B/T slots in bottom-to-top order"
                )

    @property
    def half_ladder_layout(self) -> tuple[SensorType | None, ...]:
        """Five geometry slots, centre outward; gaps preserve module copy indices."""
        half = self.n_sensors // 2
        positions = (
            [int(name[6]) for name in self.module_names[half:]]
            if self.module_names
            else range(half)
        )
        slots = [None] * MAX_SENSORS_PER_HALF_LADDER
        for position, sensor in zip(positions, self.sensor_types[half:]):
            slots[position] = sensor
        return tuple(slots)

    @property
    def n_sensors(self) -> int:
        return len(self.sensor_types)

    def sensors_size_xy(self) -> np.ndarray:
        return np.asarray(
            [sensor.size_xy() for sensor in self.sensor_types], dtype=float
        )

    def sensor_positions(self) -> np.ndarray:
        # ConstructHalfLadder starts at one overlap, skips kNone without advancing,
        # and CreateLadder translates/mirrors the two copies by the signed offset.
        edge = SENSOR_OVERLAP_MM
        offset = self.half_ladder_offset_y
        assert offset is not None  # Resolved and validated during construction.
        top = []
        for sensor in self.half_ladder_layout:
            if sensor is None:
                continue
            height = sensor.size_xy()[1]
            centre = edge + height / 2 - SENSOR_OVERLAP_MM
            top.append(centre + offset)
            edge = centre + height / 2
        return np.asarray([-value for value in reversed(top)] + top)

    def sensor_bbox(self) -> np.ndarray:
        sizes = self.sensors_size_xy()
        widths, heights = sizes[:, 0], sizes[:, 1]
        centres = self.sensor_positions()
        return np.column_stack(
            (
                -0.5 * widths,
                0.5 * widths,
                centres - 0.5 * heights,
                centres + 0.5 * heights,
            )
        )

    @property
    def ladder_size_xy(self) -> tuple[float, float]:
        """Actual sensor-envelope width and height, including overlap and cutout."""
        boxes = self.sensor_bbox()
        return (
            float(boxes[:, 1].max() - boxes[:, 0].min()),
            float(boxes[:, 3].max() - boxes[:, 2].min()),
        )
