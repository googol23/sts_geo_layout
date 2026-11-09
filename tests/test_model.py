import numpy as np
import pytest

from sts_geo_layout import LadderLayout, SensorType


def layout(ids=(1, 1, 1, 1), **kwargs):
    return LadderLayout([SensorType(value) for value in ids], **kwargs)


@pytest.mark.parametrize(
    "sensor_id,size,label",
    [
        (0, (62, 22), "k62_22"),
        (1, (62, 22), "k62_22"),
        (2, (62, 42), "k62_42"),
        (3, (62, 62), "k62_62"),
        (4, (62, 124), "k62_124"),
    ],
)
def test_sensor_definitions(sensor_id, size, label):
    sensor = SensorType(sensor_id)
    assert sensor.size_xy() == size
    assert str(sensor) == label


@pytest.mark.parametrize("sensor_id", [-1, 5, 1.5, "1"])
def test_invalid_sensor_type(sensor_id):
    with pytest.raises(ValueError, match="Unsupported sensor type"):
        SensorType(sensor_id)


def test_overlap_and_sensor_envelope():
    nominal = layout()
    np.testing.assert_allclose(nominal.sensor_positions(), [-26.1, -8.7, 8.7, 26.1])
    assert nominal.ladder_size_xy == pytest.approx((62, 74.2))
    assert nominal.sensor_bbox().shape == (4, 4)
    assert nominal.sensor_bbox()[0] == pytest.approx([-31, 31, -37.1, -15.1])


def test_cutout_mixed_sizes_and_support_length():
    nominal = layout((2, 1, 1, 2), cutout_size=82, length=818)
    np.testing.assert_allclose(nominal.sensor_positions(), [-79.4, -52, 52, 79.4])
    assert nominal.ladder_size_xy == pytest.approx((62, 200.8))
    assert nominal.length == 818
    boxes = nominal.sensor_bbox()
    assert boxes[2, 2] - boxes[1, 3] == pytest.approx(82)


@pytest.mark.parametrize("ids", [(), (1,), (1, 1, 1), (1, 2), (1, 2, 1, 2)])
def test_invalid_symmetry(ids):
    with pytest.raises(ValueError):
        layout(ids)


@pytest.mark.parametrize("field", ["length", "cutout_size"])
@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_dimensions(field, value):
    with pytest.raises(ValueError, match=field):
        layout(**{field: value})


def test_snapshot_is_immutable_and_retains_module_identity():
    sensors = [SensorType(1), SensorType(1)]
    names = ("M4DL1B0001162B2", "M4DL1T0001162B2")
    nominal = LadderLayout(sensors, module_names=names)
    sensors.clear()
    assert nominal.n_sensors == 2
    assert nominal.module_names == names


@pytest.mark.parametrize("names", [("one",), ("same", "same")])
def test_invalid_module_identity(names):
    with pytest.raises(ValueError, match="module_names"):
        layout((1, 1), module_names=names)


def test_equal_dimensions_with_distinct_sensor_ids_are_supported():
    assert layout((0, 1)).n_sensors == 2


def test_more_than_five_sensors_per_half_is_rejected():
    with pytest.raises(ValueError, match="at most five"):
        layout((1,) * 12)


@pytest.mark.parametrize("offset", [-10.0, 0.0, 15.0])
def test_explicit_signed_offset_is_independent_of_cutout(offset):
    nominal = layout((1, 1), cutout_size=82, half_ladder_offset_y=offset)
    assert nominal.half_ladder_offset_y == offset
    np.testing.assert_allclose(
        nominal.sensor_positions(), [-(11 + offset), 11 + offset]
    )


@pytest.mark.parametrize("offset", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_offset_is_rejected(offset):
    with pytest.raises(ValueError, match="half_ladder_offset_y"):
        layout(half_ladder_offset_y=offset)


def test_small_positive_cutout_has_no_legacy_threshold():
    nominal = layout((1, 1), cutout_size=0.1)
    assert nominal.half_ladder_offset_y == pytest.approx(0.05)
    np.testing.assert_allclose(nominal.sensor_positions(), [-11.05, 11.05])


def test_internal_empty_slot_preserves_indices_but_does_not_advance_placement():
    names = tuple(
        f"M4DL1{half}{slot}001162B2"
        for half, slot in (
            ("B", 2),
            ("B", 0),
            ("T", 0),
            ("T", 2),
        )
    )
    nominal = layout((2, 1, 1, 2), module_names=names)
    assert nominal.half_ladder_layout == (
        SensorType(1),
        None,
        SensorType(2),
        None,
        None,
    )
    np.testing.assert_allclose(
        nominal.sensor_positions(), layout((2, 1, 1, 2)).sensor_positions()
    )


@pytest.mark.parametrize(
    "names",
    [
        ("invalid", "M4DL1T0001162B2"),
        ("M4DL1B5001162B2", "M4DL1T5001162B2"),
        ("M4DL1B1001162B2", "M4DL1T0001162B2"),
        ("M4DL1T0001162B2", "M4DL1B0001162B2"),
    ],
)
def test_invalid_or_mismatched_module_slots_are_rejected(names):
    with pytest.raises(ValueError):
        layout((1, 1), module_names=names)


def test_distinct_modules_cannot_share_a_geometry_slot():
    names = (
        "M4DL1B0001162B2",
        "M4DL1B0101162B2",
        "M4DL1T0001162B2",
        "M4DL1T0101162B2",
    )
    with pytest.raises(ValueError, match="pair B/T slots"):
        layout(module_names=names)
