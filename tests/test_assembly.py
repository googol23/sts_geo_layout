import pytest

from sts_geo_layout import assembly


def module(half, position):
    return f"M4DL1{half}{position}001162B2"


def records():
    return [
        {"name": module("T", 1), "sensor_name": "sensor2"},
        {"name": module("B", 0), "sensor_name": "sensor1"},
        {"name": module("T", 0), "sensor_name": "sensor1"},
        {"name": module("B", 1), "sensor_name": "sensor2"},
    ]


class Connection:
    def __init__(self, rows=None):
        self.rows = records() if rows is None else rows
        self.closed = False
        self.calls = []

    def cursor(self):
        return Cursor(self)

    def close(self):
        self.closed = True


class Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, parameters=None):
        self.connection.calls.append((query, parameters))
        self.query = query

    def fetchall(self):
        if "public.sts_ladder" in self.query:
            return [{"name": "L4DL000161"}, {"name": "L5DL000161"}]
        return self.connection.rows


def test_borrowed_connection_ordering_and_sensor_mapping():
    connection = Connection()
    layout = assembly.load_layout("L4DL000161", connection)
    assert not connection.closed
    assert layout.module_names == tuple(
        module(half, index)
        for half, index in (
            ("B", 1),
            ("B", 0),
            ("T", 0),
            ("T", 1),
        )
    )
    assert [sensor.id for sensor in layout.sensor_types] == [2, 1, 1, 2]
    assert layout.cutout_size == 82
    assert layout.length == 818
    assert layout.half_ladder_offset_y == 41
    assert connection.calls[0][1] == ("L4DL000161", "L4DL000161")
    assert "MAX(substring(name FROM 8 FOR 1))" in connection.calls[0][0]


def test_owned_connection_closes(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(assembly, "connect", lambda: connection)
    assembly.load_layout("L4DL000161")
    assert connection.closed


@pytest.mark.parametrize("owned", [False, True])
def test_connection_ownership_on_failure(monkeypatch, owned):
    connection = Connection([])
    monkeypatch.setattr(assembly, "connect", lambda: connection)
    with pytest.raises(ValueError, match="No modules"):
        assembly.load_layout("L4DL000161", None if owned else connection)
    assert connection.closed is owned


def test_batch_reuses_one_owned_connection(monkeypatch):
    connection = Connection()
    opened = []

    def connect():
        opened.append(connection)
        return connection

    monkeypatch.setattr(assembly, "connect", connect)
    assert list(assembly.load_layouts()) == ["L4DL000161", "L5DL000161"]
    assert len(opened) == 1
    assert len(connection.calls) == 3
    assert connection.closed


@pytest.mark.parametrize("name", ["invalid", "L4DL000199"])
def test_invalid_ladder_or_unknown_support_never_connects(monkeypatch, name):
    def unexpected():
        pytest.fail("Invalid ladder must not open a database connection")

    monkeypatch.setattr(assembly, "connect", unexpected)
    with pytest.raises(ValueError):
        assembly.load_layout(name)


def test_bad_module_label_is_rejected():
    rows = records()
    rows[0]["name"] = "invalid"
    with pytest.raises(ValueError, match="Invalid module name"):
        assembly.load_layout("L4DL000161", Connection(rows))


def test_unbalanced_module_positions_are_rejected():
    with pytest.raises(ValueError, match="Module positions"):
        assembly.load_layout("L4DL000161", Connection(records()[:-1]))


@pytest.mark.parametrize("value", [None, "", "sensor9", "nonsense"])
def test_bad_sensor_record_is_not_silently_skipped(value):
    rows = records()
    rows[0]["sensor_name"] = value
    with pytest.raises(ValueError, match="Invalid sensor_name"):
        assembly.load_layout("L4DL000161", Connection(rows))


def test_sensor_asymmetry_is_rejected():
    rows = records()
    rows[0]["sensor_name"] = "sensor4"
    with pytest.raises(ValueError, match="mirror-symmetric"):
        assembly.load_layout("L4DL000161", Connection(rows))


@pytest.mark.parametrize("position", [5, 9])
def test_module_positions_outside_macro_slots_are_rejected(position):
    rows = [
        {"name": module("B", position), "sensor_name": "sensor1"},
        {"name": module("T", position), "sensor_name": "sensor1"},
    ]
    with pytest.raises(ValueError, match="outside geometry slots 0..4"):
        assembly.load_layout("L4DL000161", Connection(rows))


def test_slot_gaps_are_preserved_from_database_records():
    rows = records()
    rows[0]["name"] = module("T", 2)
    rows[3]["name"] = module("B", 2)
    layout = assembly.load_layout("L4DL000161", Connection(rows))
    assert [
        None if sensor is None else sensor.id for sensor in layout.half_ladder_layout
    ] == [1, None, 2, None, None]
    assert layout.module_names[0] == module("B", 2)


def test_zero_cutout_uses_negative_half_overlap():
    layout = assembly.load_layout("L4DL600119", Connection())
    assert layout.cutout_size == 0
    assert layout.half_ladder_offset_y == pytest.approx(-2.3)


def test_database_configuration_has_no_password_fallback(monkeypatch):
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        assembly.connect()
