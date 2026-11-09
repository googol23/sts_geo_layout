import json

import pytest
import yaml

from sts_geo_layout import LadderLayout, SensorType
from sts_geo_layout.cli import main
from sts_geo_layout.export import geometry_document, read_snapshot, write_geometry_yaml


def nominal(cutout=82):
    return LadderLayout([SensorType(value) for value in (2, 1, 1, 2)], cutout, 818)


def test_geometry_schema_units_and_half_ordering():
    assert geometry_document({"L4DL000161": nominal()}) == {
        "types": [
            {
                "L4DL000161": {
                    "length": pytest.approx(81.8),
                    "cutoutSize": pytest.approx(8.2),
                    "halfLadderOffsetY": pytest.approx(4.1),
                    "layout": ["k62_22", "k62_42", "kNone", "kNone", "kNone"],
                }
            }
        ]
    }
    fields = geometry_document({"L4DL000161": nominal(0)})["types"][0]["L4DL000161"]
    assert fields["cutoutSize"] == 0
    assert fields["halfLadderOffsetY"] == pytest.approx(-0.23)


def test_document_and_yaml_share_the_same_cm_precision(tmp_path):
    layout = LadderLayout([SensorType(1)] * 2, cutout_size=95.6, length=818.1234)
    layouts = {"L4DL000161": layout}
    document = geometry_document(layouts)
    fields = document["types"][0]["L4DL000161"]
    assert fields["length"] == 81.81
    assert fields["cutoutSize"] == 9.56
    assert fields["halfLadderOffsetY"] == 4.78
    output = write_geometry_yaml(layouts, tmp_path / "geometry.yaml")
    assert yaml.safe_load(output.read_text()) == document


def test_yaml_round_trip_determinism_and_no_global_representers(tmp_path):
    before = yaml.dump({"value": 1.23456789})
    layouts = {"L5DL000161": nominal(), "L4DL000161": nominal()}
    first = write_geometry_yaml(layouts, tmp_path / "nested" / "geometry.yaml")
    text = first.read_text()
    assert yaml.safe_load(text) == geometry_document(layouts)
    assert "length: 81.80" in text
    assert "layout: [k62_22, k62_42, kNone, kNone, kNone]" in text
    assert text.index("L4DL") < text.index("L5DL")
    assert yaml.dump({"value": 1.23456789}) == before
    second = write_geometry_yaml(
        dict(reversed(list(layouts.items()))), tmp_path / "second.yaml"
    )
    assert second.read_bytes() == first.read_bytes()


@pytest.mark.parametrize(
    "layouts",
    [
        {},
        {"invalid": nominal()},
        {"L4DL000161": LadderLayout([SensorType(1)] * 2)},
    ],
)
def test_invalid_export_does_not_replace_output(tmp_path, layouts):
    output = tmp_path / "geometry.yaml"
    output.write_text("preserved")
    with pytest.raises(ValueError):
        write_geometry_yaml(layouts, output)
    assert output.read_text() == "preserved"


def test_offline_snapshot_and_cli(tmp_path):
    source = tmp_path / "snapshot.json"
    source.write_text(
        json.dumps(
            {
                "L4DL000161": {
                    "sensor_types": [2, 1, 1, 2],
                    "cutout_size": 82,
                    "length": 818,
                }
            }
        )
    )
    output = tmp_path / "geometry.yaml"
    assert read_snapshot(source)["L4DL000161"].length == 818
    assert main(["export", "--input", str(source), "--output", str(output)]) == 0
    assert yaml.safe_load(output.read_text()) == geometry_document(
        {"L4DL000161": nominal()}
    )


def test_cli_protects_input_snapshot(tmp_path):
    source = tmp_path / "snapshot.json"
    source.write_text("preserved")
    with pytest.raises(SystemExit) as error:
        main(["export", "--input", str(source), "--output", str(source)])
    assert error.value.code == 2
    assert source.read_text() == "preserved"


def test_slots_from_module_names_are_not_compacted():
    names = tuple(
        f"M4DL1{half}{slot}001162B2"
        for half, slot in (
            ("B", 2),
            ("B", 0),
            ("T", 0),
            ("T", 2),
        )
    )
    layout = LadderLayout(nominal().sensor_types, length=818, module_names=names)
    fields = geometry_document({"L4DL000161": layout})["types"][0]["L4DL000161"]
    assert fields["layout"] == ["k62_22", "kNone", "k62_42", "kNone", "kNone"]


def test_leading_empty_slots_and_legacy_db_zero_are_distinct():
    layout = LadderLayout(
        [SensorType(0), SensorType(0)],
        length=818,
        module_names=("M4DL1B2001162B2", "M4DL1T2001162B2"),
    )
    fields = geometry_document({"L4DL000161": layout})["types"][0]["L4DL000161"]
    assert fields["layout"] == ["kNone", "kNone", "k62_22", "kNone", "kNone"]


@pytest.mark.parametrize(
    "changes",
    [
        {"length": 818.00001},
        {"cutout_size": 82.00001},
        {"half_ladder_offset_y": 41.00001},
        {"sensor_types": [SensorType(1)] * 2},
    ],
)
def test_same_layout_id_conflicts_are_rejected_before_rounding(tmp_path, changes):
    fields = {"sensor_types": nominal().sensor_types, "cutout_size": 82, "length": 818}
    fields.update(changes)
    layouts = {"L4DL000161": nominal(), "L5DL000161": LadderLayout(**fields)}
    output = tmp_path / "geometry.yaml"
    output.write_text("preserved")
    with pytest.raises(
        ValueError, match="Conflicting LadderInfo definitions for layout ID 61"
    ):
        write_geometry_yaml(layouts, output)
    assert output.read_text() == "preserved"


def test_same_layout_id_cannot_hide_different_slot_indices():
    names = tuple(
        f"M4DL1{half}{slot}001162B2"
        for half, slot in (
            ("B", 2),
            ("B", 0),
            ("T", 0),
            ("T", 2),
        )
    )
    sparse = LadderLayout(
        nominal().sensor_types, cutout_size=82, length=818, module_names=names
    )
    with pytest.raises(ValueError, match="Conflicting LadderInfo"):
        geometry_document({"L4DL000161": nominal(), "L5DL000161": sparse})


def test_different_layout_ids_can_have_different_definitions():
    layouts = {"L4DL000161": nominal(), "L5DL000160": nominal(0)}
    assert len(geometry_document(layouts)["types"]) == 2


def test_snapshot_preserves_explicit_half_ladder_offset(tmp_path):
    source = tmp_path / "snapshot.json"
    source.write_text(
        json.dumps(
            {
                "L4DL000161": {
                    "sensor_types": [1, 1],
                    "cutout_size": 82,
                    "length": 818,
                    "half_ladder_offset_y": -1.2,
                }
            }
        )
    )
    layout = read_snapshot(source)["L4DL000161"]
    assert layout.half_ladder_offset_y == -1.2
    fields = geometry_document({"L4DL000161": layout})["types"][0]["L4DL000161"]
    assert fields["halfLadderOffsetY"] == -0.12
    assert fields["cutoutSize"] == 8.2


def test_snapshot_rejects_unknown_fields(tmp_path):
    source = tmp_path / "snapshot.json"
    source.write_text(
        json.dumps({"L4DL000161": {"sensor_types": [1, 1], "lenght": 818}})
    )
    with pytest.raises(ValueError, match="Unknown snapshot fields"):
        read_snapshot(source)
