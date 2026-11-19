// Views of the left menu: the same views, sections, and guidance as the
// HTML report (report/renderer/html/analysis_catalogue.py and the views of
// interactiveplots.py), built from results.json.
//
// A view is a list of sections:
//   heading   {text}                          h2 of the view
//   guide     {paragraphs}                    "How to read this view" (collapsed)
//   text      {paragraphs}                    paragraphs
//   note      {title, paragraphs}             analysis focus/scope (small, yellow)
//   list      {intro, items, outro}           diagnostic path
//   run       {}                              command and trace mode
//   table     {table, title}                  results.overview tables
//   model     {modelId, include, exclude, title}  efficiency table
//   interpretation {}                         colour scale and guidance
//   paraver   {}                              recommended Paraver views
//   scalingModel {}                           scaling model of the run
//   plot      {title, description, series, ideal, yTitle}

function hasModel(results, id) {
  return results.models.some((m) => m.id === id);
}

function metricOf(results, modelId, key) {
  const model = results.models.find((m) => m.id === modelId);
  return model && model.metrics.find((m) => m.key === key);
}

export function hasValues(results, modelId, key) {
  const metric = metricOf(results, modelId, key);
  return !!metric && results.traces.some((t) => typeof metric.values[t.id] === 'number');
}

/** Name of the runtime of the traces, as in the report (MPI, CUDA...). */
export function runtimeName(results) {
  const trace = results.traces[0] || {};
  if (String(trace.mode || '').startsWith('nsys2prv')) return 'CUDA';
  return trace.display_mode || 'Runtime';
}

/** Title of the Runtime Model: "Hybrid (MPI+OpenMP)", or the runtime. */
export function runtimeModelTitle(results) {
  const name = runtimeName(results);
  if (hasModel(results, 'hybrid') && name.startsWith('MPI+')) return `Hybrid (${name})`;
  return name;
}

// The runtime table of a single-runtime model (MPI, OpenMP, CUDA) is the
// Parallel Efficiency branch of the Application model, as in the report;
// the Application table does not list Serialization and Transfer.
const RUNTIME_KEYS = new Set(['parallel_eff', 'load_balance', 'comm_eff', 'serial_eff', 'transfer_eff']);
const NOT_IN_APPLICATION = new Set(['serial_eff', 'transfer_eff']);
const SM_CHAIN = new Set(['dev_hwc_sm_utilization', 'dev_hwc_sm_coverage', 'dev_hwc_sm_issue_eff']);
const isIo = (key) => key === 'io_eff' || key.startsWith('io_');

const METRIC_DETAILS = 'Metric details: click any metric to see its definition, interpretation, '
  + 'and the recommended deeper analysis (on the right).';

const s = (modelId, key, label) => ({ modelId, key, label });

function plot(title, description, series, extra) {
  return { type: 'plot', title, description, series, ...(extra || {}) };
}

export function buildViews(results) {
  const views = [];
  const hybrid = hasModel(results, 'hybrid');
  const runtime = runtimeModelTitle(results);
  const inner = runtimeName(results).replace(/^MPI\+/, '');
  const application = { type: 'model', modelId: 'application', title: 'Application',
                        exclude: (key) => NOT_IN_APPLICATION.has(key) };

  // ------------------------------------------------------------------
  views.push({
    id: 'overview', label: 'Execution Overview', group: 'Analysis',
    sections: [
      { type: 'guide', paragraphs: [
        'BasicAnalysis organizes the performance analysis into complementary views. Start with '
        + 'Execution Overview to verify the analyzed configurations and their general performance '
        + 'characteristics. Then use the analytical views to locate the main sources of efficiency loss.',
        'Within the analytical views, follow the metric hierarchy toward the factors showing the '
        + 'greatest efficiency loss. Click any metric to view its definition, interpretation, and '
        + 'recommended next diagnostic step.',
      ] },
      { type: 'h3', text: 'Trace configuration' },
      { type: 'run' },
      { type: 'table', table: 'trace_configuration' },
      { type: 'h3', text: 'Execution mapping' },
      { type: 'table', table: 'execution_mapping' },
      { type: 'h3', text: 'General metrics' },
      { type: 'model', modelId: 'general', exclude: isIo, title: 'Metric' },
      { type: 'heading', text: 'Validate the analysis in Paraver' },
      { type: 'paraver' },
    ],
  });

  // ------------------------------------------------------------------
  views.push({
    id: 'runtime', label: 'Runtime Model', group: 'Analysis', title: runtime,
    sections: [
      { type: 'guide', paragraphs: [
        'Start with Application Efficiency. Global Efficiency combines losses from Parallel '
        + 'Efficiency and Computation Scalability. Follow the hierarchy toward the factors showing '
        + 'the greatest efficiency loss.',
        hybrid
          ? `For hybrid applications, the ${runtime} table decomposes Parallel Efficiency `
            + `multiplicatively into the Outer (MPI) and Inner (${inner}) levels.`
          : 'For a single parallel runtime, continue from Application Efficiency to the '
            + 'runtime-level Parallel Efficiency hierarchy. Use Load Balance and Communication '
            + 'Efficiency to distinguish workload-distribution problems from communication, '
            + 'synchronization, or runtime overhead.',
        METRIC_DETAILS,
      ] },
      application,
      hybrid
        ? { type: 'model', modelId: 'hybrid', title: runtime }
        : { type: 'model', modelId: 'application', include: (key) => RUNTIME_KEYS.has(key), title: runtime },
      { type: 'interpretation' },
    ],
  });

  // ------------------------------------------------------------------
  if (hasModel(results, 'device') || hasModel(results, 'host')) {
    views.push({
      id: 'heterogeneous', label: 'Heterogeneous Model', group: 'Analysis',
      sections: [
        { type: 'guide', paragraphs: [
          'Use this view to identify where accelerator-related inefficiencies manifest. Analyze '
          + 'the Host and Device domains separately and compare their behavior across the '
          + 'analyzed configurations.',
          'Host and Device are complementary execution domains, not components of a common '
          + 'multiplicative efficiency model. Host Global Efficiency and Device Global Efficiency '
          + 'are independent top-level metrics.',
          'In the Device domain, follow Device Global Efficiency toward Device Parallel Efficiency '
          + 'and Device Computation Scalability. Device Parallel Efficiency separates workload '
          + 'imbalance, device communication, and orchestration losses.',
          'In the Host domain, follow Host Global Efficiency toward Host Parallel Efficiency and '
          + 'Host Computation Scalability. Host Parallel Efficiency distinguishes losses '
          + 'associated with host-side parallel execution and with the offload of work to the device.',
          METRIC_DETAILS,
        ] },
        ...['device', 'host'].filter((id) => hasModel(results, id))
          .map((modelId) => ({ type: 'model', modelId, title: modelId === 'device' ? 'Device' : 'Host' })),
        { type: 'interpretation' },
        { type: 'note', title: 'Analysis focus', paragraphs: [
          'The Heterogeneous Model view identifies where accelerator-related inefficiencies '
          + 'manifest across host execution, the accelerator offload path, and device execution.',
          'Host and Device metrics provide complementary evidence and should not be interpreted '
          + 'as direct decompositions of the runtime-specific metrics shown in the Runtime Model.',
        ] },
      ],
    });
  }

  // ------------------------------------------------------------------
  if (results.models.some((m) => m.id === 'general' && m.metrics.some((x) => isIo(x.key)
      && results.traces.some((t) => typeof x.values[t.id] === 'number')))) {
    views.push({
      id: 'io', label: 'I/O Metrics', group: 'Analysis',
      sections: [
        { type: 'guide', paragraphs: [
          'Examine the contribution and distribution of File I/O activity in the measured execution. '
          + 'I/O Efficiency is decomposed into Data Access Efficiency and File Management Efficiency.',
          METRIC_DETAILS,
        ] },
        { type: 'model', modelId: 'general', include: isIo, title: 'I/O' },
        { type: 'interpretation' },
      ],
    });
  }

  // ------------------------------------------------------------------
  if (hasModel(results, 'gpu_hardware_counters')) {
    views.push({
      id: 'gpu-hwc', label: 'GPU Hardware Counters', group: 'Analysis',
      sections: [
        { type: 'guide', paragraphs: [
          'Start with SM Utilization, the degree to which the SMs issue instructions while the GPU '
          + 'is active (not a fraction of the peak instruction throughput). It is the product of SM '
          + 'Coverage (are the available SMs active?) and SM Issue Efficiency (do the active SMs '
          + 'issue instructions?).',
          'Then follow the Diagnostic path below the indicators: SM Coverage, then SM Issue '
          + 'Efficiency, explained with Achieved Occupancy and the DRAM bandwidth, and finally '
          + 'Tensor Core Activity and the GPC Clock.',
          METRIC_DETAILS,
        ] },
        { type: 'model', modelId: 'gpu_hardware_counters', include: (key) => SM_CHAIN.has(key),
          title: 'GPU Hardware Counters' },
        { type: 'h3', text: 'Indicators' },
        { type: 'text', paragraphs: [
          'Click any indicator to view its definition and interpretation. Indicators are not '
          + 'efficiencies: a higher value is not necessarily better.',
        ] },
        { type: 'model', modelId: 'gpu_hardware_counters', exclude: (key) => SM_CHAIN.has(key),
          title: 'Indicator' },
        { type: 'h3', text: 'Diagnostic path' },
        { type: 'list',
          intro: 'Start from the factors of SM Utilization and use the indicators to formulate '
            + 'hypotheses about the behavior to investigate:',
          items: [
            'Low SM Coverage: part of the SM capacity is inactive while the GPU is active. Check '
            + 'whether the kernels expose enough parallel work (grids with few blocks relative to '
            + 'the number of SMs, or short kernels).',
            'High SM Coverage + low SM Issue Efficiency: the work is distributed over the SMs, but '
            + 'the active SMs often do not issue instructions. Continue with the next steps.',
            'Low Achieved Occupancy together with low SM Issue Efficiency: there may not be enough '
            + 'resident warps to hide latency. Check the grid and block dimensions, registers, and '
            + 'shared memory per block.',
            'If occupancy is sufficient, check the DRAM bandwidth. High DRAM bandwidth makes '
            + 'device-memory behavior a relevant hypothesis; low bandwidth does not exclude memory '
            + 'latency problems.',
            'For workloads expected to use Tensor Cores, low Tensor Core Activity may indicate that '
            + 'they are not being extensively used.',
            'When comparing executions on the same GPU model, a lower GPC Clock may contribute to a '
            + 'performance difference.',
          ],
          outro: 'Low and high are relative: there are no fixed thresholds. The values are '
            + 'execution-level aggregates, so the path indicates what to investigate, not a '
            + 'kernel-level root cause.' },
        plot('SM Utilization Trends',
             'Compare how SM Utilization and its factors evolve across the analyzed execution configurations.',
             [s('gpu_hardware_counters', 'dev_hwc_sm_utilization'),
              s('gpu_hardware_counters', 'dev_hwc_sm_coverage'),
              s('gpu_hardware_counters', 'dev_hwc_sm_issue_eff')], { yTitle: 'Percentage (%)' }),
        { type: 'interpretation' },
      ],
    });
  }

  // ------------------------------------------------------------------
  if (results.traces.length > 1) {
    const scaling = [
      { type: 'guide', paragraphs: [
        'Use this view to understand how performance and efficiency evolve as resources or '
        + 'execution configurations change. Start with the Scaling Overview to verify the scaling '
        + 'model, then compare the measured Speedup and Efficiency with their ideal behavior.',
        'The scalability metrics are computed relative to a reference execution (T1). A value of '
        + '100% indicates no change relative to the reference for that scalability factor.',
        'Continue with the efficiency-factor trends to identify which metrics degrade, remain '
        + 'stable, or improve as the application scales. A degrading factor identifies where to '
        + 'focus the analysis.',
      ] },
      { type: 'heading', text: 'Scaling Overview' },
      { type: 'h3', text: 'Scaling model' },
      { type: 'scalingModel' },
      { type: 'h3', text: 'Performance scaling' },
      { type: 'text', paragraphs: ['Compare measured Speedup and Efficiency with the ideal scaling '
        + 'behavior defined by the selected scaling model.'] },
      { type: 'plotPair', plots: [
        plot('Speedup', '', [s('general', 'speedup', 'Measured')], { ideal: 'speedup', yTitle: 'Speedup (×)' }),
        plot('Efficiency', '', [s('general', 'efficiency', 'Measured')], { ideal: 'efficiency', yTitle: 'Efficiency' }),
      ] },
      { type: 'heading', text: 'Global Efficiency Analysis' },
      plot('Global Efficiency',
           'Compare the evolution of Global Efficiency, Parallel Efficiency, and Computation '
           + 'Scalability across the analyzed configurations.',
           [s('application', 'global_eff'), s('application', 'parallel_eff'), s('application', 'comp_scale')],
           { yTitle: 'Efficiency / Scalability (%)' }),
      plot('Computation Scalability',
           'Compare Computation Scalability and its available IPC, Instruction, and Frequency '
           + 'components across the analyzed configurations.',
           [s('application', 'comp_scale'), s('application', 'ipc_scale'),
            s('application', 'inst_scale'), s('application', 'freq_scale')],
           { yTitle: 'Scalability (%)' }),
      { type: 'heading', text: 'Parallel Efficiency Analysis' },
      plot('Parallel Efficiency',
           'Compare Load Balance and Communication Efficiency to identify which factor contributes '
           + 'most to the evolution of Parallel Efficiency.',
           [s('application', 'parallel_eff'), s('application', 'load_balance'), s('application', 'comm_eff')],
           { yTitle: 'Efficiency (%)' }),
    ];
    if (hybrid) {
      scaling.push(
        plot('Parallel Runtime Contribution',
             'Contribution of each parallel runtime to the Hybrid Parallel Efficiency.',
             [s('hybrid', 'hybrid_eff'), s('hybrid', 'mpi_parallel_eff'), s('hybrid', 'omp_parallel_eff')],
             { yTitle: 'Efficiency (%)' }),
        plot('MPI Parallel Efficiency', 'Factors of the Outer (MPI) level.',
             [s('hybrid', 'mpi_parallel_eff'), s('hybrid', 'mpi_load_balance'), s('hybrid', 'mpi_comm_eff')],
             { yTitle: 'Efficiency (%)' }),
        plot(`${inner} Parallel Efficiency`, `Factors of the Inner (${inner}) level.`,
             [s('hybrid', 'omp_parallel_eff'), s('hybrid', 'omp_load_balance'), s('hybrid', 'omp_comm_eff')],
             { yTitle: 'Efficiency (%)' }),
        plot('MPI Communication Efficiency',
             'MPI Communication Efficiency with its Serialization and Transfer components.',
             [s('hybrid', 'mpi_comm_eff'), s('hybrid', 'serial_eff'), s('hybrid', 'transfer_eff')],
             { yTitle: 'Efficiency (%)' }),
      );
    } else {
      scaling.push(plot('Communication Efficiency',
        'Compare Communication Efficiency with its Serialization and Transfer components.',
        [s('application', 'comm_eff'), s('application', 'serial_eff'), s('application', 'transfer_eff')],
        { yTitle: 'Efficiency (%)' }));
    }
    if (hasModel(results, 'openmp_runtime')) {
      scaling.push(plot('OpenMP Runtime-Specific Efficiency',
        'Direct OpenMP execution metrics: serial execution, imbalance inside parallel regions, and '
        + 'scheduling or fork/join overhead.',
        [s('openmp_runtime', 'omp_talp_parallel_eff'), s('openmp_runtime', 'omp_talp_serial_eff'),
         s('openmp_runtime', 'omp_talp_load_balance'), s('openmp_runtime', 'omp_talp_scheduling_eff')],
        { yTitle: 'Efficiency (%)' }));
    }
    if (hasModel(results, 'device') || hasModel(results, 'host')) {
      scaling.push(
        { type: 'heading', text: 'Heterogeneous Model Analysis' },
        plot('Device Global Efficiency', '',
             [s('device', 'dev_global_eff'), s('device', 'dev_parallel_eff'), s('device', 'dev_comp_scale')],
             { yTitle: 'Efficiency (%)' }),
        plot('Device Parallel Efficiency', '',
             [s('device', 'dev_parallel_eff'), s('device', 'dev_load_balance'),
              s('device', 'dev_comm_eff'), s('device', 'dev_orches_eff')],
             { yTitle: 'Efficiency (%)' }),
        plot('Host Global Efficiency', '',
             [s('host', 'host_global_eff'), s('host', 'host_parallel_eff'), s('host', 'host_comp_scale')],
             { yTitle: 'Efficiency (%)' }),
        plot('Host Parallel Efficiency', '',
             [s('host', 'host_parallel_eff'), s('host', 'mpi_parallel_eff'), s('host', 'dev_offload_eff')],
             { yTitle: 'Efficiency (%)' }),
      );
    }
    scaling.push({ type: 'note', title: 'Analysis scope', paragraphs: [
      'The trends compare each configuration with the reference execution (T1). They show which '
      + 'factors degrade with scale; the tables of the other views give the values, and the '
      + 'deeper analysis explains the causes.',
    ] });
    views.push({ id: 'scaling', label: 'Scaling', group: 'Analysis', sections: scaling });
  }

  // ------------------------------------------------------------------
  if (hybrid) {
    const isOuter = (key) => key.startsWith('mpi_') || key === 'serial_eff' || key === 'transfer_eff';
    const isInner = (key) => key.startsWith('omp_') && !key.startsWith('omp_talp_');
    views.push({
      id: 'outer', label: 'Outer (MPI)', group: 'Runtimes',
      sections: [
        { type: 'guide', paragraphs: ['MPI-specific diagnosis of load imbalance, serialization, '
          + 'and data-transfer overhead.', METRIC_DETAILS] },
        { type: 'model', modelId: 'hybrid', include: isOuter, title: 'Outer (MPI)' },
        { type: 'interpretation' },
      ],
    });
    views.push({
      id: 'inner', label: `Inner (${inner})`, group: 'Runtimes',
      sections: [
        { type: 'guide', paragraphs: [`${inner} contribution derived from the composed MPI+${inner} `
          + `multiplicative runtime model. This is not an isolated ${inner} runtime-specific model.`,
        METRIC_DETAILS] },
        { type: 'model', modelId: 'hybrid', include: isInner, title: `Inner (${inner})` },
        { type: 'model', modelId: 'hybrid_inner_comm' },
        { type: 'interpretation' },
      ],
    });
  }
  if (hasModel(results, 'openmp_runtime')) {
    views.push({
      id: 'openmp-runtime', label: 'OpenMP runtime', group: 'Runtimes',
      title: 'OpenMP Runtime-Specific Analysis',
      sections: [
        { type: 'guide', paragraphs: ['Direct OpenMP execution metrics used to distinguish serial '
          + 'execution, workload imbalance inside parallel regions, and scheduling or fork/join '
          + 'overhead.', METRIC_DETAILS] },
        { type: 'model', modelId: 'openmp_runtime', title: 'OpenMP' },
        { type: 'interpretation' },
      ],
    });
  }
  return views;
}

/** Values of a plot series, in trace order (null when not available). */
export function seriesValues(results, ref) {
  const metric = metricOf(results, ref.modelId, ref.key);
  if (!metric) return null;
  const values = results.traces.map((t) => (typeof metric.values[t.id] === 'number' ? metric.values[t.id] : null));
  return values.some((v) => v !== null) ? { name: ref.label || metric.name, values } : null;
}

/** Ideal Speedup (parallel units relative to the reference) or Efficiency (1),
 *  as in the report. */
export function idealValues(results, kind) {
  if (kind === 'efficiency') return results.traces.map(() => 1.0);
  const units = results.traces.map((t) => Number(t.processes));
  const reference = units[0];
  return units.map((u) => (reference && Number.isFinite(u) ? u / reference : null));
}
