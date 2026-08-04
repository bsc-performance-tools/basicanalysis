import unittest

from report.model import ReportSection, TraceInfo
from report.renderer.html import render_trace_configuration


class TestOverviewHtmlRenderer(unittest.TestCase):

    def test_render_mpi_trace_configuration(self):
        section = ReportSection(
            section_id="trace-configuration",
            title="Trace configuration",
            section_type="overview-traces",
            payload=(
                TraceInfo(
                    trace_id=1,
                    name="case.prv",
                    path="/tmp/case.prv",
                    mode="Detailed+MPI",
                    processes=16,
                    tasks=16,
                    threads=1,
                    devices=0,
                    gpu_streams=0,
                    gpu_streams_per_rank=0,
                ),
            ),
        )

        rendered = render_trace_configuration(section)

        self.assertIn(
            "<table class='metric-table'>",
            rendered,
        )
        self.assertIn("<th>MPI ranks</th>", rendered)
        self.assertIn("<strong>T1</strong>", rendered)
        self.assertIn("<code>case.prv</code>", rendered)
        self.assertIn("<td>Detailed</td>", rendered)
        self.assertIn("<td>MPI</td>", rendered)
        self.assertIn("<td>16</td>", rendered)

    def test_render_mpi_openmp_trace_configuration(self):
        section = ReportSection(
            section_id="trace-configuration",
            title="Trace configuration",
            section_type="overview-traces",
            payload=(
                TraceInfo(
                    trace_id=2,
                    name="hybrid.prv",
                    path="/tmp/hybrid.prv",
                    mode="Detailed+MPI+OpenMP",
                    processes=32,
                    tasks=8,
                    threads=4,
                    devices=0,
                    gpu_streams=0,
                    gpu_streams_per_rank=0,
                ),
            ),
        )

        rendered = render_trace_configuration(section)

        self.assertIn("<th>Parallel units</th>", rendered)
        self.assertIn("<th>MPI ranks</th>", rendered)
        self.assertIn("<th>Threads/rank</th>", rendered)
        self.assertIn("<td>MPI + OpenMP</td>", rendered)
        self.assertIn("<td>32</td>", rendered)
        self.assertIn("<td>8</td>", rendered)
        self.assertIn("<td>4</td>", rendered)

    def test_render_empty_trace_configuration(self):
        section = ReportSection(
            section_id="trace-configuration",
            title="Trace configuration",
            section_type="overview-traces",
            payload=(),
        )

        rendered = render_trace_configuration(section)

        self.assertEqual(
            rendered,
            "<p>No trace configuration information available.</p>",
        )

    def test_reject_wrong_section(self):
        section = ReportSection(
            section_id="general-metrics",
            title="General metrics",
            section_type="overview-metrics",
            payload=(),
        )

        with self.assertRaises(ValueError):
            render_trace_configuration(section)


if __name__ == "__main__":
    unittest.main()