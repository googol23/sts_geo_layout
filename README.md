# sts-geo-layout

An independently installable model of nominal STS ladder sensor arrangements, with
optional assembly-database loading, plotting and geometry-builder YAML export.
This is not measured alignment and does not inspect ROOT files. No ROOT runtime is
required. Python 3.10+, NumPy and the shared `sts-utils` package are required.

The read-only reference is `create_stsgeo_v26a.C`: `LadderInfo`, `BuildLadders`,
`ConstructHalfLadder` and `CreateLadder`. Assembly records supply the actual sensor
inventory and ordering; the macro defines how that configuration is interpreted.
The package never modifies or loads the macro. Its XY helpers are a configuration
preview, not a second implementation of the complete 3D geometry. Use the generated
ROOT geometry and `geo_inspector` for Z staggering, rotations, global placements,
and physical geometry inspection.

## Install once per consuming environment

From the surrounding `sts_tools` working directory:

```sh
python -m pip install -e ./sts_utils -e './sts_geo_layout[export,plot,assembly]'
```

Install only the extras you use. For offline geometry generation, `[export]` is
enough; for pure model calculations, omit all extras. `sts-utils` is private/local,
so supply its checkout explicitly. All projects can point to these same editable
checkouts; no copying or `PYTHONPATH` manipulation is required. Reinstall if package
metadata changes. Other application dependencies (e.g. metrology fitting or serial
hardware control) remain the responsibility of their applications.

Distribution name: `sts-geo-layout`. Import name: `sts_geo_layout`. CLI: `sts-geo-layout`.

## Nominal geometry in mm

```python
from sts_geo_layout import LadderLayout, SensorType

layout = LadderLayout(
    [SensorType(i) for i in (4, 4, 3, 2, 2, 3, 4, 4)],
    cutout_size=82.0,
    length=818.0,
)
print(layout.sensor_positions())
# [-317.2, -197.8, -109.4, -62.0, 62.0, 109.4, 197.8, 317.2]
print(layout.ladder_size_xy)        # (62.0, 758.4), the XY sensor envelope
print(layout.half_ladder_offset_y)  # 41.0
```

Sensors use bottom-to-top module order: B positions descending, then T positions
ascending. Every sensor is centred at X=0. The immutable model requires a nonempty,
even number of active sensors, mirrored dimensions, and at most five slots per
half-ladder. Optional `module_names` retain identities in that same order and must
pair matching B/T slot indices in 0..4. Gaps are retained, not renumbered.

Sensor IDs are assembly IDs, not C++ enum ordinals. The legacy DB ID-0 alias still
maps to 62 x 22 mm, like ID 1; it is **not** `kNone`. Empty geometry slots are Python
`None`. Geometry types 40x25, 31x42 and 15x42 exist in the macro but have no confirmed
DB-ID mapping here; unsupported IDs are rejected rather than guessed.

The reference overlap is **4.6 mm** (`fLadderSensorOverlapY = 0.46 cm`). The signed
`half_ladder_offset_y` is an independent field. If omitted or null, it defaults to
`cutout_size / 2` for a positive cutout, or `-4.6 / 2 = -2.3 mm` for zero cutout,
matching all current `BuildLadders` definitions. An explicit finite offset is
preserved, including negative values. There is no 0.2 mm cutout threshold.

Half-ladder placement starts at `height[0]/2` and advances by
`(height[i-1] + height[i])/2 - 4.6`. The two copies are translated/mirrored by the
signed offset. Empty slots do not advance placement, but retain module copy
indices. `half_ladder_layout` exposes those five centre-outward slots. Arbitrary
explicit offsets can move copies across Y=0; outputs retain module order rather
than being re-sorted by coordinate. `length` is the support length, not the envelope.

Unlike the removed root script, `ladder_size_xy` uses actual bounding-box extents,
not summed widths/heights. Four 62 x 22 mm sensors without a cutout occupy
62 x 74.2 mm, not 248 x 88 mm. The earlier 4.2 mm overlap would have given 75.4 mm;
that assumption is corrected. These changes affect LED mapping and plot limits.

Sensor enum labels now use both dimensions: `SensorType(1)` is `k62_22`, not
`k62_62`. Sensor sizes and the carbon-fibre support table are owned here, not by
the workspace's database package.

## Export geometry-builder YAML

Offline, using three supplied **macro-reference fixtures**, not live database records:

```sh
# From sts_tools:
sts-geo-layout export --input sts_geo_layout/examples/layouts.json --output output/layouts.yaml
# Equivalent module entry point:
python -m sts_geo_layout export --input sts_geo_layout/examples/layouts.json --output output/layouts.yaml
```

A snapshot is a JSON mapping from ladder names to `sensor_types` (integer IDs in
bottom-to-top module order), `cutout_size`, and `length`, all distances in mm.
Optional `module_names` and `half_ladder_offset_y` may be included. Without module
names, active slots are consecutive starting at zero. Unknown fields are rejected.
JSON is only an input convenience format; YAML describes all `LadderInfo` members.
For the reference `L4DL000161` entry (one of the three exported fixtures):

```yaml
types:
  - L4DL000161:
      layout: [k62_42, k62_62, k62_124, k62_124, kNone]
      length: 81.80
      cutoutSize: 8.20
      halfLadderOffsetY: 4.10
```

The Python API is independent of the input source:

```python
from sts_geo_layout.export import geometry_document, write_geometry_yaml

document = geometry_document({"L4DL000161": layout})
write_geometry_yaml({"L4DL000161": layout}, "output/layouts.yaml")
```

Export contract:

- Ladder entries are sorted by name; lengths are converted from mm to cm.
- The mapping key represents `LadderInfo.name`; the value contains `layout`,
  `length`, `cutoutSize`, and `halfLadderOffsetY` using the C++ member names.
- `layout` has exactly five half-ladder slots in **centre-outward** order. Empty
  slots are `kNone`, including internal or leading gaps identified by module names.
  A geometric mirror is required on the other half; unsupported asymmetry fails.
- `cutoutSize` is independent of the signed half-copy translation. For zero cutout,
  `halfLadderOffsetY` defaults to **-0.23 cm**. `firstSensorOffsetY` is no longer emitted.
- Ladders sharing the final two-digit layout ID must have identical slots, support
  length, cutout and offset. Conflicts are rejected **before** output rounding,
  matching `CreateLadders` reuse of logical volumes.
- Export values are rounded to two decimal places in cm in both the document API
  and YAML; sensor lists use flow style. The numerical model retains full precision.
- Export requires a positive support length. The output path is relative to the
  caller's working directory; parent directories are created.
- YAML serialization uses a local safe dumper; no global representers are changed.

This intentionally replaces the earlier legacy export schema and reversed half
ordering. Existing downstream YAML consumers must adopt the corrected fields.
The supplied macro hardcodes `BuildLadders` and contains **no YAML reader**. This
export describes its configuration; it does not make that macro consume YAML.
Adding a loader is a separate integration and must not modify this reference file.

## Load from assembly records

```python
from sts_geo_layout.assembly import load_layout, load_layouts

layout = load_layout("L4DL000161")
layouts = load_layouts(["L4DL000161"])
# Or reuse an existing psycopg2 connection configured with dict-like cursors:
layout = load_layout("L4DL000161", connection=connection)
```

The adapter queries `public.sts_ladder` and `public.sts_module`. It selects the
latest manufacturing-module revision using character 8 of the module name, as
before. This is separate from naming-scheme and package versions. Module positions
must pair across B/T halves, and sensor records must be valid and symmetric;
failures raise errors instead of silently dropping sensors. Slot numbers are used
literally; indices outside 0..4 fail and no one-based conversion is inferred. The
legacy schema's last-character sensor-type extraction is preserved.

Before production export, verify the DB's index origin and naming scheme. The
macro's `LadderName` stores a raw unit and remaps it in `GetUnit`; DB names must not
already be renumbered incompatibly. This package passes names unchanged and does
not guess a conversion. The DB ID-0 alias also requires schema confirmation before
it is changed; it must never be confused with the geometry's `kNone` ordinal.

For connections opened by the adapter, set `DB_HOST`, `DB_NAME`, `DB_USER`, and
`DB_PASSWORD`; set `DB_PORT` if it differs from the default 5432. Use your secret
management/environment configuration, not files committed to Git. There are no
built-in credentials. New connections are read-only; owned connections are always
closed, and caller-supplied connections are never closed or reconfigured. Batch
loading shares one connection. Existing workspace database helpers are not imported.

```sh
sts-geo-layout export --database --ladder L4DL000161 --output output/layouts.yaml
# Omit --ladder to export every ladder; repeat it to select several.
```

Assembly membership is live data. Save a snapshot with module identities, and
record the utilities/layout Git revisions for reproducible analysis.

## Plotting

```python
from sts_geo_layout.plotting import plot_layout

figure = plot_layout(layout)
figure.savefig("layout.png")
```

The function returns a Matplotlib figure; the caller owns saving and closing it.
No `draw()` or serialization methods are added to the numerical model.

## Migration and development

The root `ladder_layout.py` and `sts_db_api/sensor_type.py` were removed; their consumers
now import this package directly. The support table moved to `supports.py`.
Metrology uses the ordered module identities stored with its layout, rather than
querying the database again when assigning fit results.

From this project directory, after installing the shared utilities:

```sh
python -m pip install -e '.[test]'
python -m pytest
python -m pip wheel --no-deps . --wheel-dir dist
```

Tests cover geometry, units, slots, layout-ID conflicts, export round trips,
optional-import isolation, plotting, and database validation/connection ownership
using test doubles. `tests/fixtures/v26a_reference.json` records three independently
checked macro cases and the reference SHA-256; it is not production inventory or
a runtime macro dependency. Tests do not connect to the live database or execute
ROOT. Generated geometry remains the authority for later geometrical inspection.
