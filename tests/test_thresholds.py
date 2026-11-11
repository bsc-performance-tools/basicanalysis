import argparse
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

import interactiveplots as ip
import utils
from metrics import (
    MetricThresholds,
    SCALE_ANCHORS,
    efficiency_scale_position,
    get_default_provider,
    parse_thresholds,
)


class TestParseThresholds(unittest.TestCase):

    def test_valid(self):
        t = parse_thresholds("50, 80")
        self.assertEqual((t.critical, t.attention, t.reference), (50.0, 80.0, 100.0))

    def test_invalid(self):
        for text in ("50", "80,50", "0,50", "50,101", "a,b", "50,80,90"):
            with self.assertRaises(ValueError, msg=text):
                parse_thresholds(text)

    def test_parser_option(self):
        parser = utils.build_argument_parser()
        args = parser.parse_args(["--thresholds", "40,70", "t.prv"])
        self.assertEqual(args.thresholds.critical, 40.0)
        self.assertIsNone(parser.parse_args(["t.prv"]).thresholds)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--thresholds", "70,40", "t.prv"])


class TestScalePosition(unittest.TestCase):

    def test_default_is_identity(self):
        for value in (0.0, 12.5, 60.0, 72.0, 85.0, 99.0, 100.0, 130.0):
            self.assertAlmostEqual(
                efficiency_scale_position(value, MetricThresholds()), value)

    def test_custom_thresholds_fall_on_anchors(self):
        t = MetricThresholds(critical=50.0, attention=80.0)
        self.assertAlmostEqual(efficiency_scale_position(50.0, t), SCALE_ANCHORS.critical)
        self.assertAlmostEqual(efficiency_scale_position(80.0, t), SCALE_ANCHORS.attention)
        self.assertAlmostEqual(efficiency_scale_position(100.0, t), 100.0)
        self.assertAlmostEqual(efficiency_scale_position(25.0, t), 30.0)
        self.assertAlmostEqual(efficiency_scale_position(65.0, t), 72.5)

    def test_attention_equal_to_reference(self):
        t = MetricThresholds(critical=50.0, attention=100.0)
        self.assertAlmostEqual(efficiency_scale_position(100.0, t), 100.0)


class TestThresholdOverride(unittest.TestCase):

    def setUp(self):
        self.provider = get_default_provider()

    def tearDown(self):
        self.provider.set_threshold_override(None)

    def test_override_applies_to_every_metric(self):
        args = argparse.Namespace(thresholds=MetricThresholds(critical=40.0, attention=70.0))
        with redirect_stdout(io.StringIO()) as out:
            utils.apply_efficiency_thresholds(args)
        self.assertIn("Critical below 40%", out.getvalue())
        for metric in ("parallel_eff", "io_eff"):
            t = self.provider.get(metric).thresholds
            self.assertEqual((t.critical, t.attention), (40.0, 70.0))
        self.assertEqual(self.provider.default_thresholds.critical, 40.0)

        self.provider.set_threshold_override(None)
        t = self.provider.get("parallel_eff").thresholds
        self.assertEqual((t.critical, t.attention), (60.0, 85.0))

    def test_no_option_keeps_defaults(self):
        utils.apply_efficiency_thresholds(argparse.Namespace(thresholds=None))
        self.assertIsNone(self.provider.threshold_override)

    def test_cell_colors_follow_override(self):
        default_color = ip._metric_value_color(70.0)
        self.provider.set_threshold_override(MetricThresholds(critical=50.0, attention=70.0))
        # 70 % is now on the Good threshold, the color of 85 % by default.
        self.provider.set_threshold_override(None)
        good_color = ip._metric_value_color(85.0)
        self.provider.set_threshold_override(MetricThresholds(critical=50.0, attention=70.0))
        self.assertEqual(ip._metric_value_color(70.0), good_color)
        self.assertNotEqual(ip._metric_value_color(70.0), default_color)
        self.assertEqual(ip._metric_value_class(65.0), "metric-warning")
        self.assertEqual(ip._metric_value_class(45.0), "metric-critical")

    def test_scale_panel(self):
        html = ip._build_efficiency_scale_html()
        self.assertIn('data-critical="60"', html)
        self.assertIn('data-threshold-input="critical"', html)
        self.assertIn("data-threshold-reset", html)
        self.assertNotIn("--thresholds when", html)
        # Two-handle slider: two range inputs, bands and value bubbles.
        self.assertEqual(html.count('type="range"'), 2)
        self.assertNotIn('type="number"', html)
        self.assertIn('data-threshold-band="attention"', html)
        self.assertIn('style="width: 25%;"', html)
        self.assertIn('data-threshold-bubble="critical"', html)
        self.assertIn('aria-valuetext="Good from 85%"', html)

        self.provider.set_threshold_override(MetricThresholds(critical=50.0, attention=80.0))
        html = ip._build_efficiency_scale_html()
        self.assertIn('data-critical="50"', html)
        self.assertIn('value="80"', html)
        self.assertIn("&lt; 50%", html)
        self.assertIn("Thresholds set with --thresholds", html)


class TestReportMarkup(unittest.TestCase):

    def test_cell_attributes(self):
        attrs = ip._threshold_data_attrs(72.5)
        self.assertIn("data-value='72.5000000000'", attrs)
        self.assertIn("data-critical='60'", attrs)
        self.assertIn("data-attention='85'", attrs)
        self.assertIn("data-reference='100'", attrs)
        self.assertEqual(ip._threshold_data_attrs(None), "")

    def test_script(self):
        script = ip._threshold_script()
        self.assertNotIn("__SCALE__", script)
        self.assertNotIn("__ANCHORS__", script)
        self.assertIn('"#b2182b"', script)
        self.assertIn("window.effectiveThresholds", script)
        # The thresholds are kept per report view; the printable report
        # keeps the thresholds of the report.
        self.assertIn("data-guided-view-id", script)
        self.assertIn("data-basicanalysis-printable-report", script)


if __name__ == "__main__":
    unittest.main()
