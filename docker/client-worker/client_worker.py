#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkerRuntime:
    network: str
    manifest: dict[str, Any]
    manifest_path: Path
    role: str = "client"

    def get_manifest_key(self, key: str, default: Any = None) -> Any:
        return self.manifest.get(key, default)

    def require_manifest_key(self, key: str) -> Any:
        if key not in self.manifest:
            raise KeyError(f"Manifest key '{key}' not found in {self.manifest_path}")
        return self.manifest[key]


def load_function(module_path: Path, function_name: str):
    sys.path.insert(0, str(module_path.parent))
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, function_name):
        raise AttributeError(f"{function_name} not found in {module_path}")
    return getattr(module, function_name)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")


def run(job_path: Path) -> int:
    job = read_json(job_path)
    output_path = Path(job.get("output_path", "/din/output/result.json"))

    try:
        model_base_dir = Path(job["model_base_dir"])
        manifest_path = Path(job.get("manifest_path", model_base_dir / "manifest.json"))
        manifest = read_json(manifest_path)

        service_entry = manifest["train_client_model_and_upload_to_ipfs"]
        service_path = model_base_dir / service_entry["path"]
        train_fn = load_function(service_path, "train_client_model_and_upload_to_ipfs")

        runtime = WorkerRuntime(
            network=job["network"],
            manifest=manifest,
            manifest_path=manifest_path,
        )

        cid = train_fn(
            job["genesis_model_ipfs_hash"],
            job["account_address"],
            job["network"],
            initial_model_ipfs_hash=job.get("initial_model_ipfs_hash"),
            model_base_dir=model_base_dir,
            gi=job.get("gi"),
            runtime=runtime,
        )

        write_json(
            output_path,
            {
                "status": "ok",
                "client_model_ipfs_hash": cid,
            },
        )
        return 0

    except Exception as exc:
        write_json(
            output_path,
            {
                "status": "error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a DIN client training job.")
    parser.add_argument("--job", default="/din/job/job.json", help="Path to the mounted worker job JSON.")
    args = parser.parse_args()
    raise SystemExit(run(Path(args.job)))


if __name__ == "__main__":
    main()
