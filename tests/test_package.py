import subprocess
import sys


def test_core_import_has_no_optional_or_workspace_dependencies(tmp_path):
    code = """
import sys
from sts_geo_layout import LadderLayout, SensorType
assert not {'yaml', 'matplotlib', 'psycopg2', 'db', 'ladder_layout'} & sys.modules.keys()
assert LadderLayout([SensorType(1)] * 2).n_sensors == 2
"""
    subprocess.run(
        [sys.executable, "-I", "-c", code], cwd=tmp_path, check=True, timeout=30
    )
    subprocess.run(
        [sys.executable, "-I", "-m", "sts_geo_layout", "--help"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=30,
    )
