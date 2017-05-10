#!/usr/bin/python

import os
import sys
import subprocess
import tempfile
import argparse
import fnmatch
import re
import time
from collections import OrderedDict


#Basic debug switch to enable more verbose output
debug = False


#Contains all raw data entries with a printable name.
#This is used to generate and print all raw data, so, if you need to add an
#entry, it should be added here, too.
raw_data_doc = OrderedDict([('runtime',     'Runtime'),
                            ('runtime_dim', 'Runtime (ideal)'),
                            ('useful_avg',  'Useful duration (average)'),
                            ('useful_max',  'Useful duration (maximum)'),
                            ('useful_tot',  'Useful duration (total)'),
                            ('useful_dim',  'Useful duration (ideal, max)'),
                            ('useful_ins',  'Useful instructions (total)'),
                            ('useful_cyc',  'Useful cycles (total)')])


#Contains all model factor entries with a printable name.
#This is used to generate and print all model factors, so, if you need to add an
#entry, it should be added here, too.
mod_factors_doc = OrderedDict([('parallel_eff', 'Parallel efficiency'),
                               ('load_balance', '  Load balance'),
                               ('comm_eff',     '  Communication efficiency'),
                               ('serial_eff',   '    Serialization efficiency'),
                               ('transfer_eff', '    Transfer efficiency'),
                               ('comp_scale',   'Computation scalability'),
                               ('global_eff',   'Global efficiency'),
                               ('ipc_scale',    'IPC scalability'),
                               ('inst_scale',   'Instruction scalability'),
                               ('speedup',      'Speedup'),
                               ('ipc',          'Average IPC')])


def parse_arguments():
    """Parses the command line arguments.
    Currently the script only accepts one parameter list, which is the list of
    traces that are processed. This can be a regex and only valid trace files
    are kept at the end.
    """
    parser = argparse.ArgumentParser(description='Generates performance metrics from a set of paraver traces.')
    parser.add_argument('trace_list', nargs='+', help='List of traces to process. Accepts wild cards and automatically filters for valid traces.')
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    cmdl_args = parser.parse_args()
    return cmdl_args


def get_traces_from_args(cmdl_args):
    """Filters the given list to extract traces, i.e. matching *.prv and sorts
    the traces in ascending order based on the number of processes in the trace.
    Excludes all files other than *.prv and ignores also simulated traces from
    this script, i.e. *.sim.prv
    """
    prv_files = [x for x in cmdl_args.trace_list if fnmatch.fnmatch(x, '*.prv') if not fnmatch.fnmatch(x, '*.sim.prv')]
    prv_files = sorted(prv_files, key=get_num_processes)
    print_overview(prv_files)
    return prv_files


def get_num_processes(prv_file):
    """Gets the number of processes in a trace from the according .row file.
    The number of processes in a trace is always stored at the fourth position
    in the first line of the according *.row file.
    Please note: return value needs to be integer because this function is also
    used as sorting key.
    """
    cpus = open( prv_file[:-4] + '.row' ).readline().rstrip().split(' ')[3]
    return int(cpus)


def human_readable(size, precision=1):
    """Converts a given size in bytes to the value in human readable form."""
    suffixes=['B','KB','MB','GB','TB']
    suffixIndex = 0
    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size = size/1024.0
    return "%.*f%s"%(precision,size,suffixes[suffixIndex])


def print_overview(trace_list):
    """Prints an overview of the traces that will be processed."""
    print 'Running modelfactors.py for the following traces:'

    for trace in trace_list:
        line = trace
        line += ', ' + str(get_num_processes(trace)) + ' processes'
        line += ', ' + human_readable( os.path.getsize( trace ) )
        print line
    print


def run_command(cmd):
    """Runs a command and forwards the return value."""
    out = tempfile.NamedTemporaryFile(suffix='.out', prefix=cmd[0]+'_',
                                      dir='./', delete=False)
    err = tempfile.NamedTemporaryFile(suffix='.err', prefix=cmd[0]+'_',
                                      dir='./', delete=False)
    if (debug):
        print 'Executing:'
        print ' '.join(cmd)

    return_value = subprocess.call(cmd, stdout=out, stderr=err)
    if return_value == 0:
        os.remove(out.name)
        os.remove(err.name)
    else:
        print ' '.join(cmd) + ' failed with return value ' + str(return_value) + '!'

    return return_value


def create_raw_data(trace_list):
    """Creates 2D dictionary of the raw input data and initializes with zero.
    The raw_data dictionary has the format: [raw data key][trace].
    """
    global raw_data_doc
    raw_data = {}
    for key in raw_data_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = 0

        raw_data[key] = trace_dict

    return raw_data


def create_mod_factors(trace_list):
    """Creates 2D dictionary of the model factors and initializes with an empty
    string. The mod_factors dictionary has the format: [mod factor key][trace].
    """
    global mod_factors_doc
    mod_factors = {}
    for key in mod_factors_doc:
        trace_dict = {}
        for trace_name in trace_list:
            trace_dict[trace_name] = ''
        mod_factors[key] = trace_dict

    return mod_factors


def print_raw_data_table(raw_data, trace_list):
    """Prints the raw data table in human readable form on stdout."""
    global raw_data_doc

    longest_name = len(sorted(raw_data_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    for trace in trace_list:
        line += ' | '
        line += str(get_num_processes(trace)).rjust(15)
    print line

    print ''.ljust(len(line),'=')

    for data_key in raw_data_doc:
        line = raw_data_doc[data_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            line += str(raw_data[data_key][trace]).rjust(15)
        print line
    print


def print_mod_factors_table(mod_factors, trace_list):
    """Prints the model factors table in human readable form on stdout."""
    global mod_factors_doc

    longest_name = len(sorted(mod_factors_doc.values(), key=len)[-1])

    line = ''.rjust(longest_name)
    for trace in trace_list:
        line += ' | '
        line += str(get_num_processes(trace)).rjust(10)
    print line

    print ''.ljust(len(line),'=')

    for mod_key in mod_factors_doc:
        line = mod_factors_doc[mod_key].ljust(longest_name)
        for trace in trace_list:
            line += ' | '
            line += ('{:.2f}'.format(mod_factors[mod_key][trace])).rjust(10)
        print line
        #Print empty line to separate values
        if mod_key == 'global_eff' or mod_key == 'inst_scale':
            line = ''.ljust(longest_name)
            for trace in trace_list:
                line += ' | '
                line += ''.rjust(10)
            print line

    print


def print_mod_factors_csv(mod_factors, trace_list):
    """Prints the model factors table in a csv file."""
    global mod_factors_doc

    delimiter = ';'
    #File is stored in the trace directory
    file_path = os.path.join(os.path.dirname(os.path.realpath(trace_list[0])), 'modelfactors.csv')

    with open(file_path, 'w') as output:
        line = 'Number of processes'
        for trace in trace_list:
            line += delimiter
            line += str(get_num_processes(trace))
        output.write(line + '\n')

        for mod_key in mod_factors_doc:
            line = mod_factors_doc[mod_key].replace('  ', '', 2)
            for trace in trace_list:
                line += delimiter
                line += '{:.2f}'.format(mod_factors[mod_key][trace])
            output.write(line + '\n')

    print 'Output written to ' + file_path


def gather_raw_data(trace_list):
    """Gathers all raw data needed to generate the model factors. Return raw
    data in a 2D dictionary <data type><list of values for each trace>"""
    raw_data = create_raw_data(trace_list)

    cfgs = {}
    cfgs['root_dir']      = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')
    cfgs['timings']       = os.path.join(cfgs['root_dir'], 'timings.cfg')
    cfgs['runtime']       = os.path.join(cfgs['root_dir'], 'runtime.cfg')
    cfgs['cycles']        = os.path.join(cfgs['root_dir'], 'cycles.cfg')
    cfgs['instructions']  = os.path.join(cfgs['root_dir'], 'instructions.cfg')

    #Main loop over all traces
    #This can be parallized: the loop iterations have no dependencies
    for trace in trace_list:
        time_tot = time.time()

        line = 'Analyzing ' + os.path.basename(trace)
        line += ' (' + str(get_num_processes(trace)) + ' processes'
        line += ', ' + human_readable( os.path.getsize( trace ) ) + ')'
        print line

        #Create simulated ideal trace with Dimemas
        time_dim = time.time()
        trace_sim = create_ideal_trace(trace)
        time_dim = time.time() - time_dim
        print 'Successfully created simulated trace with Dimemas in {:.1f} seconds.'.format(time_dim)

        #Run paramedir for the original and simulated trace
        time_pmd = time.time()
        cmd_normal = ['paramedir', trace]
        cmd_normal.extend([cfgs['timings'],      trace[:-4] + '.timings.stats'])
        cmd_normal.extend([cfgs['runtime'],      trace[:-4] + '.runtime.stats'])
        cmd_normal.extend([cfgs['cycles'],       trace[:-4] + '.cycles.stats'])
        cmd_normal.extend([cfgs['instructions'], trace[:-4] + '.instructions.stats'])

        cmd_ideal = ['paramedir', trace_sim]
        cmd_ideal.extend([cfgs['timings'],       trace_sim[:-4] + '.timings.stats'])
        cmd_ideal.extend([cfgs['runtime'],       trace_sim[:-4] + '.runtime.stats'])

        run_command(cmd_normal)
        run_command(cmd_ideal)

        time_pmd = time.time() - time_pmd
        print 'Successfully analyzed trace with paramedir in {:.1f} seconds.'.format(time_pmd)


        #Parse the paramedir output files
        time_prs = time.time()

        #Get total, average, and maximum useful duration
        content = []
        with open(trace[:-4] + '.timings.stats') as f:
            content = f.readlines()

        for line in content:
            if line.split():
                if line.split()[0] == 'Total':
                    raw_data['useful_tot'][trace] = float(line.split()[1])
                if line.split()[0] == 'Average':
                    raw_data['useful_avg'][trace] = float(line.split()[1])
                if line.split()[0] == 'Maximum':
                    raw_data['useful_max'][trace] = float(line.split()[1])

        #Get runtime
        content = []
        with open(trace[:-4] + '.runtime.stats') as f:
            content = f.readlines()

        for line in content:
            if line.split():
                if line.split()[0] == 'Average':
                    raw_data['runtime'][trace] = float(line.split()[1])

        #Get useful cycles
        content = []
        with open(trace[:-4] + '.cycles.stats') as f:
            content = f.readlines()

        for line in content:
            if line.split():
                if line.split()[0] == 'Total':
                    raw_data['useful_cyc'][trace] = int(float(line.split()[1]))

        #Get useful instructions
        content = []
        with open(trace[:-4] + '.instructions.stats') as f:
            content = f.readlines()

        for line in content:
            if line.split():
                if line.split()[0] == 'Total':
                    raw_data['useful_ins'][trace] = int(float(line.split()[1]))

        #Get maximum useful duration for simulated trace
        content = []
        with open(trace_sim[:-4] + '.timings.stats') as f:
            content = f.readlines()

        for line in content:
            if line.split():
                if line.split()[0] == 'Maximum':
                    raw_data['useful_dim'][trace] = float(line.split()[1])

        #Get runtime for simulated trace
        content = []
        with open(trace_sim[:-4] + '.runtime.stats') as f:
            content = f.readlines()

        for line in content:
            if line.split():
                if line.split()[0] == 'Average':
                    raw_data['runtime_dim'][trace] = float(line.split()[1])

        #Remove paramedir output files
        os.remove(trace[:-4] + '.timings.stats')
        os.remove(trace[:-4] + '.runtime.stats')
        os.remove(trace[:-4] + '.cycles.stats')
        os.remove(trace[:-4] + '.instructions.stats')
        os.remove(trace_sim[:-4] + '.timings.stats')
        os.remove(trace_sim[:-4] + '.runtime.stats')
        time_prs = time.time() - time_prs
        #print 'Successfully parsed data in {:.1f} seconds.'.format(time_prs)

        time_tot = time.time() - time_tot
        print 'Finished successfully in {:.1f} seconds.'.format(time_tot)
        print

    return raw_data


def get_scaling_type(raw_data, trace_list):
    """Guess the scaling type (weak/strong) based on the useful instructions.
    Computes the normalized instruction ratio for all measurements, whereas the
    normalized instruction ratio is (instructions ratio / process ratio) with
    the smallest run as reference. For exact weak scaling the normalized ratio
    should be exactly 1 and for exact strong scaling it should be close to zero
    with an upper bound of 0.5. The eps value defines the threshold to be
    considered weak scaling and should give enough buffer to safely handle
    non-ideal scaling.
    """
    eps = 0.9
    normalized_inst_ratio = 0

    for trace in trace_list:
        inst_ratio = float(raw_data['useful_ins'][trace]) / float(raw_data['useful_ins'][trace_list[0]])
        proc_ratio = float(get_num_processes(trace)) / float(get_num_processes(trace_list[0]))
        normalized_inst_ratio += inst_ratio / proc_ratio

    #Get the average inst increase. Ignore ratio of first trace 1.0)
    normalized_inst_ratio = (normalized_inst_ratio - 1) / (len(trace_list) - 1)

    if normalized_inst_ratio > eps:
        return 'weak'
    else:
        return 'strong'


def compute_model_factors(raw_data, trace_list):
    """Computes the model factors from the gathered raw data and returns the
    according dictionary of model factors."""
    mod_factors = create_mod_factors(trace_list)
    #Guess the weak or strong scaling
    scaling = get_scaling_type(raw_data, trace_list)

    #Loop over all traces
    for trace in trace_list:
        proc_ratio = float(get_num_processes(trace)) / float(get_num_processes(trace_list[0]))

        #Basic efficiency factors
        mod_factors['load_balance'][trace] = raw_data['useful_avg'][trace] / raw_data['useful_max'][trace] * 100.0
        mod_factors['comm_eff'][trace] =     raw_data['useful_max'][trace] / raw_data['runtime'][trace] * 100.0
        mod_factors['serial_eff'][trace] =   raw_data['useful_dim'][trace] / raw_data['runtime_dim'][trace] * 100.0
        mod_factors['transfer_eff'][trace] = mod_factors['comm_eff'][trace] / mod_factors['serial_eff'][trace] * 100.0
        mod_factors['parallel_eff'][trace] = mod_factors['load_balance'][trace] * mod_factors['comm_eff'][trace] / 100.0

        if scaling == 'strong':
            mod_factors['comp_scale'][trace] = raw_data['useful_tot'][trace_list[0]] / raw_data['useful_tot'][trace] * 100.0
        else:
            mod_factors['comp_scale'][trace] = raw_data['useful_tot'][trace_list[0]] / raw_data['useful_tot'][trace] / proc_ratio * 100.0

        mod_factors['global_eff'][trace] = mod_factors['parallel_eff'][trace] * mod_factors['comp_scale'][trace] / 100.0

        #Basic scalability factors
        mod_factors['ipc'][trace] = float(raw_data['useful_ins'][trace]) / float(raw_data['useful_cyc'][trace])
        mod_factors['ipc_scale'][trace] = mod_factors['ipc'][trace] / mod_factors['ipc'][trace_list[0]] * 100.0

        if scaling == 'strong':
            mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) / float(raw_data['useful_ins'][trace]) * 100.0
        else:
            mod_factors['inst_scale'][trace] = float(raw_data['useful_ins'][trace_list[0]]) / float(raw_data['useful_ins'][trace]) / proc_ration * 100.0

        mod_factors['speedup'][trace] = raw_data['runtime'][trace_list[0]] / raw_data['runtime'][trace]

    return mod_factors


def create_ideal_trace(trace):
    """Runs prv2dim and dimemas with ideal configuration for given trace."""
    trace_dim = trace[:-4] + '.dim'
    trace_sim = trace[:-4] + '.sim.prv'
    cmd = ['prv2dim', trace, trace_dim]
    run_command(cmd)

    if os.path.isfile(trace_dim):
        if (debug):
            print 'Created file ' + trace_dim
    else:
        print 'Error: ' + trace_dim + 'could not be creaeted.'
        return

    num_processes = str(get_num_processes(trace))

    #Create Dimemas configuration
    cfg_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'cfgs')

    content = []
    with open(os.path.join(cfg_dir, 'dimemas_ideal.cfg')) as f:
        content = f.readlines()

    content = [line.replace('REPLACE_BY_NTASKS', num_processes ) for line in content]
    content = [line.replace('REPLACE_BY_COLLECTIVES_PATH', os.path.join(cfg_dir, 'dimemas.collectives')) for line in content]

    with open(trace[:-4]+'.dimemas_ideal.cfg', 'w') as f:
        f.writelines(content)

    cmd = ['Dimemas', '-S', '32k', '--dim', trace_dim, '-p', trace_sim, trace[:-4]+'.dimemas_ideal.cfg']
    run_command(cmd)

    if os.path.isfile(trace_sim):
        if (debug):
            print 'Created file ' + trace_sim
    else:
        print 'Error: ' + trace_sim + 'could not be creaeted.'

    os.remove(trace_dim)
    os.remove(trace[:-4]+'.dimemas_ideal.cfg')

    return trace_sim


if __name__ == "__main__":
    """Main control flow.
    Currently the script only accepts one parameter, which is a list of traces
    that are processed. This can be a regex with wild cards and only valid trace
    files are kept at the end.
    """
    #Parse command line arguments
    cmdl_args = parse_arguments()

    #Filters all traces (i.e. *.prv) and sorts them by the number of processes
    trace_list = get_traces_from_args(cmdl_args)

    #Analyse the traces and gathers the raw input data
    raw_data = gather_raw_data(trace_list)
    if (debug):
        print_raw_data_table(raw_data, trace_list)

    #Compute the model factors and print them
    mod_factors = compute_model_factors(raw_data, trace_list)
    print_mod_factors_table(mod_factors, trace_list)
    print_mod_factors_csv(mod_factors, trace_list)



