from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .common import kubectl_apply_manifest, kubectl_delete_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply or delete a Chaos Mesh manifest from a YAML file."
    )
    parser.add_argument("action", choices=["apply", "revert"])
    parser.add_argument("filepath", help="Path to the Chaos Mesh YAML manifest")
    return parser


def read_yaml(filepath: str) -> str:
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"YAML manifest not found: {filepath}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()

    try:
        yaml_text = read_yaml(args.filepath)
        if args.action == "apply":
            print(kubectl_apply_manifest(yaml_text))
        else:
            print(kubectl_delete_manifest(yaml_text))
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
