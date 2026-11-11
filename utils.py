#!/usr/bin/env python3

"""modelfactors.py utils."""

from __future__ import print_function, division
import os
import sys
import subprocess
import tempfile
import argparse
import shutil
import shlex
import socket
import time
import atexit
from datetime import datetime

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

__version_major__ = 2026
__version_minor__ = 10
__version_micro__ = 5
__version__ = f"{__version_major__}.{__version_minor__:02d}.{__version_micro__:02d}"



def build_argument_parser():
    parser = argparse.ArgumentParser(
        description='Generates performance metrics from a set of Paraver traces.'
    )
    parser.add_argument('trace_list', nargs='*',
                        help='list of traces to process. Accepts wild cards and automatically filters for '
                             'valid traces')
    parser.add_argument("-m", "--metrics", choices=['simple', 'hybrid'], default='hybrid',
                        help='select the kind of efficiency metrics (single parallelism or hybrid, default: hybrid)')
    parser.add_argument("-v", "--version", action='version',
                        version='%(prog)s {version}'.format(version=__version__))
    parser.add_argument("-d", "--debug", help="increase output verbosity to debug level", action="store_true")
    parser.add_argument("-s", "--scaling",
                        help="define whether the measurements are weak or strong scaling (default: auto). "
                             "In the Host/Device model with only --host-workload or --device-workload, it sets "
                             "the scaling of the domain without a workload",
                        choices=['weak', 'strong', 'auto'], default='auto')
    parser.add_argument("--workload", metavar="W1,W2,...",
                        help='use a user-defined workload instead of weak or strong scaling. Comma-separated '
                             'workload values of the whole application (e.g. batch sizes, or ratios), one per '
                             'trace, in the order the traces are given; the traces are then not sorted, and the '
                             'first one is the reference. The ratio of each trace is its value divided by the '
                             'value of the reference. It is used in all the scalability metrics; in the '
                             'Host/Device model, it is also the workload of the Host and Device domains that '
                             'have no workload of their own. Cannot be combined with --scaling')
    for domain, unit in (('host', 'Host'), ('device', 'Device')):
        parser.add_argument("--{}-workload".format(domain), metavar="W1,W2,...",
                            help='{0} workload values, one per trace, for the {0} metrics of the Host/Device model '
                                 '(MPI+GPU, GPU without MPI, nsys2prv). Without --workload, the domain without a '
                                 'workload uses the scaling detected from its own measurements, or the one given '
                                 'with --scaling{1}'.format(
                                     unit,
                                     ', and Speedup and Scaling Efficiency use the Device workload'
                                     if domain == 'device' else ''))
    parser.add_argument("--thresholds", metavar="CRITICAL,ATTENTION", type=_thresholds_argument,
                        default=None,
                        help='efficiency thresholds, in %%, of the colors of the efficiency tables and '
                             'figures and of the interpretation in the report: values below CRITICAL are '
                             'critical, values from ATTENTION are good (default: 60,85). They apply to '
                             'every efficiency metric; the report can still change them in the browser')
    parser.add_argument('--limit', help='limit number of cores for the plots '
                                        '(default: max processes of the trace list )')
    parser.add_argument("-ms", "--max_trace_size", help='set the maximum trace size in MiB allowed.'
                                                        ' (default: 1024 MiB )', default=1024.0)
    parser.add_argument("-skip-simul", "--skip-simulation",
                        help="Skip running the dimemas simulation", action="store_true")
    parser.add_argument("-tmd", "--trace_mode_detection", choices=['pcf', 'prv'], default='pcf',
                        help='select .prv or .pcf file for trace mode detection. '
                             'For customized traces, i.e. cut, filtered and so on, you must select'
                             ' the .prv file. (default: pcf)')
    add_sort_arguments(parser)
    parser.add_argument("-somp", "--simulation_openmp", help='OpenMP events will be simulated '
                                                          '(default: disable).', action="store_true")
    parser.add_argument("-scuda", "--simulation_cuda", help='CUDA events will be simulated '
                                                         '(default: disable).', action="store_true")                                                   
    parser.add_argument("-pop-model", "--pop_model_to_apply", choices=['classic', 'talp'], default='talp',
                        help='Select the model to compute POP metrics for MPI+GPU codes (default: talp).'
                             ' classic shows the multiplicative hybrid metrics proposed by BSC Tools group in POP2'
                             ' and talp presents the metrics proposed by TALP team in POP3.')
    parser.add_argument('--jobs', default='1', help='Number of parallel trace analyses, or "auto" (default: 1)')
    parser.add_argument('--mem-per-worker-gb', type=float, default=None,
                       help='Estimated memory required per worker in GiB; overrides automatic heuristic')
    parser.add_argument('--ideal-omp', action='store_true', help='In simulation of MPI+OpenMP codes, it ignores the duration'
    ' of OpenMP runtime events. Any remaining duration is due to implicit synchronization.')
    parser.add_argument('--hyb-mpiomp', action='store_true', help='Compute Serialization and Transfer at OpenMP level for MPI+OpenMP codes.')
    parser.add_argument('-o', '--output', '--log', dest='log', metavar='FILE', default=None,
                        help='file where the command line and the standard output of the run are saved '
                             '(default: {} in the current directory). --log is the former name of this '
                             'option'.format(DEFAULT_LOG_FILE))
    parser.add_argument('--no-log', action='store_true',
                        help='do not save the command line and the standard output in a file')
    return parser


class _DeprecatedOrderAction(argparse.Action):
    """-ord/--order_traces yes|not, replaced by --no-sort."""

    def __call__(self, parser, namespace, values, option_string=None):
        print('==WARNING== {} is deprecated and will be removed in a future release; '
              'use --no-sort to keep the order of the traces.'.format(option_string),
              file=sys.stderr)
        setattr(namespace, self.dest, values)


def add_sort_arguments(parser, workload_options=True):
    """--no-sort, and the deprecated -ord/--order_traces.

    Both set ``order_traces`` ('yes' sorts the traces by number of processes).
    A user-defined workload always keeps the command-line order."""
    parser.add_argument('--no-sort', dest='order_traces', action='store_const', const='not',
                        default='yes',
                        help='keep the traces in the order given, instead of sorting them by number '
                             'of processes; the first trace is the reference{}'.format(
                                 '. Implied by --workload, --host-workload, and --device-workload'
                                 if workload_options else ''))
    parser.add_argument('-ord', '--order_traces', dest='order_traces', choices=['yes', 'not'],
                        action=_DeprecatedOrderAction,
                        help='deprecated: use --no-sort instead of "-ord not"')


def _thresholds_argument(text):
    """argparse type of --thresholds."""
    from metrics import parse_thresholds
    try:
        return parse_thresholds(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error))


def apply_efficiency_thresholds(cmdl_args):
    """Use the thresholds of --thresholds for every efficiency metric."""
    thresholds = getattr(cmdl_args, 'thresholds', None)
    if thresholds is None:
        return
    from metrics import get_default_provider
    get_default_provider().set_threshold_override(thresholds)
    print('==> Efficiency thresholds (--thresholds): Critical below {:g}%, '
          'Attention {:g}%-{:g}%, Good from {:g}%'.format(
              thresholds.critical, thresholds.critical,
              thresholds.attention, thresholds.attention))


def parse_arguments():
    return build_argument_parser().parse_args()


DEFAULT_LOG_FILE = 'basicanalysis.log'


class _TeeStream(object):
    """Write to the console stream and to the log file."""

    def __init__(self, stream, log):
        self._stream = stream
        self._log = log

    def write(self, data):
        self._stream.write(data)
        if not self._log.closed:
            self._log.write(data)
        return len(data)

    def flush(self):
        self._stream.flush()
        if not self._log.closed:
            self._log.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def command_line(argv=None):
    """The command line of the run, quoted so that it can be pasted in a shell."""
    argv = sys.argv if argv is None else argv
    return ' '.join(shlex.quote(arg) for arg in argv)


def start_run_log(cmdl_args, default_file=DEFAULT_LOG_FILE):
    """Save the command line and the standard output and error of the run in a file.

    The output still goes to the console. The command line is always printed
    first, so that it is the reference of the output; the log file has it in its
    header. Returns the path of the log file, or None when the log is disabled
    (--no-log, or no file given and no default)."""
    print('Command: {}'.format(command_line()))
    if getattr(cmdl_args, 'no_log', False):
        return None
    path = getattr(cmdl_args, 'log', None) or default_file
    if not path:
        return None
    try:
        log = open(path, 'w', buffering=1)
    except OSError as error:
        print('==WARNING== Could not open the log file {}: {}'.format(path, error))
        return None
    start = datetime.now()
    log.write('BasicAnalysis {} ({})\n'.format(__version__, os.path.basename(sys.argv[0])))
    log.write('Date:      {}\n'.format(start.strftime('%Y-%m-%d %H:%M:%S')))
    log.write('Host:      {}\n'.format(socket.gethostname()))
    log.write('Directory: {}\n'.format(os.getcwd()))
    log.write('Command:   {}\n'.format(command_line()))
    log.write('-' * 79 + '\n')
    sys.stdout = _TeeStream(sys.stdout, log)
    sys.stderr = _TeeStream(sys.stderr, log)

    def _close():
        end = datetime.now()
        log.write('-' * 79 + '\n')
        log.write('Finished:  {} (elapsed {})\n'.format(
            end.strftime('%Y-%m-%d %H:%M:%S'), str(end - start).split('.')[0]))
        log.close()

    atexit.register(_close)
    print('==> Command line and output saved in {}'.format(path))
    return path


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

    if not which('Dimemas') and not cmdl_args.skip_simulation:
        print('Could not find Dimemas. Please make sure Dimemas is correctly installed and in the path.')
        print("Warning: Dimemas is not installed. Transfer and Serialization will be not calculated!\n")

    if cmdl_args.skip_simulation:
        print("Skipping Simulation. Transfer and Serialization will be not calculated!\n")

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
    ERROR_SIMULATION_INCOMPLETE = 1001  # 1001 when Dimemas produces incomplete simulation

    if cmdl_args.debug:
        print('==DEBUG== Executing:', ' '.join(cmd))

    if "Dimemas" in cmd:
        # Run Dimemas and capture output
        result_dimemas = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # cmd[4] should be the trace/config file path
        dim_path = cmd[4]
        dim_base = os.path.splitext(os.path.basename(dim_path))[0]  # e.g. "sphexa-cuda....extrae-5.0.0"

        dimemas_output = f"dimemas_{dim_base}.out"
        dimemas_error  = f"dimemas_{dim_base}.err"

        with open(dimemas_output, "wb") as f:
            f.write(result_dimemas.stdout)
        with open(dimemas_error, "wb") as f:
            f.write(result_dimemas.stderr)

        if b'] 100.0%' in result_dimemas.stdout:
            return_value = 0
        elif b'END SIMULATION' in result_dimemas.stdout:
            return_value = ERROR_SIMULATION_INCOMPLETE
        else:
            print("ERROR DIMEMAS:\n", result_dimemas.returncode)
            return_value = result_dimemas.returncode

    else:
        # Normal command (non-Dimemas)
        if len(cmd) < 2:
            raise ValueError(f"Unexpected cmd structure (need at least 2 elements): {cmd}")

        trace_path = cmd[1]
        trace_base = os.path.splitext(os.path.basename(trace_path))[0]

        unique_id = f"{os.getpid()}_{time.time_ns()}"

        std_output = f"{cmd[0]}stdout_{trace_base}_{unique_id}.out"
        err_error  = f"{cmd[0]}error_{trace_base}_{unique_id}.err"

        with open(std_output, "w") as out, open(err_error, "w") as err:
            return_value = subprocess.call(cmd, stdout=out, stderr=err)

    # Remove temp files if everything went well
    if return_value == 0:
        if "Dimemas" in cmd:
            if os.path.exists(dimemas_output):
                os.remove(dimemas_output)

            if os.path.exists(dimemas_error):
                os.remove(dimemas_error)
            print("")
        else:
            if os.path.exists(std_output):
                os.remove(std_output)

            if os.path.exists(err_error):
                os.remove(err_error)

    else:
        if return_value != ERROR_SIMULATION_INCOMPLETE and "Dimemas" not in cmd:
            print('==ERROR== ' + ' '.join(cmd) + ' failed with return value ' + str(return_value) + '!')
            print('See ' + std_output + ' and ' + err_error + ' for more details.')
        else:
            if return_value != ERROR_SIMULATION_INCOMPLETE:
                print('==ERROR== ' + ' '.join(cmd) + ' failed with return value ' + str(return_value) + '!')
                print('See ' + dimemas_output + ' and ' + dimemas_error + ' for more details.')

    return return_value


def create_temp_folder(folder_name, cmdl_args):
    path_output_aux = os.path.join(os.getcwd(), folder_name)
    os.makedirs(path_output_aux, exist_ok=True)
    return path_output_aux


def move_files(path_source, path_dest, cmdl_args):
    """Move file to destination directory, replacing existing file if needed."""
    try:
        if not os.path.exists(path_source):
            return

        os.makedirs(path_dest, exist_ok=True)

        dst_file = os.path.join(path_dest, os.path.basename(path_source))

        if os.path.exists(dst_file):
            os.remove(dst_file)

        shutil.move(path_source, dst_file)

    except Exception as e:
        if cmdl_args.debug:
            print('==DEBUG== Failed to move ' + path_source + ' to ' + path_dest + '!')
            print('==DEBUG== ' + str(e))


def remove_files(path,cmdl_args):
    """Wraps os.remove with a try clause."""
    try:
        os.remove(path)
    except:
        if cmdl_args.debug:
            print('==DEBUG== Failed to remove ' + path + '!')
