#!/usr/bin/env python3
"""Validation tests for the metric knowledge base."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metrics import MetricKnowledgeBase  # noqa: E402


class MetricKnowledgeBaseTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.kb = MetricKnowledgeBase(
            ROOT / "metrics" / "definitions.yaml"
        )

    def test_global_efficiency(self):
        global_info = self.kb.get("global_eff")

        self.assertEqual(
            global_info["name"],
            "Global Efficiency",
        )

        self.assertEqual(
            global_info["formula"]["text"],
            "GE = PE × CompScale",
        )

    def test_runtime_template_resolution(self):
        cuda_info = self.kb.get(
            "omp_parallel_eff",
            runtime="CUDA",
            runtime_family="cuda",
        )

        self.assertEqual(
            cuda_info["id"],
            "runtime_parallel_eff",
        )

        self.assertEqual(
            cuda_info["name"],
            "CUDA Parallel Efficiency",
        )

        self.assertEqual(
            cuda_info["family"],
            "cuda",
        )

    def test_legacy_conversion(self):
        legacy = self.kb.as_legacy_info(
            "dev_orches_eff"
        )

        self.assertEqual(
            legacy["label"],
            "Device Orchestration Efficiency",
        )

        self.assertTrue(
            legacy["typical_causes"]
        )

    def test_semantic_metric_levels(self):
        runtime_contribution = self.kb.get(
            "omp_parallel_eff",
            runtime="OpenMP",
            runtime_family="openmp",
        )

        self.assertEqual(
            runtime_contribution["analysis_level"],
            "runtime_contribution",
        )

        openmp_specific = self.kb.get(
            "omp_talp_parallel_eff"
        )

        self.assertEqual(
            openmp_specific["analysis_level"],
            "runtime_specific",
        )

        device_metric = self.kb.get(
            "dev_orches_eff"
        )

        self.assertEqual(
            device_metric["analysis_level"],
            "execution_domain",
        )

    def test_all_metrics_have_required_semantic_fields(self):
        for metric_id, metric in self.kb.metrics.items():

            with self.subTest(metric=metric_id):
                self.assertTrue(
                    metric.get("analysis_level")
                )

                self.assertTrue(
                    metric.get("metric_type")
                )

                self.assertTrue(
                    metric.get("name")
                    or metric.get("name_template")
                )

                self.assertTrue(
                    metric.get("definition")
                    or metric.get("definition_template")
                )


if __name__ == "__main__":
    unittest.main()
