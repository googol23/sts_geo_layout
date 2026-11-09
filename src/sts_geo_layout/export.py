"""LadderInfo configuration export for the v26a builder, in cm."""

import json
from collections.abc import Mapping
from pathlib import Path

from sts_utils.sts_naming import LADDER_NAME_PATTERN, is_valid_label

from .model import LadderLayout, SensorType


def geometry_document(layouts: Mapping[str, LadderLayout]) -> dict:
    """Use ladder-name keys for LadderInfo.name and emit its four remaining members."""
    if not layouts:
        raise ValueError("At least one ladder layout is required")
    types = []
    definitions = {}
    for name, layout in sorted(layouts.items()):
        if not is_valid_label(name, LADDER_NAME_PATTERN):
            raise ValueError(f"Invalid ladder name: {name}")
        if layout.length <= 0:
            raise ValueError(
                f"Support length must be positive for geometry export: {name}"
            )
        slots = [
            str(sensor) if sensor is not None else "kNone"
            for sensor in layout.half_ladder_layout
        ]
        offset = layout.half_ladder_offset_y
        assert offset is not None  # Resolved and validated by LadderLayout.
        signature = (tuple(slots), layout.length, layout.cutout_size, offset)
        layout_id = int(name[-2:])
        if layout_id in definitions and definitions[layout_id][0] != signature:
            previous = definitions[layout_id][1]
            raise ValueError(
                f"Conflicting LadderInfo definitions for layout ID {layout_id:02d}: {previous} and {name}"
            )
        definitions[layout_id] = (signature, name)
        types.append(
            {
                name: {
                    "layout": slots,
                    "length": round(layout.length / 10, 2),
                    "cutoutSize": round(layout.cutout_size / 10, 2),
                    "halfLadderOffsetY": round(offset / 10, 2),
                }
            }
        )
    return {"types": types}


def write_geometry_yaml(layouts: Mapping[str, LadderLayout], output) -> Path:
    """Write deterministic, safe YAML; only this export uses two-decimal cm floats."""
    try:
        import yaml
    except ImportError as error:
        raise RuntimeError(
            "YAML export requires: pip install 'sts-geo-layout[export]'"
        ) from error

    class SensorList(list):
        pass

    class GeometryDumper(yaml.SafeDumper):
        pass

    GeometryDumper.add_representer(
        SensorList,
        lambda dumper, values: dumper.represent_sequence(
            "tag:yaml.org,2002:seq",
            values,
            flow_style=True,
        ),
    )
    GeometryDumper.add_representer(
        float,
        lambda dumper, value: dumper.represent_scalar(
            "tag:yaml.org,2002:float",
            f"{value:.2f}",
        ),
    )
    document = geometry_document(layouts)
    for entry in document["types"]:
        fields = next(iter(entry.values()))
        fields["layout"] = SensorList(fields["layout"])
    text = yaml.dump(
        document, Dumper=GeometryDumper, sort_keys=False, default_flow_style=False
    )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def read_snapshot(source) -> dict[str, LadderLayout]:
    """Read an offline JSON mapping of ladder names to bottom-to-top sensor IDs (mm)."""
    document = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("A layout snapshot must map ladder names to layout fields")
    layouts = {}
    allowed = {
        "sensor_types",
        "cutout_size",
        "length",
        "module_names",
        "half_ladder_offset_y",
    }
    for name, fields in document.items():
        if not isinstance(fields, dict) or "sensor_types" not in fields:
            raise ValueError(f"Missing sensor_types for ladder {name}")
        if fields.keys() - allowed:
            raise ValueError(
                f"Unknown snapshot fields for {name}: {sorted(fields.keys() - allowed)}"
            )
        fields = dict(fields)
        fields["sensor_types"] = [SensorType(value) for value in fields["sensor_types"]]
        layouts[name] = LadderLayout(**fields)
    return layouts
