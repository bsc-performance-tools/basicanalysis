#!/usr/bin/env python3

"""Event codes of nsys2prv traces, found in the .pcf of each trace.

The labels, and sometimes the codes, of the events written by nsys2prv
change between nsys2prv versions, Nsight Systems versions and machines
(63000006 was "CUDA kernel" and is now "CUDA kernel execution"; the
hardware counters are numbered 9400, 9401... in the order of the sampled
metric set). The configurations in cfgs/nsys2prv/ select each event by a
reference code. Before the analysis, each event is looked up in the .pcf of
the trace, and the configurations are rewritten with the codes found, without
labels (paramedir drops a filter whose label is not in the .pcf).

An event is found, in this order:

  1. in the user's event map (--nsys2prv-events FILE);
  2. by one of its known labels;
  3. by a label pattern (e.g. "HIP kernel");
  4. by its reference code, when the trace has it and its label is not the
     label of another known event (only the label changed).

The hardware counters are only found by their user map entry, their label
or their label pattern (the name with or without a unit in brackets), never by
code: their codes depend on the metric set.

Event map file: one "name = code" or "name = label" line per event, e.g.

    # my traces from machine X
    kernel = 63000009
    memcpy = "CUDA memcpy kernel"
    gr_active = 9410

Names: kernel, memcpy, nccl, cuda_calls, and the hardware counters
gpc_clock, gr_active, sms_active, sm_issue, tensor_active, warps_in_flight,
unallocated_warps, dram_read, dram_write.
"""

from __future__ import print_function

import os
import re
from collections import OrderedDict, namedtuple


EventSpec = namedtuple('EventSpec', 'code labels pattern description')

# Events with fixed meaning. code: reference code used in cfgs/nsys2prv/.
FIXED_EVENTS = OrderedDict([
    ('kernel', EventSpec(
        63000006, ('CUDA kernel', 'CUDA kernel execution'),
        r'^(cuda|hip)\s+kernel(\s+execution)?$',
        'GPU kernels on the streams (Device useful time)')),
    ('memcpy', EventSpec(
        63000001, ('CUDA memcpy kernel',),
        r'^(cuda|hip)\s+(memcpy|memory\s+(copy|operation))',
        'memory copies and memset on the streams')),
    ('nccl', EventSpec(
        63000007, ('NCCL kernel',),
        r'^(nccl|rccl)\s+kernel',
        'NCCL kernels on the streams')),
    ('cuda_calls', EventSpec(
        63000000, ('CUDA library call',),
        r'^(cuda|hip)\s+(library|runtime|api|driver)\s+call',
        'CUDA runtime and driver calls on the host threads')),
])

# GPU hardware counters (Nsight Systems metric names, via nsys2prv).
# The names depend on the metric set of the GPU: some sets add the unit to the
# name ("GR Active [Throughput %]", "GPC Clock Frequency [MHz]") and some do
# not ("GR Active", "GPC Clock Frequency"); some write "SMs Active" and others
# "SM Active". The pattern of each counter accepts the name with or without a
# unit in brackets. It is anchored to the whole label, so that other counters
# with similar names (e.g. "SYS Clock Frequency") are not taken.
_UNIT = r'(\s*\[[^\]]*\])?$'


def _hwc(code, label, name_regex, description):
    return EventSpec(code, (label,), r'^' + name_regex + _UNIT, description)


HWC_EVENTS = OrderedDict([
    ('gpc_clock', _hwc(9400, 'GPC Clock Frequency [MHz]',
                       r'gpc\s+clock\s+frequency', 'GPC clock')),
    ('gr_active', _hwc(9402, 'GR Active [Throughput %]',
                       r'gr\s+active', 'GR Active')),
    ('sms_active', _hwc(9403, 'SMs Active [Throughput %]',
                        r'sms?\s+active', 'SMs Active')),
    ('sm_issue', _hwc(9404, 'SM Issue [Throughput %]',
                      r'sm\s+issue', 'SM Issue')),
    ('tensor_active', _hwc(9405, 'Tensor Active [Throughput %]',
                           r'tensor\s+active', 'Tensor Active')),
    ('warps_in_flight', _hwc(9412, 'Compute Warps in Flight [Throughput %]',
                             r'compute\s+warps\s+in\s+flight',
                             'Compute Warps in Flight')),
    ('unallocated_warps', _hwc(9415, 'Unallocated Warps in Active SMs [Throughput %]',
                               r'unallocated\s+warps\s+in\s+active\s+sms?',
                               'Unallocated Warps in Active SMs')),
    ('dram_read', _hwc(9418, 'DRAM Read Bandwidth [Throughput %]',
                       r'dram\s+read\s+bandwidth', 'DRAM Read Bandwidth')),
    ('dram_write', _hwc(9419, 'DRAM Write Bandwidth [Throughput %]',
                        r'dram\s+write\s+bandwidth', 'DRAM Write Bandwidth')),
])

ALL_EVENTS = OrderedDict(list(FIXED_EVENTS.items()) + list(HWC_EVENTS.items()))

# Reference code -> event name, to rewrite the cfgs.
EVENT_BY_REFERENCE_CODE = {spec.code: name for name, spec in ALL_EVENTS.items()}

# Kinds of memory operation in the values of the memcpy event, found by the
# value labels ("CUDA memcpy Device-to-Host", "CUDA memset").
MEMORY_VALUE_PATTERNS = OrderedDict([
    ('d2d', r'device.?to.?device|\bdtod\b|peer'),
    ('d2h', r'device.?to.?host|\bdtoh\b'),
    ('h2d', r'host.?to.?device|\bhtod\b'),
    ('memset', r'memset'),
])

# Values used by the nsys2prv versions known so far (also when the .pcf
# has no value labels).
DEFAULT_MEMORY_VALUES = OrderedDict([
    ('d2d', 3), ('d2h', 4), ('h2d', 5), ('memset', 6)])


def _normalize(label):
    return ' '.join(label.split()).lower()


def parse_pcf_event_types(pcf_path):
    """Event types of a .pcf: list of (code, label), in file order.

    A code can appear more than once (nsys2prv has written 9500 for an NVTX
    domain and for a network metric in the same .pcf).
    """
    types = []
    if not pcf_path or not os.path.exists(pcf_path):
        return types

    in_types = False
    with open(pcf_path, errors='replace') as pcf:
        for raw_line in pcf:
            line = raw_line.strip()
            if line == 'EVENT_TYPE':
                in_types = True
                continue
            if not line or line == 'VALUES':
                in_types = False
                continue
            if in_types:
                fields = line.split(None, 2)
                if len(fields) < 2:
                    continue
                try:
                    code = int(fields[1])
                except ValueError:
                    continue
                types.append((code, fields[2].strip() if len(fields) > 2 else ''))
    return types


def read_event_map(path):
    """Read a user event map: {name: code (int) or label (str)}.

    Raises ValueError with the line number on a malformed line or an
    unknown name.
    """
    mapping = OrderedDict()
    with open(path) as map_file:
        for number, raw_line in enumerate(map_file, 1):
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue
            if '=' not in line:
                raise ValueError('{}:{}: expected "name = code" or '
                                 '"name = label"'.format(path, number))
            name, value = (part.strip() for part in line.split('=', 1))
            name = name.lower()
            if name not in ALL_EVENTS:
                raise ValueError('{}:{}: unknown event "{}" (known: {})'.format(
                    path, number, name, ', '.join(ALL_EVENTS)))
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                mapping[name] = value[1:-1]
            else:
                try:
                    mapping[name] = int(value)
                except ValueError:
                    mapping[name] = value
    return mapping


Resolution = namedtuple('Resolution', 'code label how')


def resolve_events(pcf_path, event_map=None):
    """Find the code of each known event in the .pcf of a trace.

    Returns OrderedDict {name: Resolution(code, label, how)}; code is None
    when the event was not found. how is 'event map', 'label',
    'label pattern' or 'reference code'.
    """
    event_map = event_map or {}
    types = parse_pcf_event_types(pcf_path)
    labels_of_code = OrderedDict()
    for code, label in types:
        labels_of_code.setdefault(code, []).append(label)
    code_of_label = {}
    for code, label in types:
        code_of_label.setdefault(_normalize(label), code)

    known_label_owner = {}
    for name, spec in ALL_EVENTS.items():
        for label in spec.labels:
            known_label_owner[_normalize(label)] = name

    result = OrderedDict()
    for name, spec in ALL_EVENTS.items():
        found = None

        if name in event_map:
            wanted = event_map[name]
            if isinstance(wanted, int):
                found = Resolution(wanted, ' / '.join(labels_of_code.get(wanted, [])),
                                   'event map')
            elif _normalize(wanted) in code_of_label:
                code = code_of_label[_normalize(wanted)]
                found = Resolution(code, wanted, 'event map')
            else:
                found = Resolution(None, wanted, 'event map (label not in .pcf)')

        if found is None:
            for label in spec.labels:
                code = code_of_label.get(_normalize(label))
                if code is not None:
                    found = Resolution(code, label, 'label')
                    break

        if found is None and spec.pattern:
            regex = re.compile(spec.pattern, re.IGNORECASE)
            for code, label in types:
                if regex.search(label.strip()):
                    found = Resolution(code, label, 'label pattern')
                    break

        is_fixed = name in FIXED_EVENTS
        if found is None and is_fixed and spec.code in labels_of_code:
            owners = {known_label_owner.get(_normalize(label))
                      for label in labels_of_code[spec.code]} - {None, name}
            if not owners:
                found = Resolution(spec.code,
                                   ' / '.join(labels_of_code[spec.code]),
                                   'reference code')

        result[name] = found or Resolution(None, '', 'not found')

    return result


def resolve_memory_values(value_labels):
    """Values of the memcpy event that are memory operations.

    value_labels: {value: label} of the memcpy event in the .pcf. Returns
    (OrderedDict {kind: value}, how). Without value labels, the values of
    the known nsys2prv versions are used.
    """
    labelled = {value: label for value, label in value_labels.items() if value != 0}
    if not labelled:
        return OrderedDict(DEFAULT_MEMORY_VALUES), 'reference values'

    kinds = OrderedDict()
    for kind, pattern in MEMORY_VALUE_PATTERNS.items():
        regex = re.compile(pattern, re.IGNORECASE)
        for value, label in sorted(labelled.items()):
            if regex.search(label):
                kinds[kind] = value
                break
    if not kinds:
        return OrderedDict(DEFAULT_MEMORY_VALUES), 'reference values'
    return kinds, 'value labels'


def ambiguous_codes(pcf_path, resolution):
    """Codes found for the events that the .pcf also uses for other events."""
    count = {}
    for code, _label in parse_pcf_event_types(pcf_path):
        count[code] = count.get(code, 0) + 1
    return sorted({r.code for r in resolution.values()
                   if r.code is not None and count.get(r.code, 0) > 1})


_FILTER_TYPE_RE = re.compile(r'^(window_filter_module\s+evt_type\s+)(\d+)(\s+)(.*)$')


def rewrite_cfg(text, codes_by_reference):
    """Rewrite the event filters of a Paraver cfg.

    codes_by_reference: {reference code: code in the trace}. The event
    types of every "window_filter_module evt_type" line are replaced, and
    the "window_filter_module evt_type_label" lines are removed.
    """
    lines = []
    for line in text.splitlines(True):
        stripped = line.rstrip('\n')
        if stripped.startswith('window_filter_module evt_type_label'):
            continue
        match = _FILTER_TYPE_RE.match(stripped)
        if match:
            prefix, count, space, codes = match.groups()
            new_codes = []
            for token in codes.split():
                try:
                    code = int(token)
                except ValueError:
                    new_codes.append(token)
                    continue
                new_codes.append(str(codes_by_reference.get(code, code)))
            line = prefix + count + space + ' '.join(new_codes) + '\n'
        lines.append(line)
    return ''.join(lines)


def cfg_reference_codes(text):
    """Event codes selected by the filters of a cfg."""
    codes = set()
    for line in text.splitlines():
        match = _FILTER_TYPE_RE.match(line.strip())
        if match:
            for token in match.group(4).split():
                try:
                    codes.add(int(token))
                except ValueError:
                    pass
    return codes


def format_resolution(resolution, memory_values=None, memory_how=None):
    """Lines describing the events found, for the standard output."""
    lines = []
    for name, found in resolution.items():
        if found.code is None:
            lines.append('    {:<18} not found{}'.format(
                name, ' ("{}")'.format(found.label) if found.label else ''))
        else:
            lines.append('    {:<18} {:<10} "{}" ({})'.format(
                name, found.code, found.label, found.how))
    if memory_values:
        lines.append('    {:<18} {} ({})'.format(
            'memcpy values', ', '.join('{}={}'.format(kind, value)
                                       for kind, value in memory_values.items()),
            memory_how))
    return lines


def translation_table(target_pcf, reference_pcf=None, event_map=None,
                      cfg_codes=()):
    """Codes to rewrite a cfg for the trace of target_pcf.

    Without reference_pcf, the cfg is taken to use the reference codes of
    the known events (63000006 for the kernels...). With reference_pcf (the
    .pcf of a trace the cfg works with), each code of the cfg is translated
    by its event: a known event is found in the target as in the analysis,
    any other event by the same label.

    Returns ({code in cfg: code in target}, [codes of the cfg not found]).
    """
    target = resolve_events(target_pcf, event_map)
    target_types = parse_pcf_event_types(target_pcf)
    target_codes = {code for code, _label in target_types}
    target_by_label = {}
    for code, label in target_types:
        target_by_label.setdefault(_normalize(label), code)

    table = {}
    if reference_pcf:
        reference = resolve_events(reference_pcf)
        for name, found in reference.items():
            if found.code is not None and target[name].code is not None:
                table.setdefault(found.code, target[name].code)
        reference_labels = {}
        for code, label in parse_pcf_event_types(reference_pcf):
            reference_labels.setdefault(code, label)
    else:
        for name, spec in ALL_EVENTS.items():
            if target[name].code is not None:
                table[spec.code] = target[name].code
        reference_labels = {}

    missing = []
    for code in sorted(cfg_codes):
        if code in table:
            continue
        label = reference_labels.get(code)
        if label is not None and _normalize(label) in target_by_label:
            table[code] = target_by_label[_normalize(label)]
        elif code in target_codes and label is None:
            table[code] = code
        else:
            missing.append(code)
    return table, missing


def main(argv=None):
    """Rewrite Paraver cfgs with the event codes of an nsys2prv trace."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Rewrite Paraver cfgs for an nsys2prv trace: the event '
                    'filters get the codes of the events in the .pcf of the '
                    'trace, without labels.')
    parser.add_argument('cfgs', nargs='+', help='cfg files to rewrite')
    parser.add_argument('--pcf', required=True,
                        help='.pcf of the trace the cfgs will be used with')
    parser.add_argument('--reference', metavar='PCF',
                        help='.pcf of a trace the cfgs already work with; '
                             'without it, the cfgs are taken to use the codes '
                             'of the nsys2prv versions known by BasicAnalysis')
    parser.add_argument('--nsys2prv-events', metavar='FILE',
                        help='event map, as in modelfactors.py')
    parser.add_argument('-o', '--output-dir', default=None,
                        help='folder for the rewritten cfgs (default: '
                             'cfgs-<trace name> in the current folder)')
    args = parser.parse_args(argv)

    event_map = read_event_map(args.nsys2prv_events) if args.nsys2prv_events else None
    output_dir = args.output_dir or 'cfgs-' + os.path.basename(args.pcf)[:-len('.pcf')]
    os.makedirs(output_dir, exist_ok=True)

    texts = {}
    cfg_codes = set()
    for path in args.cfgs:
        with open(path) as cfg_file:
            texts[path] = cfg_file.read()
        cfg_codes |= cfg_reference_codes(texts[path])

    table, missing = translation_table(args.pcf, args.reference, event_map,
                                       cfg_codes)
    print('Event codes for {}:'.format(args.pcf))
    for code in sorted(cfg_codes):
        if code in table:
            print('    {:<10} -> {}'.format(code, table[code]))
    if missing:
        print('WARNING: codes of the cfgs not found in the trace (left as '
              'they are): {}'.format(', '.join(str(c) for c in missing)))
    for path, text in texts.items():
        out = os.path.join(output_dir, os.path.basename(path))
        with open(out, 'w') as out_file:
            out_file.write(rewrite_cfg(text, table))
        print('Written ' + out)
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
