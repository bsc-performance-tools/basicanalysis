import io
import unittest

from contextlib import redirect_stdout
from types import SimpleNamespace

from scaling import (
    build_workload_map,
    describe_scaling,
    get_scaling_info,
)


class WorkloadScalingTests(unittest.TestCase):

    def _make_args(self, scaling="auto", workload=None, ratios_workload=None):
        return SimpleNamespace(
            scaling=scaling,
            debug=False,
            workload=workload,
            ratios_workload=ratios_workload,
        )

    def _data(self):
        """Same GPU, growing batch size: the processes do not change."""

        trace_list = ["b1.prv", "b4.prv", "b16.prv"]
        trace_processes = {trace: 1 for trace in trace_list}
        raw_data = {
            "useful_ins": {"b1.prv": 1000.0, "b4.prv": 3000.0, "b16.prv": 9000.0},
            "runtime": {"b1.prv": 100.0, "b4.prv": 150.0, "b16.prv": 300.0},
            "useful_avg": {"b1.prv": 90.0, "b4.prv": 140.0, "b16.prv": 290.0},
        }
        return raw_data, trace_list, trace_processes

    def _scaling_info(self, args):
        raw_data, trace_list, trace_processes = self._data()
        build_workload_map(args, trace_list)
        return get_scaling_info(raw_data, trace_list, trace_processes, args)

    def test_workload_values_become_ratios_of_reference(self):
        info = self._scaling_info(self._make_args(workload="2,8,32"))

        self.assertEqual(info.selected, "workload")
        self.assertEqual(info.selection_mode, "workload")
        self.assertFalse(info.overridden)
        self.assertEqual(
            info.workload_ratios,
            {"b1.prv": 1.0, "b4.prv": 4.0, "b16.prv": 16.0},
        )
        self.assertEqual(info.workload_values["b16.prv"], 32.0)

    def test_ratios_workload_is_used_as_given(self):
        info = self._scaling_info(self._make_args(ratios_workload="1,4,16"))

        self.assertEqual(
            info.workload_ratios,
            {"b1.prv": 1.0, "b4.prv": 4.0, "b16.prv": 16.0},
        )

    def test_ratios_workload_with_reference_not_one_warns(self):
        output = io.StringIO()
        with redirect_stdout(output):
            info = self._scaling_info(self._make_args(ratios_workload="2,8,32"))

        self.assertIn("==Warning==", output.getvalue())
        self.assertEqual(info.workload_ratios["b16.prv"], 16.0)

    def test_detected_scaling_is_kept_for_information(self):
        info = self._scaling_info(self._make_args(workload="1,4,16"))

        self.assertIn(info.detected, ("strong", "weak"))

    def test_work_ratio_replaces_every_resource_ratio(self):
        info = self._scaling_info(self._make_args(workload="1,4,16"))

        for resource_ratio in (1.0, 2.0, 3.5):
            self.assertEqual(info.work_ratio("b4.prv", resource_ratio), 4.0)

    def test_work_ratio_without_workload_is_the_resource_ratio(self):
        info = self._scaling_info(self._make_args(scaling="weak"))

        self.assertIsNone(info.workload_ratios)
        self.assertEqual(info.work_ratio("b4.prv", 2.5), 2.5)

    def test_values_follow_the_given_trace_order(self):
        args = self._make_args(workload="1,4,16")
        build_workload_map(args, ["b1.prv", "b4.prv", "b16.prv"])
        raw_data, _, trace_processes = self._data()

        # The analysis may reorder the traces; each keeps its value.
        info = get_scaling_info(
            raw_data, ["b1.prv", "b16.prv", "b4.prv"], trace_processes, args
        )

        self.assertEqual(info.workload_ratios["b16.prv"], 16.0)
        self.assertEqual(info.workload_ratios["b4.prv"], 4.0)

    def test_no_workload_option_leaves_map_empty(self):
        args = self._make_args()
        self.assertIsNone(build_workload_map(args, ["b1.prv", "b4.prv"]))
        self.assertIsNone(args.workload_map)

    def test_wrong_number_of_values_is_an_error(self):
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                build_workload_map(
                    self._make_args(workload="1,4"), ["a.prv", "b.prv", "c.prv"]
                )

    def test_non_positive_or_non_numeric_value_is_an_error(self):
        for text in ("1,0", "1,-2", "1,abc"):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    build_workload_map(
                        self._make_args(workload=text), ["a.prv", "b.prv"]
                    )

    def test_combining_with_weak_or_strong_is_an_error(self):
        for scaling in ("weak", "strong"):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    build_workload_map(
                        self._make_args(scaling=scaling, workload="1,2"),
                        ["a.prv", "b.prv"],
                    )

    def test_single_trace_has_no_scaling_analysis(self):
        args = self._make_args(workload="8")
        raw_data, _, trace_processes = self._data()
        build_workload_map(args, ["b1.prv"])

        info = get_scaling_info(raw_data, ["b1.prv"], trace_processes, args)

        self.assertFalse(info.has_scaling_analysis)
        self.assertEqual(info.selected, "strong")

    def test_description_names_the_option(self):
        info = self._scaling_info(self._make_args(ratios_workload="1,4,16"))

        self.assertEqual(
            describe_scaling(info),
            ("User-defined workload", "Manual (--ratios-workload)"),
        )


if __name__ == "__main__":
    unittest.main()
