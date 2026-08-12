import io
import unittest

from contextlib import redirect_stdout
from types import SimpleNamespace

from scaling import (
    get_scaling_info,
    get_scaling_type,
)


class ScalingTests(unittest.TestCase):

    def _make_args(
        self,
        scaling="auto",
        debug=False,
    ):
        return SimpleNamespace(
            scaling=scaling,
            debug=debug,
        )

    def _strong_scaling_data(self):
        """Create a simple strong-scaling experiment.

        The amount of useful work remains approximately constant
        while the number of processes increases.
        """

        trace_list = [
            "trace1",
            "trace2",
            "trace3",
        ]

        trace_processes = {
            "trace1": 1,
            "trace2": 2,
            "trace3": 4,
        }

        raw_data = {
            "useful_ins": {
                "trace1": 1000.0,
                "trace2": 1000.0,
                "trace3": 1000.0,
            },
            "runtime": {
                "trace1": 100.0,
                "trace2": 55.0,
                "trace3": 30.0,
            },
            "useful_avg": {
                "trace1": 100.0,
                "trace2": 55.0,
                "trace3": 30.0,
            },
        }

        return (
            raw_data,
            trace_list,
            trace_processes,
        )

    def _weak_scaling_data(self):
        """Create a simple weak-scaling experiment.

        Useful instructions increase proportionally with the
        number of processes while runtime remains approximately
        constant.
        """

        trace_list = [
            "trace1",
            "trace2",
            "trace3",
        ]

        trace_processes = {
            "trace1": 1,
            "trace2": 2,
            "trace3": 4,
        }

        raw_data = {
            "useful_ins": {
                "trace1": 1000.0,
                "trace2": 2000.0,
                "trace3": 4000.0,
            },
            "runtime": {
                "trace1": 100.0,
                "trace2": 100.0,
                "trace3": 100.0,
            },
            "useful_avg": {
                "trace1": 100.0,
                "trace2": 100.0,
                "trace3": 100.0,
            },
        }

        return (
            raw_data,
            trace_list,
            trace_processes,
        )

    def test_detects_strong_scaling(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._strong_scaling_data()

        info = get_scaling_info(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertTrue(
            info.has_scaling_analysis
        )

        self.assertEqual(
            info.detected,
            "strong",
        )

        self.assertEqual(
            info.selected,
            "strong",
        )

        self.assertEqual(
            info.selection_mode,
            "auto",
        )

        self.assertFalse(
            info.overridden
        )

    def test_detects_weak_scaling(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._weak_scaling_data()

        info = get_scaling_info(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertTrue(
            info.has_scaling_analysis
        )

        self.assertEqual(
            info.detected,
            "weak",
        )

        self.assertEqual(
            info.selected,
            "weak",
        )

        self.assertEqual(
            info.selection_mode,
            "auto",
        )

        self.assertFalse(
            info.overridden
        )

    def test_strong_scaling_evidence(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._strong_scaling_data()

        info = get_scaling_info(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertIsNotNone(
            info.normalized_inst_ratio
        )

        self.assertIsNotNone(
            info.normalized_runtime_ratio
        )

        self.assertIsNotNone(
            info.normalized_useful_avg_ratio
        )

        self.assertEqual(
            info.threshold,
            0.9,
        )

    def test_weak_scaling_indicators_exceed_threshold(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._weak_scaling_data()

        info = get_scaling_info(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertGreater(
            info.normalized_inst_ratio,
            info.threshold,
        )

        self.assertGreater(
            info.normalized_runtime_ratio,
            info.threshold,
        )

        self.assertGreater(
            info.normalized_useful_avg_ratio,
            info.threshold,
        )

    def test_manual_strong_override_of_weak_detection(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._weak_scaling_data()

        output = io.StringIO()

        with redirect_stdout(output):
            info = get_scaling_info(
                raw_data,
                trace_list,
                trace_processes,
                self._make_args(
                    scaling="strong"
                ),
            )

        self.assertEqual(
            info.detected,
            "weak",
        )

        self.assertEqual(
            info.selected,
            "strong",
        )

        self.assertEqual(
            info.selection_mode,
            "manual",
        )

        self.assertTrue(
            info.overridden
        )

        self.assertIn(
            "detected weak scaling",
            output.getvalue(),
        )

    def test_manual_weak_override_of_strong_detection(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._strong_scaling_data()

        output = io.StringIO()

        with redirect_stdout(output):
            info = get_scaling_info(
                raw_data,
                trace_list,
                trace_processes,
                self._make_args(
                    scaling="weak"
                ),
            )

        self.assertEqual(
            info.detected,
            "strong",
        )

        self.assertEqual(
            info.selected,
            "weak",
        )

        self.assertEqual(
            info.selection_mode,
            "manual",
        )

        self.assertTrue(
            info.overridden
        )

        self.assertIn(
            "detected strong scaling",
            output.getvalue(),
        )

    def test_manual_selection_matching_detection_is_not_override(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._weak_scaling_data()

        info = get_scaling_info(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(
                scaling="weak"
            ),
        )

        self.assertEqual(
            info.detected,
            "weak",
        )

        self.assertEqual(
            info.selected,
            "weak",
        )

        self.assertEqual(
            info.selection_mode,
            "manual",
        )

        self.assertFalse(
            info.overridden
        )

    def test_single_trace_has_no_scaling_analysis(self):
        trace_list = [
            "trace1",
        ]

        trace_processes = {
            "trace1": 128,
        }

        raw_data = {
            "useful_ins": {
                "trace1": 1000.0,
            },
            "runtime": {
                "trace1": 100.0,
            },
            "useful_avg": {
                "trace1": 80.0,
            },
        }

        info = get_scaling_info(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertFalse(
            info.has_scaling_analysis
        )

        self.assertIsNone(
            info.detected
        )

        # Historical compatibility value.
        self.assertEqual(
            info.selected,
            "strong",
        )

        self.assertEqual(
            info.selection_mode,
            "implicit",
        )

        self.assertFalse(
            info.overridden
        )

        self.assertEqual(
            info.status_message,
            "Single execution",
        )

    def test_get_scaling_type_preserves_strong_interface(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._strong_scaling_data()

        scaling = get_scaling_type(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertEqual(
            scaling,
            "strong",
        )

    def test_get_scaling_type_preserves_weak_interface(self):
        (
            raw_data,
            trace_list,
            trace_processes,
        ) = self._weak_scaling_data()

        scaling = get_scaling_type(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertEqual(
            scaling,
            "weak",
        )

    def test_get_scaling_type_single_trace_preserves_compatibility(self):
        trace_list = [
            "trace1",
        ]

        trace_processes = {
            "trace1": 64,
        }

        raw_data = {
            "useful_ins": {
                "trace1": 1000.0,
            },
            "runtime": {
                "trace1": 100.0,
            },
            "useful_avg": {
                "trace1": 90.0,
            },
        }

        scaling = get_scaling_type(
            raw_data,
            trace_list,
            trace_processes,
            self._make_args(),
        )

        self.assertEqual(
            scaling,
            "strong",
        )


if __name__ == "__main__":
    unittest.main()