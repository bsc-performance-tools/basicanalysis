import unittest

from configuration import add_plot_trace_ids, disambiguate_configuration_labels


class PlotTraceIdTests(unittest.TestCase):

    def test_every_column_has_report_trace_id(self):
        self.assertEqual(
            add_plot_trace_ids(['64 (8x8)', '128 (16x8)']),
            ['64 (8x8) [T1]', '128 (16x8) [T2]'])

    def test_replaces_duplicate_suffix(self):
        labels = disambiguate_configuration_labels(
            ['5 (1x4) [1D]', '5 (1x4) [1D]'], trace_ids=[1, 2])
        self.assertEqual(
            add_plot_trace_ids(labels),
            ['5 (1x4) [1D] [T1]', '5 (1x4) [1D] [T2]'])

    def test_keeps_device_count(self):
        self.assertEqual(add_plot_trace_ids(['4 (2x2) [1D]']),
                         ['4 (2x2) [1D] [T1]'])

    def test_xaxis_label_explains_trace_id(self):
        from hybridmetrics import _build_hybrid_xaxis_label
        label = _build_hybrid_xaxis_label(
            ['a'], {'a': 'Detailed+MPI+CUDA'}, ['4 (2x2) [1D] [T1]'])
        self.assertIn('[Tn = trace ID]', label)



class PlotUnavailableRowsTests(unittest.TestCase):

    def _df(self, rows):
        import numpy as np
        import pandas as pd
        return pd.DataFrame(
            [[np.nan if v is None else v for v in values] for _, values in rows],
            index=[label for label, _ in rows], columns=['a', 'b'])

    def test_rows_without_values_are_removed(self):
        from hybridmetrics import _drop_unavailable_rows
        df = self._df([
            ('-- Host Computation scalability', (100.0, 79.5)),
            ('   == IPC scalability', (None, None)),
            ('   == Frequency scalability', (None, 98.0)),
        ])
        result, _ = _drop_unavailable_rows(df)
        self.assertEqual(list(result.index), [
            '-- Host Computation scalability', '   == Frequency scalability'])

    def test_separator_follows_removed_rows(self):
        from hybridmetrics import _drop_unavailable_rows
        df = self._df([
            ('HOST Global efficiency', (80.0, 40.0)),
            ('   == IPC scalability', (None, None)),
            ('DEVICE Global efficiency', (12.0, 6.0)),
        ])
        result, separator = _drop_unavailable_rows(df, separator_row=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(separator, 1)

    def test_separator_dropped_when_one_side_is_empty(self):
        from hybridmetrics import _drop_unavailable_rows
        df = self._df([
            ('HOST Global efficiency', (None, None)),
            ('DEVICE Global efficiency', (12.0, 6.0)),
        ])
        _, separator = _drop_unavailable_rows(df, separator_row=1)
        self.assertIsNone(separator)


if __name__ == '__main__':
    unittest.main()
