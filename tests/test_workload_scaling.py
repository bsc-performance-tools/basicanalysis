import io
import unittest

from contextlib import redirect_stdout
from types import SimpleNamespace

from scaling import (
    build_workload_map,
    describe_detected,
    describe_domains,
    describe_scaling,
    detect_domain_scaling,
    get_scaling_info,
    has_workload,
    workload_table,
)


class WorkloadScalingTests(unittest.TestCase):

    def _make_args(self, scaling="auto", workload=None, host_workload=None,
                   device_workload=None):
        return SimpleNamespace(
            scaling=scaling,
            debug=False,
            workload=workload,
            host_workload=host_workload,
            device_workload=device_workload,
        )

    def _data(self):
        """Same GPU, growing batch size: the processes do not change."""

        trace_list = ["b1.prv", "b4.prv", "b16.prv"]
        trace_processes = {trace: 1 for trace in trace_list}
        raw_data = {
            "useful_ins": {"b1.prv": 1000.0, "b4.prv": 3000.0, "b16.prv": 9000.0},
            "runtime": {"b1.prv": 100.0, "b4.prv": 150.0, "b16.prv": 300.0},
            "useful_avg": {"b1.prv": 90.0, "b4.prv": 140.0, "b16.prv": 290.0},
            # Host/Device model: one host thread and one device.
            "count_host_threads": {trace: 1 for trace in trace_list},
            "count_devices": {trace: 1 for trace in trace_list},
            "useful_host": {"b1.prv": 20.0, "b4.prv": 21.0, "b16.prv": 22.0},
            "useful_device": {"b1.prv": 60.0, "b4.prv": 110.0, "b16.prv": 260.0},
        }
        return raw_data, trace_list, trace_processes

    def _scaling_info(self, args, has_domains=False):
        raw_data, trace_list, trace_processes = self._data()
        build_workload_map(args, trace_list)
        return get_scaling_info(raw_data, trace_list, trace_processes, args,
                                has_domains=has_domains)

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

    def test_values_can_be_ratios(self):
        # Ratios are values whose reference is 1: no separate option.
        sizes = self._scaling_info(self._make_args(workload="2,8,32"))
        ratios = self._scaling_info(self._make_args(workload="1,4,16"))

        self.assertEqual(sizes.workload_ratios, ratios.workload_ratios)

    def test_detector_is_not_used_in_workload_mode(self):
        info = self._scaling_info(self._make_args(workload="1,4,16"))

        self.assertIsNone(info.detected)
        self.assertEqual(describe_detected(info), "Not used (workload given)")

        info = self._scaling_info(self._make_args())
        self.assertIn(describe_detected(info), ("Strong", "Weak"))

    def test_one_domain_model_uses_the_application_ratio(self):
        info = self._scaling_info(self._make_args(workload="1,4,16"))

        self.assertEqual(info.domain_modes, {})
        for domain in (None, "host", "device"):
            self.assertEqual(info.work_ratio("b16.prv", 2.0, domain), 16.0)

    def test_workload_alone_applies_to_host_device_and_application(self):
        info = self._scaling_info(
            self._make_args(workload="1,4,16"), has_domains=True)

        self.assertEqual(info.domain_modes,
                         {"host": "workload", "device": "workload"})
        for domain in (None, "host", "device"):
            self.assertEqual(info.work_ratio("b16.prv", 2.0, domain), 16.0)
        self.assertEqual(
            describe_domains(info),
            [("Host", "User-defined workload", "Manual, --workload"),
             ("Device", "User-defined workload", "Manual, --workload")])

    def test_domain_workloads_with_the_application_workload(self):
        info = self._scaling_info(self._make_args(
            workload="1,4,16",
            host_workload="10,11,12",
            device_workload="1,4,16",
        ), has_domains=True)

        self.assertAlmostEqual(info.work_ratio("b16.prv", 2.0, "host"), 1.2)
        self.assertEqual(info.work_ratio("b16.prv", 2.0, "device"), 16.0)
        self.assertEqual(info.work_ratio("b16.prv", 2.0), 16.0)
        self.assertEqual(info.domain_workload_values["host"]["b4.prv"], 11.0)
        self.assertEqual(info.domain_workload_options,
                         {"host": "--host-workload",
                          "device": "--device-workload"})
        self.assertEqual(info.workload_option, "--workload")

    def test_device_workload_alone(self):
        # Device: its workload. Speedup and Scaling Efficiency: the Device
        # workload. Host: detected from the Host measurements only.
        info = self._scaling_info(
            self._make_args(device_workload="1,256,1024"), has_domains=True)

        self.assertEqual(info.selected, "workload")
        self.assertEqual(info.workload_option, "--device-workload")
        self.assertEqual(info.work_ratio("b4.prv", 2.0), 256.0)
        self.assertEqual(info.work_ratio("b4.prv", 2.0, "device"), 256.0)
        self.assertIn("host", info.domain_detection)
        self.assertEqual(info.domain_modes["host"],
                         info.domain_detection["host"].detected)
        self.assertEqual(info.domain_selection["host"],
                         "Automatic, Host measurements only")

    def test_scaling_option_forces_the_domain_without_workload(self):
        for scaling, ratio in (("strong", 1.0), ("weak", 2.0)):
            info = self._scaling_info(
                self._make_args(scaling=scaling, device_workload="1,4,16"),
                has_domains=True)

            self.assertEqual(info.domain_modes["host"], scaling)
            self.assertEqual(info.domain_selection["host"],
                             "Manual, --scaling")
            self.assertEqual(info.work_ratio("b16.prv", 2.0, "host"), ratio)
            self.assertEqual(info.work_ratio("b16.prv", 2.0, "device"), 16.0)

    def test_host_workload_alone(self):
        # The application and the Device use the detected scaling.
        info = self._scaling_info(
            self._make_args(host_workload="1,1,2"), has_domains=True)

        self.assertIn(info.selected, ("strong", "weak"))
        self.assertIsNone(info.workload_ratios)
        self.assertEqual(info.work_ratio("b16.prv", 3.0, "host"), 2.0)
        self.assertIn("device", info.domain_detection)

    def test_domain_workloads_are_ignored_without_domains(self):
        output = io.StringIO()
        with redirect_stdout(output):
            info = self._scaling_info(
                self._make_args(device_workload="1,4,16"))

        self.assertIn("--device-workload ignored", output.getvalue())
        self.assertIn(info.selected, ("strong", "weak"))
        self.assertEqual(info.domain_modes, {})

    def test_host_detection_uses_host_measures(self):
        # The application looks weak (runtime and useful time grow with the
        # device work), but the Host threads double with the same total
        # work: the Host detection says strong.
        trace_list = ["a.prv", "b.prv"]
        raw_data = {
            "runtime": {"a.prv": 100.0, "b.prv": 200.0},
            "useful_ins": {"a.prv": 1000.0, "b.prv": 1000.0},
            "count_host_threads": {"a.prv": 2, "b.prv": 4},
            "useful_host": {"a.prv": 40.0, "b.prv": 40.0},
            "count_devices": {"a.prv": 1, "b.prv": 1},
            "useful_device": {"a.prv": 50.0, "b.prv": 150.0},
        }

        self.assertEqual(
            detect_domain_scaling(raw_data, trace_list, "host").detected,
            "strong")
        self.assertEqual(
            detect_domain_scaling(raw_data, trace_list, "device").detected,
            "weak")

    def test_domain_workload_does_not_need_the_application_workload(self):
        args = self._make_args(host_workload="1,2")
        self.assertIsNone(build_workload_map(args, ["a.prv", "b.prv"]))
        self.assertIn("host", args.domain_workload_maps)

    def test_domain_workload_with_wrong_number_of_values_is_an_error(self):
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                build_workload_map(
                    self._make_args(workload="1,2", device_workload="1,2,3"),
                    ["a.prv", "b.prv"])

    def test_has_workload(self):
        self.assertFalse(has_workload(self._make_args()))
        self.assertTrue(has_workload(self._make_args(workload="1,2")))
        self.assertTrue(has_workload(self._make_args(device_workload="1,2")))

    def test_workload_table_shows_every_level(self):
        info = self._scaling_info(
            self._make_args(scaling="strong", device_workload="1,4,16"),
            has_domains=True)

        columns, rows = workload_table(info)

        self.assertEqual(columns, ["Application", "Host", "Device"])
        trace, cells = rows[2]
        self.assertEqual(trace, "b16.prv")
        self.assertEqual([cell[1] for cell in cells], [16.0, 1.0, 16.0])
        self.assertEqual(cells[1][2], "strong scaling (ratio 1)")
        self.assertEqual(cells[0][2], "--device-workload")

    def test_workload_table_shows_the_weak_resource_ratio(self):
        raw_data, trace_list, _ = self._data()
        raw_data["count_host_threads"] = {
            "b1.prv": 2, "b4.prv": 4, "b16.prv": 8}
        info = self._scaling_info(
            self._make_args(scaling="weak", device_workload="1,4,16"),
            has_domains=True)

        _columns, rows = workload_table(info, trace_list, raw_data)

        self.assertEqual(rows[2][1][1][1], 4.0)
        self.assertEqual(rows[2][1][1][2],
                         "weak scaling (ratio of Host threads)")

    def test_work_ratio_replaces_every_resource_ratio(self):
        info = self._scaling_info(self._make_args(workload="1,4,16"))

        for resource_ratio in (1.0, 2.0, 3.5):
            self.assertEqual(info.work_ratio("b4.prv", resource_ratio), 4.0)

    def test_work_ratio_without_workload(self):
        info = self._scaling_info(self._make_args(scaling="weak"))

        self.assertIsNone(info.workload_ratios)
        self.assertEqual(info.work_ratio("b4.prv", 2.5), 2.5)

        info = self._scaling_info(self._make_args(scaling="strong"))
        self.assertEqual(info.work_ratio("b4.prv", 2.5), 1.0)

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
        info = self._scaling_info(self._make_args(workload="1,4,16"))

        self.assertEqual(
            describe_scaling(info),
            ("User-defined workload", "Manual (--workload)"),
        )


if __name__ == "__main__":
    unittest.main()
