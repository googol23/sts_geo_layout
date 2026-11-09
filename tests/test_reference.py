"""Frozen v26a reference cases, not a runtime dependency on the external macro."""

import json
from pathlib import Path

import numpy as np
import pytest

from sts_geo_layout import LadderLayout, SensorType
from sts_geo_layout.export import geometry_document
from sts_geo_layout.model import MAX_SENSORS_PER_HALF_LADDER, SENSOR_OVERLAP_MM
from sts_geo_layout.supports import CF_SUPPORT_TYPE

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "v26a_reference.json").read_text()
)


def test_reference_constants():
    assert SENSOR_OVERLAP_MM == REFERENCE["overlap_mm"]
    assert MAX_SENSORS_PER_HALF_LADDER == REFERENCE["max_half_ladder_slots"]
    for sensor_id, size in REFERENCE["sensor_sizes_mm"].items():
        assert SensorType(int(sensor_id)).size_xy() == tuple(size)


@pytest.mark.parametrize("case", REFERENCE["ladders"], ids=lambda case: case["name"])
def test_reference_placement_and_complete_ladder_info(case):
    half = case["half_sensor_ids"]
    nominal = LadderLayout(
        [SensorType(value) for value in half[::-1] + half],
        cutout_size=case["cutout_mm"],
        length=case["length_mm"],
    )
    assert nominal.half_ladder_offset_y == pytest.approx(case["half_offset_mm"])
    positive = case["positive_copy_y_mm"]
    np.testing.assert_allclose(
        nominal.sensor_positions(), [-value for value in positive[::-1]] + positive
    )
    fields = geometry_document({case["name"]: nominal})["types"][0][case["name"]]
    assert fields == {
        "layout": case["layout"],
        "length": pytest.approx(case["length_mm"] / 10),
        "cutoutSize": pytest.approx(case["cutout_mm"] / 10),
        "halfLadderOffsetY": pytest.approx(case["half_offset_mm"] / 10),
    }
    support = CF_SUPPORT_TYPE[int(case["name"][-2:])]
    assert support[4:6] == (case["cutout_mm"], case["length_mm"])
