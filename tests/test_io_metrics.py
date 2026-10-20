import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from iometrics import (
    NON_AVAIL,
    add_io_metrics,
    aggregate_io_calls,
    classify_call,
    compute_trace_io_metrics,
    io_useful_time,
    print_io_tables,
)
from rawdata import parse_io_call_table, parse_timings_stats


def _table(units, calls):
    return {'units': units, 'calls': calls}


def _io_data(posix_time=None, posix_count=None, mpiio_time=None,
             mpiio_count=None):
    return {
        'calls': {
            'posix': {'time': posix_time, 'count': posix_count},
            'mpiio': {'time': mpiio_time, 'count': mpiio_count},
        },
    }


UNITS = ['THREAD 1.1.1', 'THREAD 1.2.1']


class ClassificationTests(unittest.TestCase):

    def test_posix_and_ansi_c_calls(self):
        self.assertEqual(classify_call('posix', 'fread'), ('read', True))
        self.assertEqual(classify_call('posix', 'writev'), ('write', True))
        self.assertEqual(classify_call('posix', 'fopen'), ('open', True))
        self.assertEqual(classify_call('posix', 'fclose'), ('close', True))
        self.assertEqual(classify_call('posix', 'fseek'), ('seek', True))
        self.assertEqual(classify_call('posix', 'ioctl'), ('control', True))

    def test_mpiio_calls(self):
        self.assertEqual(
            classify_call('mpiio', 'MPI_File_read_at_all_begin'),
            ('read', True))
        self.assertEqual(
            classify_call('mpiio', 'MPI_File_write_shared'), ('write', True))
        self.assertEqual(classify_call('mpiio', 'MPI_File_open'),
                         ('open', True))
        self.assertEqual(classify_call('mpiio', 'MPI_File_close'),
                         ('close', True))

    def test_unknown_calls_are_file_management(self):
        self.assertEqual(classify_call('posix', 'fsync'), ('other', False))
        self.assertEqual(classify_call('mpiio', 'MPI_File_sync'),
                         ('other', False))


class CallTableParserTests(unittest.TestCase):

    def test_parses_per_unit_rows(self):
        content = (
            '\tread()\twrite()\topen()\t\n'
            'THREAD 1.1.1\t10.0\t\t5.0\t\n'
            'THREAD 1.2.1\t20.0\t3.0\t\t\n'
            '\n'
            'Total\t30.0\t3.0\t5.0\t\n'
            'Average\t15.0\t3.0\t5.0\t\n'
        )

        with tempfile.NamedTemporaryFile('w', suffix='.csv',
                                         delete=False) as handle:
            handle.write(content)
            path = handle.name

        try:
            table = parse_io_call_table(path)
        finally:
            os.remove(path)

        self.assertEqual(table['units'], UNITS)
        self.assertEqual(table['calls']['read'], [10.0, 20.0])
        self.assertEqual(table['calls']['write'], [0.0, 3.0])
        self.assertEqual(table['calls']['open'], [5.0, 0.0])


class AggregationTests(unittest.TestCase):

    def test_families_and_apis_are_added_per_unit(self):
        io_data = _io_data(
            posix_time=_table(UNITS, {
                'read': [10.0, 0.0],
                'fread': [5.0, 1.0],
                'fopen': [2.0, 2.0],
            }),
            mpiio_time=_table(['THREAD 1.2.1'], {
                'MPI_File_write_at': [8.0],
                'MPI_File_sync': [1.0],
            }),
        )

        aggregate = aggregate_io_calls(io_data)

        self.assertEqual(aggregate['units'], UNITS)
        self.assertEqual(aggregate['time']['read'], [15.0, 1.0])
        self.assertEqual(aggregate['time']['write'], [0.0, 8.0])
        self.assertEqual(aggregate['time']['open'], [2.0, 2.0])
        self.assertEqual(aggregate['time']['other'], [0.0, 1.0])
        self.assertEqual(aggregate['api_time']['mpiio'], [0.0, 9.0])
        self.assertEqual(aggregate['unknown'], [('mpiio', 'MPI_File_sync')])

    def test_raw_data_without_call_tables(self):
        self.assertIsNone(aggregate_io_calls({'operations': {}}))
        self.assertIsNone(aggregate_io_calls(_io_data()))


class MetricTests(unittest.TestCase):

    def setUp(self):
        # Unit 1 reads, unit 2 writes; both open files.
        self.io_data = _io_data(
            posix_time=_table(UNITS, {
                'read': [300.0, 0.0],
                'write': [0.0, 100.0],
                'open': [60.0, 20.0],
                'close': [10.0, 10.0],
            }),
            posix_count=_table(UNITS, {
                'read': [3.0, 0.0],
                'write': [0.0, 2.0],
                'open': [2.0, 2.0],
                'close': [2.0, 2.0],
            }),
        )

    def test_factors_multiply_to_io_efficiency(self):
        useful = 1600.0
        metrics, _ = compute_trace_io_metrics(useful, 1000.0, 2,
                                              self.io_data)

        da = 400.0
        fm = 100.0
        self.assertAlmostEqual(metrics['io_da_eff'],
                               useful / (useful + da) * 100.0)
        self.assertAlmostEqual(metrics['io_fm_eff'],
                               (useful + da) / (useful + da + fm) * 100.0)
        self.assertAlmostEqual(
            metrics['io_da_eff'] * metrics['io_fm_eff'] / 100.0,
            useful / (useful + da + fm) * 100.0)

    def test_diagnostics(self):
        metrics, _ = compute_trace_io_metrics(1600.0, 1000.0, 2,
                                              self.io_data)

        # Unit 1: 370 us of I/O, unit 2: 130 us.
        self.assertAlmostEqual(metrics['io_fraction_avg'], 25.0)
        self.assertAlmostEqual(metrics['io_fraction_max'], 37.0)
        self.assertAlmostEqual(metrics['io_participation'], 100.0)
        self.assertAlmostEqual(metrics['io_read_contribution'], 75.0)
        self.assertAlmostEqual(metrics['io_posix_contribution'], 100.0)
        self.assertAlmostEqual(metrics['io_mpiio_contribution'], 0.0)
        self.assertAlmostEqual(metrics['io_open_contribution'], 80.0)
        self.assertAlmostEqual(metrics['io_read_mean_duration'], 100.0)
        self.assertAlmostEqual(metrics['io_open_operations'], 4.0)
        self.assertAlmostEqual(metrics['io_read_time'], 300.0 / 1e6)
        self.assertEqual(metrics['io_seek_time'], NON_AVAIL)

    def test_critical_path_load_balance(self):
        useful = 1600.0
        metrics, _ = compute_trace_io_metrics(useful, 1000.0, 2,
                                              self.io_data)

        # Per unit: U_avg = 800, IO_avg = 250. Critical path: max read 300
        # + max write 100 + max open 60 + max close 10 = 470.
        self.assertAlmostEqual(metrics['io_lb'],
                               (800.0 + 250.0) / (800.0 + 470.0) * 100.0)
        self.assertAlmostEqual(metrics['io_cp_eff'],
                               800.0 / (800.0 + 470.0) * 100.0)
        io_eff = useful / (useful + 500.0) * 100.0
        self.assertAlmostEqual(
            metrics['io_cp_eff'], io_eff * metrics['io_lb'] / 100.0)

    def test_balanced_io_has_full_load_balance(self):
        io_data = _io_data(posix_time=_table(UNITS, {
            'read': [100.0, 100.0],
            'open': [20.0, 20.0],
        }))
        metrics, _ = compute_trace_io_metrics(1600.0, 1000.0, 2, io_data)

        self.assertAlmostEqual(metrics['io_lb'], 100.0)

    def test_load_balance_over_participants(self):
        metrics, _ = compute_trace_io_metrics(1600.0, 1000.0, 2,
                                              self.io_data)

        # Only one unit reads and only one writes: balanced among the
        # participants.
        self.assertAlmostEqual(metrics['io_read_load_balance'], 100.0)
        self.assertAlmostEqual(metrics['io_write_load_balance'], 100.0)
        # Data Access per unit: 300 and 100.
        self.assertAlmostEqual(metrics['io_da_load_balance'],
                               200.0 / 300.0 * 100.0)
        self.assertAlmostEqual(metrics['io_open_load_balance'],
                               40.0 / 60.0 * 100.0)

    def test_participation_with_units_without_io(self):
        metrics, _ = compute_trace_io_metrics(1600.0, 1000.0, 4,
                                              self.io_data)

        self.assertAlmostEqual(metrics['io_participation'], 50.0)
        self.assertAlmostEqual(metrics['io_fraction_avg'], 12.5)

    def test_no_io(self):
        metrics, _ = compute_trace_io_metrics(1600.0, 1000.0, 2, {})

        self.assertTrue(all(value == NON_AVAIL for value in metrics.values()))


class AddIoMetricsTests(unittest.TestCase):

    def _raw_data(self, io_tot):
        return {
            'useful_tot': {'t1': 1600.0},
            'runtime': {'t1': 1000.0},
            'io_tot': {'t1': io_tot},
            'mpiio_tot': {'t1': 0.0},
        }

    def _io_data(self):
        return {'t1': _io_data(
            posix_time=_table(UNITS, {
                'read': [300.0, 0.0],
                'fsync': [0.0, 100.0],
            }),
        )}

    def test_warns_about_unknown_calls(self):
        other_metrics = {'io_units': {'t1': 2}}

        output = io.StringIO()
        with redirect_stdout(output):
            add_io_metrics(other_metrics, self._raw_data(400.0),
                           self._io_data(), ['t1'])

        self.assertIn('fsync (POSIX/ANSI C)', output.getvalue())
        self.assertNotIn('differs by more than 1%', output.getvalue())
        self.assertAlmostEqual(other_metrics['io_other_contribution']['t1'],
                               100.0)

    def test_warns_when_call_time_differs_from_io_time(self):
        other_metrics = {'io_units': {'t1': 2}}

        output = io.StringIO()
        with redirect_stdout(output):
            add_io_metrics(other_metrics, self._raw_data(500.0),
                           self._io_data(), ['t1'])

        self.assertIn('differs by more than 1%', output.getvalue())


class IoUsefulTimeTests(unittest.TestCase):

    def test_cpu_trace_uses_total_useful_time(self):
        raw_data = {
            'useful_tot': {'t1': 1600.0},
            'useful_io_tot': {'t1': 1600.0},
        }
        self.assertEqual(io_useful_time(raw_data, 't1'), 1600.0)

    def test_falls_back_to_total_useful_time(self):
        raw_data = {
            'useful_tot': {'t1': 1600.0},
            'useful_io_tot': {'t1': 'NaN'},
        }
        self.assertEqual(io_useful_time(raw_data, 't1'), 1600.0)

    def test_gpu_trace_uses_host_useful_time(self):
        # useful_tot also holds the kernel time of the GPU streams.
        raw_data = {
            'useful_tot': {'t1': 2600.0},
            'useful_io_tot': {'t1': 1600.0},
        }
        self.assertEqual(io_useful_time(raw_data, 't1'), 1600.0)

    def test_timings_host_rows_exclude_gpu_streams(self):
        content = (
            '\tRunning\tI/O\t\n'
            'THREAD 1.1.1\t1000\t100\t\n'
            'CUDA-D1.S1-node1\t900\t\t\n'
            'THREAD 1.2.1\t600\t50\t\n'
            '\n'
            'Total\t2500\t150\t\n'
            'Average\t833.33\t75\t\n'
            'Maximum\t1000\t100\t\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'trace.timings.stats.csv')
            with open(path, 'w') as f:
                f.write(content)
            result = parse_timings_stats(path, has_pcf=True)

        self.assertEqual(result['useful_tot'], 2500.0)
        self.assertEqual(result['useful_io_tot'], 1600.0)

    def test_gpu_io_factors_exclude_stream_time(self):
        raw_data = {
            'useful_tot': {'t1': 2600.0},
            'useful_io_tot': {'t1': 1600.0},
            'runtime': {'t1': 1000.0},
            'io_tot': {'t1': 400.0},
            'mpiio_tot': {'t1': 0.0},
        }
        io_data = {'t1': _io_data(posix_time=_table(UNITS, {
            'read': [300.0, 0.0],
            'write': [0.0, 100.0],
        }))}
        other_metrics = {'io_units': {'t1': 2}}

        with redirect_stdout(io.StringIO()):
            add_io_metrics(other_metrics, raw_data, io_data, ['t1'])

        self.assertAlmostEqual(other_metrics['io_da_eff']['t1'], 80.0)


class PrintTests(unittest.TestCase):

    def test_hides_calls_not_used_by_any_trace(self):
        other_metrics = {'io_units': {'t1': 2}, 'io_eff': {'t1': 75.0}}
        raw_data = {
            'useful_tot': {'t1': 1600.0},
            'runtime': {'t1': 1000.0},
            'io_tot': {'t1': 300.0},
            'mpiio_tot': {'t1': 0.0},
        }
        io_data = {'t1': _io_data(
            posix_time=_table(UNITS, {'read': [300.0, 0.0]}),
        )}

        output = io.StringIO()
        with redirect_stdout(output):
            add_io_metrics(other_metrics, raw_data, io_data, ['t1'])
            print_io_tables(other_metrics, ['t1'], ['2[1]'], 10)

        text = output.getvalue()
        self.assertIn('I/O Critical-Path Efficiency (%)', text)
        self.assertIn('   -- Data Access Efficiency (%)', text)
        self.assertIn('-- I/O Load Balance (%)', text)
        self.assertIn('Read Load Balance (%)', text)
        self.assertNotIn('MPI-IO contribution', text)
        self.assertNotIn('Seek time', text)


if __name__ == '__main__':
    unittest.main()


class IoThresholdTests(unittest.TestCase):

    def test_io_efficiencies_use_stricter_thresholds(self):
        from interactiveplots import KNOWLEDGE_PROVIDER

        for key in ('io_eff', 'io_da_eff', 'io_fm_eff'):
            thresholds = KNOWLEDGE_PROVIDER.get(key).thresholds
            self.assertEqual(thresholds.critical, 90.0)
            self.assertEqual(thresholds.attention, 95.0)

        thresholds = KNOWLEDGE_PROVIDER.get('global_eff').thresholds
        self.assertEqual(thresholds.critical, 60.0)
        self.assertEqual(thresholds.attention, 85.0)

    def test_colors_follow_the_thresholds_of_the_metric(self):
        from interactiveplots import (
            KNOWLEDGE_PROVIDER,
            _efficiency_scale_position,
            _metric_value_color,
        )

        io = KNOWLEDGE_PROVIDER.get('io_eff').thresholds
        default = KNOWLEDGE_PROVIDER.get('global_eff').thresholds

        # The I/O thresholds fall on the positions of the default ones.
        self.assertAlmostEqual(_efficiency_scale_position(90.0, io), 60.0)
        self.assertAlmostEqual(_efficiency_scale_position(95.0, io), 85.0)
        self.assertEqual(_metric_value_color(90.0, io),
                         _metric_value_color(60.0, default))

        # The other metrics keep their colors.
        for value in (0.0, 30.0, 60.0, 72.5, 85.0, 99.0, 100.0):
            self.assertAlmostEqual(
                _efficiency_scale_position(value, default), value)
            self.assertEqual(_metric_value_color(value, default),
                             _metric_value_color(value))


class IoDiagnosticsReportTests(unittest.TestCase):

    def _other_metrics(self):
        other_metrics = {'io_units': {'t1': 2}, 'io_eff': {'t1': 75.0}}
        raw_data = {
            'useful_tot': {'t1': 1600.0},
            'runtime': {'t1': 1000.0},
            'io_tot': {'t1': 300.0},
            'mpiio_tot': {'t1': 0.0},
        }
        io_data = {'t1': _io_data(
            posix_time=_table(UNITS, {'read': [300.0, 0.0]}),
            posix_count=_table(UNITS, {'read': [3000.0, 0.0]}),
        )}
        with redirect_stdout(io.StringIO()):
            add_io_metrics(other_metrics, raw_data, io_data, ['t1'])
        return other_metrics

    def test_groups_without_efficiency_colors(self):
        from interactiveplots import _build_io_diagnostics_table_html

        table = _build_io_diagnostics_table_html(
            self._other_metrics(), ['t1'], ['2 [T1]'])

        self.assertIn("I/O time", table)
        self.assertIn("Data Access", table)
        self.assertIn("Operations", table)
        self.assertIn("Read mean duration (µs)", table)
        self.assertIn("<td>3,000</td>", table)
        self.assertIn("<td>100.00%</td>", table)
        # Diagnostics are not efficiencies.
        self.assertNotIn("metric-good", table)
        self.assertNotIn("metric-critical", table)
        self.assertNotIn("background:", table)

    def test_unused_calls_and_groups_are_omitted(self):
        from interactiveplots import _build_io_diagnostics_table_html

        table = _build_io_diagnostics_table_html(
            self._other_metrics(), ['t1'], ['2 [T1]'])

        self.assertNotIn("MPI-IO contribution", table)
        self.assertNotIn("Write time", table)
        # No File Management call has time: the whole group is omitted.
        self.assertNotIn("File Management Load Balance", table)

    def test_no_table_without_io(self):
        from interactiveplots import _build_io_diagnostics_card_html

        self.assertEqual(
            _build_io_diagnostics_card_html({}, ['t1'], ['2 [T1]']), "")


class MetricLabelTests(unittest.TestCase):

    def test_inner_hyphens_are_kept(self):
        from interactiveplots import _clean_metric_label

        self.assertEqual(_clean_metric_label("-- I/O Critical-Path Efficiency"),
                         "I/O Critical-Path Efficiency")
        self.assertEqual(_clean_metric_label("   == Device Load balance"),
                         "Device Load balance")


# Filtered trace: thread 1.1.1 and 1.2.1, times in ns.
REQUESTS_TRACE = (
    '#Paraver (20/10/2026 at 10:00):100000_ns:1(2):1:2(1:1,1:1),0\n'
    # read of 300 B, 2 us -> interval 9 [256, 512)
    '2:1:1:1:1:1000:40000004:1:40000011:300\n'
    '2:1:1:1:1:3000:40000004:0\n'
    # fwrite of 1 B, 1 us -> interval 1
    '2:1:1:1:1:4000:40000004:4:40000011:1\n'
    '2:1:1:1:1:5000:40000004:0\n'
    # open: not a request
    '2:1:1:1:1:6000:40000004:11\n'
    '2:1:1:1:1:7000:40000004:0\n'
    # write without size: not counted
    '2:2:1:2:1:1000:40000004:2\n'
    '2:2:1:2:1:2000:40000004:0\n'
    # unclosed fopen, then pread of 3 GiB (last interval), 4 us
    '2:2:1:2:1:3000:40000004:12\n'
    '2:2:1:2:1:4000:40000004:5:40000011:3221225472\n'
    '2:2:1:2:1:8000:40000004:0\n'
    '2:2:1:2:1:9000:40000004:0\n'
)


class RequestSizeTraceTests(unittest.TestCase):

    def _parse(self):
        from rawdata import parse_io_requests_trace

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'trace.io_requests.prv')
            with open(path, 'w') as f:
                f.write(REQUESTS_TRACE)
            return parse_io_requests_trace(path)

    def test_requests_per_power_of_two_interval(self):
        requests = self._parse()

        self.assertEqual(requests['read'][9],
                         {'count': 1.0, 'time': 2.0, 'bytes': 300.0})
        self.assertEqual(requests['write'][1],
                         {'count': 1.0, 'time': 1.0, 'bytes': 1.0})
        # The pread follows an unclosed fopen and goes to the last interval.
        self.assertEqual(requests['read'][32]['count'], 1.0)
        self.assertEqual(requests['read'][32]['time'], 4.0)
        # Calls without size and File Management calls are not requests.
        self.assertEqual(sorted(requests['read']), [9, 32])
        self.assertEqual(sorted(requests['write']), [1])

    def test_interval_index(self):
        from rawdata import request_size_interval

        self.assertEqual(request_size_interval(1), 1)
        self.assertEqual(request_size_interval(255), 8)
        self.assertEqual(request_size_interval(256), 9)
        self.assertEqual(request_size_interval(2 ** 40), 32)

    def test_bins(self):
        from rawdata import build_io_request_size_bins

        bins = build_io_request_size_bins(self._parse()['read'])

        self.assertEqual([(b['min'], b['max']) for b in bins],
                         [(256, 512), (2 ** 31, None)])


def _request_io_data():
    io_data = _io_data(
        posix_time=_table(UNITS, {
            'read': [10.0, 0.0],
            'fread': [0.0, 30.0],
            'write': [5.0, 5.0],
        }),
        posix_count=_table(UNITS, {
            'read': [3.0, 0.0],
            'fread': [0.0, 1.0],
            'write': [1.0, 1.0],
        }),
    )
    io_data['request_size'] = {
        'read': {'bins': [
            {'min': 8, 'max': 16, 'count': 3.0, 'time': 10.0, 'bytes': 30.0},
            {'min': 1024, 'max': 2048, 'count': 1.0, 'time': 30.0,
             'bytes': 1024.0},
        ]},
        'write': {'bins': []},
    }
    return io_data


class RequestSizeMetricTests(unittest.TestCase):

    def test_distribution_shares_and_labels(self):
        from iometrics import io_request_size_distribution

        distribution = io_request_size_distribution(_request_io_data())

        self.assertEqual(list(distribution), ['read'])
        small, large = distribution['read']
        self.assertEqual(small['label'], '8-16 B')
        self.assertEqual(large['label'], '1-2 KiB')
        self.assertAlmostEqual(small['count_pct'], 75.0)
        self.assertAlmostEqual(large['time_pct'], 75.0)

    def test_volume_mean_size_and_coverage(self):
        metrics, _ = compute_trace_io_metrics(
            1000.0, 1000.0, 2, _request_io_data())

        self.assertEqual(metrics['io_read_volume'], 1054.0)
        self.assertAlmostEqual(metrics['io_read_mean_request_size'], 263.5)
        # 4 requests with size, 4 POSIX/ANSI C read calls.
        self.assertAlmostEqual(metrics['io_read_size_coverage'], 100.0)
        self.assertEqual(metrics['io_write_volume'], NON_AVAIL)

    def test_interval_labels_and_bytes(self):
        from iometrics import format_bytes, request_size_interval_label

        self.assertEqual(request_size_interval_label(1, 2), '1 B')
        self.assertEqual(request_size_interval_label(512, 1024), '512-1024 B')
        self.assertEqual(request_size_interval_label(2 ** 20, 2 ** 21),
                         '1-2 MiB')
        self.assertEqual(request_size_interval_label(2 ** 31, None),
                         '>= 2 GiB')
        self.assertEqual(format_bytes(432.0), '432 B')
        self.assertEqual(format_bytes(1536.0), '1.50 KiB')

    def test_csv_and_report_table(self):
        from iometrics import print_io_request_sizes_csv
        from interactiveplots import _build_io_request_sizes_card_html

        other_metrics = {'io_units': {'t1': 2}}
        raw_data = {
            'useful_tot': {'t1': 1000.0},
            'runtime': {'t1': 1000.0},
            'io_tot': {'t1': 50.0},
            'mpiio_tot': {'t1': 0.0},
        }
        with redirect_stdout(io.StringIO()):
            add_io_metrics(other_metrics, raw_data,
                           {'t1': _request_io_data()}, ['t1'])

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                with redirect_stdout(io.StringIO()):
                    print_io_request_sizes_csv(other_metrics, ['t1'])
                with open('io_request_sizes.csv') as f:
                    lines = f.read().splitlines()
            finally:
                os.chdir(cwd)

        self.assertEqual(len(lines), 3)
        self.assertIn('"t1";"POSIX/ANSI C";"read";"8-16 B";8;16;3;',
                      lines[1])

        card = _build_io_request_sizes_card_html(
            other_metrics, ['t1'], ['2 [T1]'])
        self.assertIn('Read request size', card)
        self.assertIn('1–2 KiB', card)
        self.assertNotIn('Write request size', card)
