import argparse
import atexit
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

import utils


class TestRunLog(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.stdout, self.stderr = sys.stdout, sys.stderr

    def tearDown(self):
        sys.stdout, sys.stderr = self.stdout, self.stderr
        self.tmp.cleanup()

    def _start(self, **kwargs):
        args = argparse.Namespace(log=kwargs.pop('log', None), no_log=kwargs.pop('no_log', False))
        console = io.StringIO()
        sys.stdout = console
        sys.stderr = console
        hooks = []
        argv = ['modelfactors.py', '--workload', '1,2', 'my trace.prv']
        with mock.patch.object(sys, 'argv', argv), \
                mock.patch.object(atexit, 'register', hooks.append):
            path = utils.start_run_log(args, **kwargs)
        return path, console, hooks

    def test_log_has_command_and_output(self):
        log = os.path.join(self.tmp.name, 'run.log')
        path, console, hooks = self._start(log=log)
        self.assertEqual(path, log)
        print('analysis output')
        sys.stderr.write('a warning\n')
        for hook in hooks:
            hook()
        sys.stdout, sys.stderr = self.stdout, self.stderr
        with open(log) as f:
            text = f.read()
        self.assertIn("Command:   modelfactors.py --workload 1,2 'my trace.prv'", text)
        self.assertIn('BasicAnalysis ' + utils.__version__, text)
        self.assertIn('analysis output', text)
        self.assertIn('a warning', text)
        self.assertIn('Finished:', text)
        self.assertIn('analysis output', console.getvalue())

    def test_no_log(self):
        path, _, hooks = self._start(log=os.path.join(self.tmp.name, 'x.log'), no_log=True)
        self.assertIsNone(path)
        self.assertEqual(hooks, [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, 'x.log')))

    def test_no_default_file(self):
        path, _, hooks = self._start(default_file=None)
        self.assertIsNone(path)
        self.assertEqual(hooks, [])

    def test_parser_options(self):
        parser = utils.build_argument_parser()
        for option in ('-o', '--output', '--log'):
            args = parser.parse_args([option, 'a.log', 't.prv'])
            self.assertEqual(args.log, 'a.log')
            self.assertFalse(args.no_log)

    def test_command_is_the_first_console_line(self):
        for no_log in (False, True):
            _, console, hooks = self._start(
                log=os.path.join(self.tmp.name, 'c.log'), no_log=no_log)
            sys.stdout, sys.stderr = self.stdout, self.stderr
            for hook in hooks:
                hook()
            self.assertEqual(
                console.getvalue().splitlines()[0],
                "Command: modelfactors.py --workload 1,2 'my trace.prv'")


class TestSortOptions(unittest.TestCase):

    def _parse(self, argv):
        stderr = io.StringIO()
        with mock.patch.object(sys, 'stderr', stderr):
            args = utils.build_argument_parser().parse_args(argv)
        return args, stderr.getvalue()

    def test_default_sorts(self):
        args, warning = self._parse(['t.prv'])
        self.assertEqual(args.order_traces, 'yes')
        self.assertEqual(warning, '')

    def test_no_sort(self):
        args, warning = self._parse(['--no-sort', 't.prv'])
        self.assertEqual(args.order_traces, 'not')
        self.assertEqual(warning, '')

    def test_deprecated_ord(self):
        args, warning = self._parse(['-ord', 'not', 't.prv'])
        self.assertEqual(args.order_traces, 'not')
        self.assertIn('-ord is deprecated', warning)
        self.assertIn('--no-sort', warning)


if __name__ == '__main__':
    unittest.main()
