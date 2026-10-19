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
    print_io_tables,
)
from rawdata import parse_io_call_table


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
