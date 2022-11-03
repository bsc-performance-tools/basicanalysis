#!/usr/bin/env python3

"""modelfactors.py utils."""

from __future__ import print_function, division
import os
import sys
import subprocess
import tempfile
import argparse
import shutil


try:
    import scipy.optimize
except ImportError:
    print('==Error== Could not import SciPy. Please make sure you have installed SciPy.')

try:
    import numpy
except ImportError:
    print('==Error== Could not import NumPy. Please make sure you have installed NumPy.')

try:
    import pandas as pd
except ImportError:
    print('==Error== Could not import pandas. Please make sure you have installed pandas.')
try:
    import seaborn as sns
except ImportError:
    print('==Error== Could not import seaborn. Please make sure you have installed  seaborn.')

try:
    import matplotlib.pyplot as plt
except ImportError:
    print('==Error== Could not import matplotlib. Please make sure you have installed matplotlib.')


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
    parser.add_argument("-m", "--metrics", choices=['simple', 'hybrid'], default='hybrid',
                        help='select the kind of efficiency metrics (single parallelism or hybrid, default: hybrid)')
    parser.add_argument("-v", "--version", action='version', version='%(prog)s {version}'.format(version=__version__))
    parser.add_argument("-d", "--debug", help="increase output verbosity to debug level", action="store_true")
    parser.add_argument("-s", "--scaling",
                        help="define whether the measurements are weak or strong scaling (default: auto)",
                        choices=['weak', 'strong', 'auto'], default='auto')
    parser.add_argument('--limit', help='limit number of cores for the plots '
                                        '(default: max processes of the trace list )')
    parser.add_argument("-ms", "--max_trace_size", help='set the maximum trace size in MiB allowed.'
                                                        ' (default: 1024 MiB )', default=1024.0)
    parser.add_argument("-tmd", "--trace_mode_detection", choices=['pcf', 'prv'], default='pcf',
                        help='select .prv or .pcf file for trace mode detection. '
                             'For customized traces, i.e. cut, filtered and so on, you must select'
                             ' the .prv file. (default: pcf)')
    parser.add_argument("-ord", "--order_traces", choices=['yes', 'not'], default='yes',
                        help='Order the trace list based on the numbers of processes')

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
        print("Warning: Dimemas is not installed. Transfer and Serialization will be not calculated!\n")
        # sys.exit(1)
    if not which('paramedir'):
        print('Could not find paramedir. Please make sure Paraver is correctly installed and in the path.')
        sys.exit(1)

    if not which('python3'):
        print('==> WARNING!!! It requires python version 3 or higher for a full functionality.')
        option_user = input("Do you want to proceed with the analysis? (Yes/No)[Yes]: ").upper()
        if option_user == 'NO':
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


def create_temp_folder(folder_name, cmdl_args):
    path_output_aux = os.getcwd() + '/' + folder_name

    if os.path.exists(path_output_aux):
        shutil.rmtree(path_output_aux)
    os.makedirs(path_output_aux)
    return (path_output_aux)


def move_files(path_source, path_dest, cmdl_args):
    """Wraps os.remove with a try clause."""
    try:
        shutil.move(path_source, path_dest)
    except:
        if cmdl_args.debug:
            print('==DEBUG== Failed to move ' + path_source + '!')


def remove_files(path,cmdl_args):
    """Wraps os.remove with a try clause."""
    try:
        os.remove(path)
    except:
        if cmdl_args.debug:
            print('==DEBUG== Failed to remove ' + path + '!')