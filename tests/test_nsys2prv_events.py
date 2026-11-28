import os
import tempfile
import unittest

import nsys2prvevents as ev
from nsys2prvmetrics import init_nsys2prv_cfgs, write_trace_cfgs
from tracemetadata import is_nsys2prv_pcf


def pcf_text(types, memcpy_values=None):
    """A minimal nsys2prv .pcf with the given (code, label) event types."""
    blocks = ['DEFAULT_OPTIONS\n']
    for code, label in types:
        block = 'EVENT_TYPE\n0   {} {}\n'.format(code, label)
        if memcpy_values is not None and 'memcpy' in label.lower():
            block += 'VALUES\n0   End\n' + ''.join(
                '{}   {}\n'.format(value, value_label)
                for value, value_label in memcpy_values)
        blocks.append(block)
    return '\n'.join(blocks)


CURRENT_TYPES = [
    (63000000, 'CUDA library call'),
    (63000006, 'CUDA kernel execution'),
    (63000001, 'CUDA memcpy kernel'),
    (63000007, 'NCCL kernel'),
    (9400, 'GPC Clock Frequency [MHz]'),
    (9402, 'GR Active [Throughput %]'),
]

MEMCPY_VALUES = [
    (3, 'CUDA memcpy Device-to-Device'),
    (4, 'CUDA memcpy Device-to-Host'),
    (5, 'CUDA memcpy Host-to-Device'),
    (6, 'CUDA memset'),
]


class _PcfTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w') as out:
            out.write(text)
        return path


class ResolveEventsTests(_PcfTestCase):

    def test_current_labels(self):
        pcf = self.write('t.pcf', pcf_text(CURRENT_TYPES))
        found = ev.resolve_events(pcf)
        self.assertEqual(found['kernel'], (63000006, 'CUDA kernel execution', 'label'))
        self.assertEqual(found['memcpy'].code, 63000001)
        self.assertEqual(found['cuda_calls'].code, 63000000)
        self.assertEqual(found['gr_active'].code, 9402)
        self.assertIsNone(found['sms_active'].code)

    def test_known_label_with_a_new_code(self):
        pcf = self.write('t.pcf', pcf_text([(63000099, 'CUDA kernel'),
                                            (9452, 'GR Active [Throughput %]')]))
        found = ev.resolve_events(pcf)
        self.assertEqual(found['kernel'], (63000099, 'CUDA kernel', 'label'))
        self.assertEqual(found['gr_active'].code, 9452)

    def test_label_pattern(self):
        pcf = self.write('t.pcf', pcf_text([(63000011, 'CUDA memcpy operation'),
                                            (64000006, 'HIP kernel')]))
        found = ev.resolve_events(pcf)
        self.assertEqual(found['memcpy'], (63000011, 'CUDA memcpy operation',
                                           'label pattern'))
        self.assertEqual(found['kernel'].code, 64000006)

    def test_reference_code_when_only_the_label_changed(self):
        pcf = self.write('t.pcf', pcf_text([(63000006, 'GPU work item')]))
        found = ev.resolve_events(pcf)
        self.assertEqual(found['kernel'], (63000006, 'GPU work item',
                                           'reference code'))

    def test_reference_code_with_the_label_of_another_event(self):
        # 63000006 now holds the memory copies: it is not the kernel event.
        pcf = self.write('t.pcf', pcf_text([(63000006, 'CUDA memcpy kernel')]))
        found = ev.resolve_events(pcf)
        self.assertIsNone(found['kernel'].code)
        self.assertEqual(found['memcpy'].code, 63000006)

    def test_counters_are_not_found_by_code(self):
        pcf = self.write('t.pcf', pcf_text([(9402, 'NVLink RX [Throughput %]')]))
        self.assertIsNone(ev.resolve_events(pcf)['gr_active'].code)

    def test_counters_without_unit_in_the_label(self):
        # Metric set of Jesus's ring traces (FOA): names without the unit,
        # "SM Active" instead of "SMs Active", other codes.
        pcf = self.write('t.pcf', pcf_text([
            (9402, 'NVLink TX Responses User Data'),
            (9409, 'GPC Clock Frequency'),
            (9410, 'SYS Clock Frequency'),
            (9411, 'GR Active'),
            (9412, 'SM Active'),
            (9413, 'SM Issue'),
            (9414, 'Tensor Active'),
            (9417, 'Compute Warps in Flight'),
            (9418, 'Unallocated Warps in Active SMs'),
            (9419, 'DRAM Read Bandwidth'),
            (9420, 'DRAM Write Bandwidth'),
        ]))
        found = ev.resolve_events(pcf)
        expected = {'gpc_clock': 9409, 'gr_active': 9411, 'sms_active': 9412,
                    'sm_issue': 9413, 'tensor_active': 9414,
                    'warps_in_flight': 9417, 'unallocated_warps': 9418,
                    'dram_read': 9419, 'dram_write': 9420}
        for name, code in expected.items():
            self.assertEqual(found[name].code, code, name)
            self.assertEqual(found[name].how, 'label pattern', name)

    def test_counter_patterns_take_only_the_whole_name(self):
        pcf = self.write('t.pcf', pcf_text([
            (9410, 'SYS Clock Frequency'),
            (9420, 'GR Active Cycles'),
            (9430, 'DRAM Read Bandwidth Peak'),
            (9440, 'Tensor Active [%]'),
        ]))
        found = ev.resolve_events(pcf)
        self.assertIsNone(found['gpc_clock'].code)
        self.assertIsNone(found['gr_active'].code)
        self.assertIsNone(found['dram_read'].code)
        self.assertEqual(found['tensor_active'].code, 9440)

    def test_new_code_and_new_label_is_not_found(self):
        pcf = self.write('t.pcf', pcf_text([(63000099, 'GPU kernel exec')]))
        self.assertEqual(ev.resolve_events(pcf)['kernel'].how, 'not found')

    def test_event_map_by_code_and_by_label(self):
        pcf = self.write('t.pcf', pcf_text([(63000099, 'GPU kernel exec'),
                                            (9777, 'Graphics Active')]))
        found = ev.resolve_events(pcf, {'kernel': 63000099,
                                        'gr_active': 'graphics active'})
        self.assertEqual(found['kernel'], (63000099, 'GPU kernel exec', 'event map'))
        self.assertEqual(found['gr_active'].code, 9777)

    def test_shared_code_is_reported(self):
        pcf = self.write('t.pcf', pcf_text([(63000007, 'NCCL kernel'),
                                            (63000007, 'Eth: Bytes received')]))
        self.assertEqual(ev.ambiguous_codes(pcf, ev.resolve_events(pcf)), [63000007])


class EventMapFileTests(_PcfTestCase):

    def test_read(self):
        path = self.write('map.txt', '# comment\nkernel = 63000009\n'
                                     'memcpy = "CUDA memcpy kernel"  # copies\n')
        self.assertEqual(dict(ev.read_event_map(path)),
                         {'kernel': 63000009, 'memcpy': 'CUDA memcpy kernel'})

    def test_unknown_name(self):
        path = self.write('map.txt', 'kernels = 1\n')
        with self.assertRaisesRegex(ValueError, 'map.txt:1: unknown event'):
            ev.read_event_map(path)

    def test_malformed_line(self):
        path = self.write('map.txt', 'kernel 1\n')
        with self.assertRaisesRegex(ValueError, 'map.txt:1'):
            ev.read_event_map(path)


class MemoryValuesTests(unittest.TestCase):

    def test_values_by_label(self):
        values, how = ev.resolve_memory_values({
            0: 'End', 7: 'CUDA memset', 8: 'CUDA memcpy Host-to-Device',
            9: 'CUDA memcpy Device-to-Host', 10: 'CUDA memcpy Peer-to-Peer'})
        self.assertEqual(dict(values), {'d2d': 10, 'd2h': 9, 'h2d': 8, 'memset': 7})
        self.assertEqual(how, 'value labels')

    def test_without_value_labels(self):
        values, how = ev.resolve_memory_values({})
        self.assertEqual(tuple(values.values()), (3, 4, 5, 6))
        self.assertEqual(how, 'reference values')


class RewriteCfgTests(_PcfTestCase):

    CFG = ('window_filter_module evt_type 1 9400\n'
           'window_filter_module evt_type_label 1 "GPC Clock Frequency [MHz]"\n'
           'window_filter_module evt_type 2 63000006 9600\n'
           'window_filter_module evt_value 1 0.000000000000\n'
           'window_filter_module evt_value_label 1 "End"\n')

    def test_codes_replaced_and_type_labels_removed(self):
        out = ev.rewrite_cfg(self.CFG, {9400: 9410, 63000006: 63000099})
        self.assertEqual(out, 'window_filter_module evt_type 1 9410\n'
                              'window_filter_module evt_type 2 63000099 9600\n'
                              'window_filter_module evt_value 1 0.000000000000\n'
                              'window_filter_module evt_value_label 1 "End"\n')
        self.assertEqual(ev.cfg_reference_codes(self.CFG), {9400, 63000006, 9600})

    def test_translation_with_a_reference_pcf(self):
        reference = self.write('ref.pcf', pcf_text(
            CURRENT_TYPES + [(9600, 'NVTX Default domain default category')]))
        target = self.write('new.pcf', pcf_text([
            (63100006, 'CUDA kernel execution'),
            (9900, 'NVTX Default domain default category')]))
        table, missing = ev.translation_table(target, reference,
                                              cfg_codes={63000006, 9600, 9400})
        self.assertEqual(table[63000006], 63100006)
        self.assertEqual(table[9600], 9900)
        self.assertEqual(missing, [9400])

    def test_trace_cfgs_skip_events_not_found(self):
        cfgs = init_nsys2prv_cfgs(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cfgs'))
        codes = {63000006: 63000099, 63000001: 63000011, 63000007: None,
                 63000000: 63000000}
        written, missing = write_trace_cfgs(
            cfgs, ('kernels_streams', 'memcpy_streams', 'nccl_streams'),
            codes, os.path.join(self.tmp.name, 'cfgs'))
        self.assertEqual(missing, ['nccl_streams'])
        with open(written['kernels_streams']) as cfg:
            self.assertIn('window_filter_module evt_type 1 63000099', cfg.read())


class DetectionTests(_PcfTestCase):

    def test_renamed_events_are_still_detected(self):
        pcf = self.write('t.pcf', pcf_text([(63000011, 'CUDA memcpy operation')]))
        self.assertTrue(is_nsys2prv_pcf(pcf))

    def test_extrae_pcf_with_states_is_not_detected(self):
        pcf = self.write('t.pcf', 'STATES\n0   Idle\n\n' +
                         pcf_text([(63000001, 'CUDA memcpy kernel')]))
        self.assertFalse(is_nsys2prv_pcf(pcf))


if __name__ == '__main__':
    unittest.main()
