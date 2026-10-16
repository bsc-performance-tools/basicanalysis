import contextlib
import io
import os
import tempfile
import unittest

from nsys2prvmetrics import (
    HWC_KEYS,
    compute_device_hwc_factors,
    create_device_hwc_factors,
    hwc_raw_data_doc,
    init_nsys2prv_cfgs,
    mod_device_hwc_factors_doc,
    parse_nsys2prv_hwc_integral,
)
from rawdata import create_raw_data, merge_trace_results, print_raw_data_csv


# Integrals (value x ns) of the vLLM b1 trace (Jesus's nsys2prv traces),
# computed with the hwc cfgs and checked against the .prv events.
B1_INTEGRALS = {
    'gr_active': 810115606573.0,
    'sms_active': 376165746411.0,
    'sm_issue': 20711797914.0,
    'tensor_active': 18640608063.0,
    'warps_in_flight': 56296122509.0,
    'unallocated_warps': 320784319318.0,
    'dram_read': 43845990694445.0,
    'dram_write': 1253583392686.0,
    'gpc_clock': 1543387258012957147136.0,
}
B1_RUNTIME_US = 53664645.850


def _raw_data(trace, integrals, runtime=B1_RUNTIME_US, devices=1):
    raw_data = {'runtime': {trace: runtime}, 'hwc_devices': {trace: devices}}
    for key, value in integrals.items():
        raw_data['hwc_' + key + '_int'] = {trace: value}
    return raw_data


class HwcIntegralParserTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write(self, rows):
        path = os.path.join(self._tmpdir.name, 'hwc.stats.csv')
        with open(path, 'w') as f:
            f.write('\t1\t\n')
            for label, value in rows:
                f.write('{}\t{}\t\n'.format(label, value))
            f.write('\nNum. Cells\t1.00\t\nTotal\t0\t\n')
        return path

    def test_single_device(self):
        path = self._write([
            ('THREAD 1.1.1', '0.00'),
            ('CUDA-D0.S7', '0.00'),
            ('Metrics GPU0', '810115606573.00'),
        ])
        self.assertEqual(parse_nsys2prv_hwc_integral(path), (810115606573.0, 1))

    def test_devices_are_added(self):
        path = self._write([
            ('Metrics GPU0', '100.00'),
            ('CUDA-D1.S7', '0.00'),
            ('Metrics GPU1', '50.00'),
        ])
        self.assertEqual(parse_nsys2prv_hwc_integral(path), (150.0, 2))

    def test_without_metrics_threads(self):
        path = self._write([('THREAD 1.1.1', '0.00')])
        self.assertIsNone(parse_nsys2prv_hwc_integral(path))

    def test_missing_file(self):
        self.assertIsNone(parse_nsys2prv_hwc_integral(
            os.path.join(self._tmpdir.name, 'missing.csv')))
        self.assertIsNone(parse_nsys2prv_hwc_integral(None))

    def test_one_cfg_per_counter(self):
        root = os.path.join(os.path.dirname(__file__), '..', 'cfgs')
        cfgs = init_nsys2prv_cfgs(root)
        for key in HWC_KEYS:
            self.assertTrue(os.path.exists(cfgs['hwc_' + key]), key)


class HwcFactorsTests(unittest.TestCase):

    def test_b1_values(self):
        factors = compute_device_hwc_factors(_raw_data('b1', B1_INTEGRALS), 'b1')

        expected = {
            'dev_hwc_gpu_active': 15.10,
            'dev_hwc_sm_utilization': 2.56,
            'dev_hwc_sm_coverage': 46.43,
            'dev_hwc_sm_issue_eff': 5.51,
            'dev_hwc_warp_occupancy': 14.97,
            'dev_hwc_tensor_activity': 2.30,
            'dev_hwc_dram_read': 54.12,
            'dev_hwc_dram_write': 1.55,
            'dev_hwc_gpc_clock': 1905.14,
        }
        self.assertEqual(list(factors), list(mod_device_hwc_factors_doc))
        for key, value in expected.items():
            self.assertAlmostEqual(factors[key], value, places=2, msg=key)

    def test_sm_utilization_is_coverage_times_issue(self):
        factors = compute_device_hwc_factors(_raw_data('b1', B1_INTEGRALS), 'b1')
        self.assertAlmostEqual(
            factors['dev_hwc_sm_utilization'],
            factors['dev_hwc_sm_coverage'] * factors['dev_hwc_sm_issue_eff'] / 100.0)

    def test_gpu_active_divides_by_devices(self):
        integrals = dict(B1_INTEGRALS, gr_active=2 * B1_INTEGRALS['gr_active'])
        factors = compute_device_hwc_factors(
            _raw_data('t', integrals, devices=2), 't')
        self.assertAlmostEqual(factors['dev_hwc_gpu_active'], 15.10, places=2)

    def test_clock_already_in_mhz(self):
        integrals = dict(B1_INTEGRALS)
        integrals['gpc_clock'] = 1905.0 * B1_INTEGRALS['gr_active']
        factors = compute_device_hwc_factors(_raw_data('t', integrals), 't')
        self.assertAlmostEqual(factors['dev_hwc_gpc_clock'], 1905.0)

    def test_without_counters(self):
        raw_data = {'runtime': {'t': 10.0}}
        factors = compute_device_hwc_factors(raw_data, 't')
        self.assertTrue(all(value == 'Non-Avail' for value in factors.values()))

    def test_idle_gpu(self):
        integrals = {key: 0.0 for key in HWC_KEYS}
        factors = compute_device_hwc_factors(_raw_data('t', integrals), 't')
        self.assertEqual(factors['dev_hwc_gpu_active'], 0.0)
        self.assertEqual(factors['dev_hwc_sm_utilization'], 'NaN')
        self.assertEqual(factors['dev_hwc_gpc_clock'], 'NaN')

    def test_create_for_trace_list(self):
        raw_data = _raw_data('b1', B1_INTEGRALS)
        for key in raw_data:
            raw_data[key]['extrae'] = 'Non-Avail'
        factors = create_device_hwc_factors(raw_data, ['b1', 'extrae'])
        self.assertAlmostEqual(factors['dev_hwc_sm_coverage']['b1'], 46.43, places=2)
        self.assertEqual(factors['dev_hwc_sm_coverage']['extrae'], 'Non-Avail')


class HwcRawDataTests(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmpdir.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmpdir.cleanup()

    def _rawdata_csv(self, raw_data, trace_list):
        with contextlib.redirect_stdout(io.StringIO()):
            print_raw_data_csv(raw_data, trace_list, {t: 1 for t in trace_list})
        with open('rawdata.csv') as f:
            return f.read()

    def test_rawdata_csv_without_counters_is_unchanged(self):
        raw_data = create_raw_data(['t'])
        content = self._rawdata_csv(raw_data, ['t'])
        for label in hwc_raw_data_doc.values():
            self.assertNotIn(label, content)

    def test_rawdata_csv_with_counters(self):
        raw_data = create_raw_data(['t', 'u'])
        raw_data['hwc_devices']['t'] = 1
        for key in HWC_KEYS:
            raw_data['hwc_' + key + '_int']['t'] = B1_INTEGRALS[key]
        content = self._rawdata_csv(raw_data, ['t', 'u'])
        for label in hwc_raw_data_doc.values():
            self.assertIn(label, content)
        self.assertIn('#GPUs with sampled hardware counters;1.00;Non-Avail', content)

    def test_merge_results_saved_without_counters(self):
        from rawdata import raw_data_doc
        result = {
            'trace': 't',
            'raw_data': {key: 0.0 for key in raw_data_doc},
            'io_data': {},
            'mpi_proc_count': None,
        }
        raw_data, _io, _mpi = merge_trace_results([result], ['t'])
        for key in hwc_raw_data_doc:
            self.assertEqual(raw_data[key]['t'], 'Non-Avail')


class HwcOutputTests(unittest.TestCase):

    def setUp(self):
        raw_data = _raw_data('b1', B1_INTEGRALS)
        for key in raw_data:
            raw_data[key]['extrae'] = 'Non-Avail'
        self.factors = create_device_hwc_factors(raw_data, ['b1', 'extrae'])

    def test_has_metrics(self):
        from hybridmetrics import has_device_hwc_metrics
        self.assertTrue(has_device_hwc_metrics(self.factors, ['b1', 'extrae']))
        self.assertFalse(has_device_hwc_metrics(self.factors, ['extrae']))
        self.assertFalse(has_device_hwc_metrics(None, ['b1']))

    def test_value_format(self):
        from hybridmetrics import format_device_hwc_value
        self.assertEqual(format_device_hwc_value('dev_hwc_gpc_clock', 1905.14), '1905')
        self.assertEqual(format_device_hwc_value('dev_hwc_sm_coverage', 46.4336), '46.43%')
        self.assertEqual(format_device_hwc_value('dev_hwc_sm_coverage', 'Non-Avail'), 'Non-Avail')
        self.assertEqual(format_device_hwc_value('dev_hwc_sm_coverage', float('nan')), 'NaN')

    def test_report_view(self):
        from interactiveplots import _build_device_hwc_section, _has_device_hwc_metrics
        metrics_result = {'device_hwc_factors': self.factors}
        self.assertTrue(_has_device_hwc_metrics(metrics_result, ['b1']))
        self.assertFalse(_has_device_hwc_metrics(metrics_result, ['extrae']))
        self.assertFalse(_has_device_hwc_metrics({}, ['b1']))

        html = _build_device_hwc_section(
            metrics_result, ['b1'], ['T1'], trace_header_note='')
        self.assertIn('SM Utilization', html)
        self.assertIn('1905 MHz', html)
        self.assertIn('46.43%', html)

    def test_report_indicator_details(self):
        import json
        import re
        from interactiveplots import _build_device_hwc_section
        html = _build_device_hwc_section(
            {'device_hwc_factors': self.factors}, ['b1'], ['T1'],
            trace_header_note='')

        # Indicator values open the Metric Details of the view.
        self.assertIn(
            "selectMetricCell(this, 'device-hwc', 'dev_hwc_gpc_clock'", html)

        info = json.loads(re.search(
            r'window\["metricInfo_device-hwc"\] = (\{.*?\});\n', html).group(1))
        self.assertTrue(info['dev_hwc_gpc_clock']['indicator'])
        self.assertEqual(info['dev_hwc_gpc_clock']['unit'], 'MHz')
        self.assertEqual(info['dev_hwc_dram_read']['unit'], '%')
        self.assertTrue(info['dev_hwc_dram_read']['action'])
        self.assertIn('SM Issue Efficiency', info['dev_hwc_dram_read']['reading'])
        self.assertIn('Diagnostic patterns', html)
        self.assertIn('memory-bound', html)
        # The SM chain keeps the efficiency interpretation.
        self.assertNotIn('indicator', info['dev_hwc_sm_utilization'])


if __name__ == '__main__':
    unittest.main()
