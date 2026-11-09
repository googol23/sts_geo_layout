"""Export nominal ladder layouts for geometry generation, online or offline."""

import argparse
from pathlib import Path

from .export import read_snapshot, write_geometry_yaml


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Write geometry-builder YAML in cm")
    source = export.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Offline JSON layout snapshot in mm")
    source.add_argument(
        "--database", action="store_true", help="Query the assembly database"
    )
    export.add_argument(
        "--ladder",
        action="append",
        help="Database ladder name; repeat to select several",
    )
    export.add_argument("--output", type=Path, required=True, help="Output YAML path")
    args = parser.parse_args(argv)
    if args.ladder and not args.database:
        parser.error("--ladder is only supported with --database")
    if args.input and args.input.resolve() == args.output.resolve():
        parser.error("Output must differ from the input snapshot")
    try:
        if args.database:
            from .assembly import load_layouts

            layouts = load_layouts(args.ladder)
        else:
            layouts = read_snapshot(args.input)
        output = write_geometry_yaml(layouts, args.output)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        parser.exit(2, f"sts-geo-layout: {error}\n")
    print(f"Exported {len(layouts)} ladder layout(s) to {output}")
    return 0
