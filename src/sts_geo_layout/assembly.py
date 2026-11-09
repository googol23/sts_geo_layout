"""Read-only assembly adapter; no dependency on workspace sts_db_api modules."""

import os
from contextlib import contextmanager

from sts_utils.sts_naming import (
    LADDER_NAME_PATTERN,
    MODULE_NAME_PATTERN,
    is_valid_label,
)

from .model import MAX_SENSORS_PER_HALF_LADDER, LadderLayout, SensorType
from .supports import CF_SUPPORT_TYPE

LATEST_MODULES_SQL = """
WITH latest AS (
    SELECT overlay(name PLACING '0' FROM 8 FOR 1) AS name_base,
           MAX(substring(name FROM 8 FOR 1)) AS version
    FROM public.sts_module
    WHERE ladder_name = %s
    GROUP BY name_base
)
SELECT module.name, module.sensor_name
FROM public.sts_module AS module
JOIN latest ON module.name = overlay(latest.name_base PLACING latest.version FROM 8 FOR 1)
WHERE module.ladder_name = %s;
"""


def connect():
    """Open an owned, read-only connection using DB_* environment variables."""
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Set required database environment variables: " + ", ".join(missing)
        )
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as error:
        raise RuntimeError(
            "Database loading requires: pip install 'sts-geo-layout[assembly]'"
        ) from error

    try:
        connection = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
    except Exception as error:
        raise RuntimeError(
            "Could not connect to assembly database; check DB_* configuration and server access"
        ) from error
    try:
        connection.set_session(readonly=True, autocommit=True)
    except Exception:
        connection.close()
        raise
    return connection


@contextmanager
def _connection(connection):
    owned = connection is None
    if owned:
        connection = connect()
    try:
        yield connection
    finally:
        if owned:
            connection.close()


def sort_modules_bottom_to_top(modules):
    """Validate manufacturing labels, then order B descending followed by T ascending."""
    modules = list(modules)
    for name in modules:
        if not is_valid_label(name, MODULE_NAME_PATTERN):
            raise ValueError(f"Invalid module name: {name}")
        if int(name[6]) >= MAX_SENSORS_PER_HALF_LADDER:
            raise ValueError(f"Module position is outside geometry slots 0..4: {name}")
    return sorted(
        modules,
        key=lambda name: (0, -int(name[6])) if name[5] == "B" else (1, int(name[6])),
    )


def load_layout(ladder_name: str, connection=None) -> LadderLayout:
    """Load latest revisions and retain literal 0..4 module slots without renumbering.

    A supplied dict-cursor connection stays open. Ladder names are passed through;
    their naming scheme and the DB's position origin must be verified by the caller.
    """
    if not is_valid_label(ladder_name, LADDER_NAME_PATTERN):
        raise ValueError(f"Invalid ladder name: {ladder_name}")
    support_id = int(ladder_name[-2:])
    if support_id not in CF_SUPPORT_TYPE:
        raise ValueError(f"Unknown support type {support_id} for ladder {ladder_name}")

    with _connection(connection) as connection:
        with connection.cursor() as cursor:
            cursor.execute(LATEST_MODULES_SQL, (ladder_name, ladder_name))
            rows = cursor.fetchall()
    if not rows:
        raise ValueError(f"No modules found for ladder {ladder_name}")
    modules = sort_modules_bottom_to_top(row["name"] for row in rows)
    if len(set(modules)) != len(modules):
        raise ValueError(f"Duplicate modules for ladder {ladder_name}")
    bottom = [name[6] for name in modules if name[5] == "B"]
    top = [name[6] for name in modules if name[5] == "T"]
    if not bottom or sorted(bottom) != sorted(top) or len(set(bottom)) != len(bottom):
        raise ValueError(
            f"Module positions are not mirror-symmetric for ladder {ladder_name}"
        )

    records = {row["name"]: row for row in rows}
    sensors = []
    for name in modules:
        raw = records[name]["sensor_name"]
        try:
            # Assembly IDs are mapped by SensorType, not cast to ROOT enum ordinals.
            sensor_id = int(str(raw)[-1]) if raw is not None else -1
            sensors.append(SensorType(sensor_id))
        except (ValueError, IndexError) as error:
            raise ValueError(
                f"Invalid sensor_name {raw!r} for module {name}"
            ) from error
    support = CF_SUPPORT_TYPE[support_id]
    return LadderLayout(
        sensors, cutout_size=support[4], length=support[5], module_names=modules
    )


def load_layouts(ladder_names=None, connection=None) -> dict[str, LadderLayout]:
    """Load selected ladders, or all ladders, using one connection for the whole batch."""
    with _connection(connection) as connection:
        if ladder_names is None:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM public.sts_ladder ORDER BY name;")
                ladder_names = [row["name"] for row in cursor.fetchall()]
            if not ladder_names:
                raise ValueError("No ladder names found in assembly database")
        return {
            name: load_layout(name, connection) for name in sorted(set(ladder_names))
        }
