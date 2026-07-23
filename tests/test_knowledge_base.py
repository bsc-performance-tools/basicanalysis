#!/usr/bin/env python3
"""Small dependency-free validation/smoke test."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metrics import MetricKnowledgeBase  # noqa: E402


def main() -> None:
    kb = MetricKnowledgeBase(ROOT / "metrics" / "definitions.yaml")

    global_info = kb.get("global_eff")
    assert global_info["name"] == "Global Efficiency"
    assert global_info["formula"]["text"] == "GE = PE × CompScale"

    cuda_info = kb.get(
        "omp_parallel_eff",
        runtime="CUDA",
        runtime_family="cuda",
    )
    assert cuda_info["id"] == "runtime_parallel_eff"
    assert cuda_info["name"] == "CUDA Parallel Efficiency"
    assert cuda_info["family"] == "cuda"

    legacy = kb.as_legacy_info("dev_orches_eff")
    assert legacy["label"] == "Device Orchestration Efficiency"
    assert legacy["typical_causes"]

    print(
        "Knowledge base OK: {} canonical metrics, {} aliases".format(
            len(kb.metrics), len(kb.aliases)
        )
    )


if __name__ == "__main__":
    main()
