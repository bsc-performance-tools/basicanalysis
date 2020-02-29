#!/usr/bin/env python3

"""modelfactors.py utils."""

from __future__ import print_function, division
import os
import sys
import subprocess
import tempfile
import argparse


try:
    import scipy.optimize
except ImportError:
    print('==ERROR== Could not import SciPy. Please make sure to install a current version.')

try:
    import numpy
except ImportError:
    print('==ERROR== Could not import NumPy. Please make sure to install a current version.')

try:
    import sty
    from sty import fg, bg, ef, rs
except ImportError:
    print('sty module not available. Skipping color printing.')

__author__ = "Sandra Mendez"
__copyright__ = "Copyright 2019, Barcelona Supercomputing Center (BSC)"
__version_major__ = 0
__version_minor__ = 3
__version_micro__ = 7
__version__ = str(__version_major__) + "." + str(__version_minor__) + "." + str(__version_micro__)



def parse_arguments():
    """Parses the command line arguments.
    Currently the script only accepts one parameter list, which is the list of
    traces that are processed. This can be a regex and only valid trace files
    are kept at the end.
    """
    parser = argparse.ArgumentParser(description='Generates performance metrics from a set of Paraver traces.')
    parser.add_argument('trace_list', nargs='*',
                        help='list of traces to process. Accepts wild cards and automatically filters for '
                             'valid traces'),
    parser.add_argument('--metrics', choices=['simple', 'hybrid'], default='simple',
                        help='select the kind of efficiency metrics (single parallelism or hybrid, default: simple)')
    parser.add_argument("-v", "--version", action='version', version='%(prog)s {version}'.format(version=__version__))
    parser.add_argument("-d", "--debug", help="increase output verbosity to debug level", action="store_true")
    parser.add_argument("-s", "--scaling",
                        help="define whether the measurements are weak or strong scaling (default: auto)",
                        choices=['weak', 'strong', 'auto'], default='auto')
    parser.add_argument("-p", "--project", metavar='<path-to-modelfactors.csv>',
                        help="run only the projection for the given modelfactors.csv (default: false)")
    parser.add_argument('--limit', help='limit number of cores for the projection (default: 10000)')
    parser.add_argument('--model', choices=['amdahl', 'pipe', 'linear'], default='amdahl',
                        help='select model for prediction (default: amdahl)')
    parser.add_argument('--bounds', choices=['yes', 'no'], default='yes',
                        help='set bounds for the prediction (default: yes)')
    parser.add_argument('--sigma', choices=['first', 'equal', 'decrease'], default='first',
                        help='set error restrains for prediction (default: first). first: prioritize smallest run; '
                             'equal: no priority; decrease: decreasing priority for larger runs')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    cmdl_args = parser.parse_args()

    if cmdl_args.debug:
        print('==DEBUG== Running in debug mode.')

    return cmdl_args


def which(cmd):
    """Returns path to cmd in path or None if not available."""
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        cmd_path = os.path.join(path, cmd)
        if os.path.isfile(cmd_path) and os.access(cmd_path, os.X_OK):
            return cmd_path

    return None

def check_installation(cmdl_args):
    """Check if Dimemas and paramedir are in the path."""

    if not which('Dimemas'):
        print('Could not find Dimemas. Please make sure Dimemas is correctly installed and in the path.')
        sys.exit(1)
    if not which('paramedir'):
        print('Could not find paramedir. Please make sure Paraver is correctly installed and in the path.')
        sys.exit(1)

    if cmdl_args.debug:
        print('==DEBUG== Using', __file__, __version__)
        print('==DEBUG== Using', sys.executable, ".".join(map(str, sys.version_info[:3])))

        try:
            print('==DEBUG== Using', 'SciPy', scipy.__version__)
        except NameError:
            print('==DEBUG== SciPy not installed.')

        try:
            print('==DEBUG== Using', 'NumPy', numpy.__version__)
        except NameError:
            print('==DEBUG== NumPy not installed.')

        print('==DEBUG== Using', which('Dimemas'))
        print('==DEBUG== Using', which('paramedir'))
        print('')

    return

def run_command(cmd, cmdl_args):
    """Runs a command and forwards the return value."""
    if cmdl_args.debug:
        print('==DEBUG== Executing:', ' '.join(cmd))

    # In debug mode, keep the output. Otherwise, redirect it to devnull.
    if cmdl_args.debug:
        out = tempfile.NamedTemporaryFile(suffix='.out', prefix=cmd[0] + '_', dir='./', delete=False)
        err = tempfile.NamedTemporaryFile(suffix='.err', prefix=cmd[0] + '_', dir='./', delete=False)
    else:
        out = open(os.devnull, 'w')
        err = open(os.devnull, 'w')

    return_value = subprocess.call(cmd, stdout=out, stderr=err)

    out.close
    err.close

    if return_value == 0:
        if cmdl_args.debug:
            os.remove(out.name)
            os.remove(err.name)
    else:
        print('==ERROR== ' + ' '.join(cmd) + ' failed with return value ' + str(return_value) + '!')
        print('See ' + out.name + ' and ' + err.name + ' for more details.')

    return return_value


def save_remove(path,cmdl_args):
    """Wraps os.remove with a try clause."""
    try:
        os.remove(path)
    except:
        if cmdl_args.debug:
            print('==DEBUG== Failed to remove ' + path + '!')

