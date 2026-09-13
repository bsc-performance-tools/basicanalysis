# Installation

BasicAnalysis does not require a separate installation step. Clone or copy the
repository to the desired location and install the required Python packages.

The BasicAnalysis scripts can be executed directly from the repository.
Alternatively, the repository directory can be added to the `PATH` environment
variable:

```bash
export PATH=<basicanalysis-dir>:$PATH
```

## Prerequisites

BasicAnalysis requires:

* Python 3
* Paraver / `paramedir`
* Dimemas, when simulation-derived communication metrics are required

### Paraver / paramedir

BasicAnalysis uses `paramedir` to extract the performance information required
from Paraver traces.

`paramedir` is distributed as part of Paraver:

https://tools.bsc.es/paraver

The corresponding executable must be available through the `PATH` environment
variable. A typical configuration is:

```bash
export PATH=<paraver-install-dir>/bin:$PATH
export PARAVER_HOME=<paraver-install-dir>
```

### Dimemas

BasicAnalysis uses Dimemas to compute simulation-derived communication metrics,
such as Serialization Efficiency and Transfer Efficiency, for supported
programming models.

Dimemas is available from:

https://tools.bsc.es/dimemas

When Dimemas is used, its executable must be available through the `PATH`
environment variable. A typical configuration is:

```bash
export PATH=<dimemas-install-dir>/bin:$PATH
export DIMEMAS_HOME=<dimemas-install-dir>
```

Dimemas is not required when simulation-derived metrics are not needed.
BasicAnalysis can be executed without Dimemas or with simulation explicitly
disabled using:

```bash
modelfactors.py --skip-simulation <list-of-traces>
```

In these cases, metrics that require Dimemas simulation are reported as
unavailable.

## Python Dependencies

The recommended Python environment can be installed using the
`requirements.txt` file provided with BasicAnalysis:

```bash
pip install -r requirements.txt
```

The requirements file contains the Python packages used for data processing,
analysis, and visualization.

BasicAnalysis can still compute the performance metrics when optional plotting
dependencies are not available, but the corresponding plotting functionality
will be skipped.

## Gnuplot

Gnuplot is required only for Gnuplot-based output. When this output is used,
Gnuplot version 5.0 or later is required.

## Verify the Installation

After configuring the environment, verify that BasicAnalysis is available with:

```bash
modelfactors.py --version
```

You can also display the available command-line options with:

```bash
modelfactors.py --help
```

For detailed information about BasicAnalysis options, workflows, metrics, and
generated output, see the BasicAnalysis User Guide in the `doc/` directory.
