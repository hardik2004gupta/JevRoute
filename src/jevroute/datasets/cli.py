"""Dataset CLI: validate, inspect, split, manifest, hash, status commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jevroute.datasets.hasher import hash_file
from jevroute.datasets.quality import generate_quality_report
from jevroute.datasets.validator import check_split_leakage, validate_dataset


def cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    report = validate_dataset(path)
    print(json.dumps(report.model_dump(), indent=2))
    if report.gate_passed:
        print(f"\nGATE: PASS ({report.record_count} records, 0 critical errors)")
        return 0
    print(f"\nGATE: BLOCKED ({len(report.errors)} error(s))")
    return 1


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"File:    {path}")
    print(f"Records: {len(lines)}")
    print(f"Hash:    {hash_file(path)}")
    if lines:
        try:
            first = json.loads(lines[0])
            print(f"Fields:  {list(first.keys())}")
            has_gt = "ground_truth" in first
            print(f"Has ground_truth: {has_gt}")
            if has_gt:
                gt = first["ground_truth"]
                print(f"GT fields: {list(gt.keys())}")
        except json.JSONDecodeError as exc:
            print(f"WARNING: first row parse error: {exc}")
    return 0


def cmd_hash(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    h = hash_file(path)
    print(h)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    datasets_dir = Path(args.datasets_dir)
    stem = args.stem
    splits: dict[str, object] = {}
    for split_name in ("train", "validation", "test"):
        p = datasets_dir / split_name / f"{stem}.jsonl"
        if p.exists():
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            splits[split_name] = {"exists": True, "records": len(lines), "hash": hash_file(p)[:16] + "..."}
        else:
            splits[split_name] = {"exists": False}
    manifest = datasets_dir / "manifests" / f"frozen_test_{stem}.json"
    print(json.dumps({
        "dataset_stem": stem,
        "splits": splits,
        "test_frozen": manifest.exists(),
        "manifest_path": str(manifest) if manifest.exists() else None,
    }, indent=2))
    return 0


def cmd_quality(args: argparse.Namespace) -> int:
    report = generate_quality_report(
        dataset_dir=args.datasets_dir,
        output_dir=args.output_dir,
        dataset_stem=args.stem,
    )
    gate = report.get("benchmark_gate", "UNKNOWN")
    print(f"Quality report written to {args.output_dir}")
    print(f"Benchmark gate: {gate}")
    return 0 if gate == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jevroute-dataset", description="JevRoute dataset tools")
    sub = parser.add_subparsers(dest="command")

    p_validate = sub.add_parser("validate", help="Validate a JSONL dataset file")
    p_validate.add_argument("path", help="Path to JSONL file")

    p_inspect = sub.add_parser("inspect", help="Inspect a dataset file (record count, hash, fields)")
    p_inspect.add_argument("path", help="Path to JSONL file")

    p_hash = sub.add_parser("hash", help="Print SHA-256 of a dataset file")
    p_hash.add_argument("path", help="Path to file")

    p_status = sub.add_parser("status", help="Show split status for a dataset")
    p_status.add_argument("--datasets-dir", default="datasets", help="Datasets directory")
    p_status.add_argument("--stem", default="benchmark_fixture", help="Dataset stem name")

    p_quality = sub.add_parser("quality", help="Generate quality report")
    p_quality.add_argument("--datasets-dir", default="datasets")
    p_quality.add_argument("--output-dir", default="results/data-quality")
    p_quality.add_argument("--stem", default="benchmark_fixture")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    handlers = {
        "validate": cmd_validate,
        "inspect": cmd_inspect,
        "hash": cmd_hash,
        "status": cmd_status,
        "quality": cmd_quality,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
