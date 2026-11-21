import os
import tempfile
import unittest

import gpuassessment
from gpuassessment import (
    classify_cuda_call,
    create_device_work_factors,
    create_host_calls_factors,
    has_metrics,
    host_call_group_times,
    parse_cuda_calls_by_name,
)


class FakeScaling(object):
    def __init__(self, mode, ratios=None):
        self._mode = mode
        self.ratios = ratios or {}

    def mode(self, domain=None):
        return self._mode

    def work_ratio(self, trace, resource_ratio, domain=None):
        if self._mode == 'workload':
            return self.ratios[trace]
        if self._mode == 'strong':
            return 1.0
        return resource_ratio


class ClassifyCudaCallTest(unittest.TestCase):

    def test_groups(self):
        cases = {
            'cudaLaunchKernel_v7000': 'launch',
            'cuLaunchKernelEx': 'launch',
            'cudaGraphLaunch_v10000': 'launch',
            'cudaDeviceSynchronize_v3020': 'sync',
            'cudaStreamSynchronize_v3020': 'sync',
            'cudaEventQuery_v3020': 'sync',
            'cudaMemcpyAsync_v3020': 'memory',
            'cudaMemsetAsync_v3020': 'memory',
            'cudaMalloc_v3020': 'memory',
            'cudaHostAlloc_v3020': 'memory',
            'cudaGraphInstantiateWithFlags_v11040': 'graph',
            'cudaStreamBeginCapture_v10000': 'graph',
            'cudaStreamIsCapturing_v10000': 'other',
            'cuKernelGetName': 'other',
            'cudaStreamWaitEvent_v3020': 'other',
        }
        for name, group in cases.items():
            self.assertEqual(classify_cuda_call(name), group, name)


class ParseCudaCallsTest(unittest.TestCase):

    def _write(self, text):
        handle, path = tempfile.mkstemp(suffix='.csv')
        with os.fdopen(handle, 'w') as out:
            out.write(text)
        self.addCleanup(os.remove, path)
        return path

    TABLE = (
        '\tcudaLaunchKernel_v7000\tcudaDeviceSynchronize_v3020\tcudaMalloc_v3020\t\n'
        'THREAD 1.1.1\t0.00\t2000.00\t0.00\t\n'
        'THREAD 1.2.1\t11000.00\t3000.00\t500.00\t\n'
        'CUDA-D0.S7\t0.00\t0.00\t0.00\t\n'
        '\n'
        'Total\t11000.00\t5000.00\t500.00\t\n'
    )

    def test_rows_matched_with_labels(self):
        labels = [('THREAD 1.1.1', 'THREAD 1.1.1'), ('THREAD 1.2.1', 'THREAD 1.2.1'),
                  ('THREAD 1.2.2', 'CUDA-D0.S7')]
        calls = parse_cuda_calls_by_name(self._write(self.TABLE), labels)
        self.assertEqual(calls['THREAD 1.2.1'],
                         {'cudaLaunchKernel_v7000': 11.0,
                          'cudaDeviceSynchronize_v3020': 3.0,
                          'cudaMalloc_v3020': 0.5})
        self.assertEqual(calls['THREAD 1.2.2'], {})

    def test_fallback_to_thread_rows(self):
        calls = parse_cuda_calls_by_name(self._write(self.TABLE), [])
        self.assertEqual(sorted(calls), ['THREAD 1.1.1', 'THREAD 1.2.1'])

    def test_missing_file(self):
        self.assertEqual(parse_cuda_calls_by_name('/nonexistent.csv', []), {})

    def test_group_times_of_host_units(self):
        labels = [('THREAD 1.1.1', 'THREAD 1.1.1'), ('THREAD 1.2.1', 'THREAD 1.2.1'),
                  ('THREAD 1.2.2', 'CUDA-D0.S7')]
        calls = parse_cuda_calls_by_name(self._write(self.TABLE), labels)
        groups = host_call_group_times(calls, ['THREAD 1.2.1'])
        self.assertEqual(list(groups), list(gpuassessment.CUDA_CALL_GROUPS))
        self.assertEqual(groups['launch'], 11.0)
        self.assertEqual(groups['sync'], 3.0)
        self.assertEqual(groups['memory'], 0.5)
        self.assertEqual(groups['other'], 0.0)


def _raw(traces):
    keys = ('count_devices', 'useful_device', 'hwc_tensor_active_int',
            'hwc_dram_read_unweighted_int', 'hwc_dram_write_unweighted_int',
            'runtime', 'host_calls_units') + tuple(
                'host_calls_' + g for g in gpuassessment.CUDA_CALL_GROUPS)
    raw = {key: {} for key in keys}
    for trace, values in traces.items():
        for key in keys:
            raw[key][trace] = values.get(key, 'Non-Avail')
    return raw


class DeviceWorkTest(unittest.TestCase):

    RAW = _raw({
        'b1': {'count_devices': 1, 'useful_device': 2.0e6,
               'hwc_tensor_active_int': 100.0,
               'hwc_dram_read_unweighted_int': 50.0,
               'hwc_dram_write_unweighted_int': 10.0},
        'b256': {'count_devices': 1, 'useful_device': 16.0e6,
                 'hwc_tensor_active_int': 12800.0,
                 'hwc_dram_read_unweighted_int': 400.0,
                 'hwc_dram_write_unweighted_int': 1280.0},
    })

    def test_workload_scaled(self):
        scaling = FakeScaling('workload', {'b1': 1.0, 'b256': 256.0})
        factors = create_device_work_factors(self.RAW, ['b1', 'b256'], scaling)
        self.assertEqual(list(factors), list(gpuassessment.mod_device_work_doc))
        self.assertAlmostEqual(factors['dev_kernel_time']['b256'], 16.0)
        self.assertAlmostEqual(factors['dev_comp_scale_unscaled']['b1'], 100.0)
        self.assertAlmostEqual(factors['dev_comp_scale_unscaled']['b256'], 12.5)
        # Tensor work grows 128x for a workload 256x: 200%.
        self.assertAlmostEqual(factors['dev_tensor_work_scale']['b256'], 200.0)
        self.assertAlmostEqual(factors['dev_dram_read_scale']['b256'], 3200.0)
        self.assertAlmostEqual(factors['dev_dram_write_scale']['b256'], 200.0)
        self.assertAlmostEqual(factors['dev_tensor_work_scale']['b1'], 100.0)

    def test_strong_scaling_has_no_unscaled_row(self):
        factors = create_device_work_factors(
            self.RAW, ['b1', 'b256'], FakeScaling('strong'))
        self.assertEqual(factors['dev_comp_scale_unscaled']['b256'], 'N/A')
        self.assertAlmostEqual(factors['dev_tensor_work_scale']['b256'], 100.0 / 128)

    def test_single_trace_only_kernel_time(self):
        factors = create_device_work_factors(
            self.RAW, ['b1'], FakeScaling('strong'))
        self.assertAlmostEqual(factors['dev_kernel_time']['b1'], 2.0)
        self.assertEqual(factors['dev_tensor_work_scale']['b1'], 'Non-Avail')

    def test_without_counters_or_devices(self):
        raw = _raw({
            'a': {'count_devices': 1, 'useful_device': 1.0e6},
            'b': {'count_devices': 1, 'useful_device': 2.0e6},
            'cpu': {'count_devices': 0, 'useful_device': 0.0},
        })
        factors = create_device_work_factors(
            raw, ['a', 'b', 'cpu'], FakeScaling('weak'))
        self.assertEqual(factors['dev_tensor_work_scale']['b'], 'Non-Avail')
        self.assertEqual(factors['dev_kernel_time']['cpu'], 'Non-Avail')
        self.assertAlmostEqual(factors['dev_comp_scale_unscaled']['b'], 50.0)

    def test_extrae_cpu_traces_have_no_metrics(self):
        raw = _raw({'p4': {'count_devices': 0}, 'p8': {'count_devices': 0}})
        factors = create_device_work_factors(
            raw, ['p4', 'p8'], FakeScaling('strong'))
        self.assertFalse(has_metrics(factors, ['p4', 'p8']))


class HostCallsTest(unittest.TestCase):

    def test_split_adds_to_100(self):
        raw = _raw({'t': {'runtime': 1000.0, 'host_calls_units': 2,
                          'host_calls_launch': 200.0, 'host_calls_sync': 100.0,
                          'host_calls_memory': 50.0, 'host_calls_graph': 0.0,
                          'host_calls_other': 50.0}})
        factors = create_host_calls_factors(raw, ['t'])
        self.assertAlmostEqual(factors['host_time_launch']['t'], 10.0)
        self.assertAlmostEqual(factors['host_time_sync']['t'], 5.0)
        self.assertAlmostEqual(factors['host_time_framework']['t'], 80.0)
        self.assertAlmostEqual(
            sum(factors[k]['t'] for k in gpuassessment.mod_host_calls_doc), 100.0)
        self.assertTrue(has_metrics(factors, ['t']))

    def test_traces_without_split(self):
        raw = _raw({'extrae': {'runtime': 1000.0}})
        factors = create_host_calls_factors(raw, ['extrae'])
        self.assertEqual(factors['host_time_framework']['extrae'], 'Non-Avail')
        self.assertFalse(has_metrics(factors, ['extrae']))


class FormatTest(unittest.TestCase):

    def test_format(self):
        self.assertEqual(gpuassessment.format_value('dev_kernel_time', 6.6671), '6.667')
        self.assertEqual(gpuassessment.format_value('host_time_launch', 11.284), '11.28%')
        self.assertEqual(gpuassessment.format_value('host_time_launch', 'Non-Avail'),
                         'Non-Avail')


if __name__ == '__main__':
    unittest.main()
