# modelfactors.py

Generates basic performance metrics based on a set of input traces.

## Installation

There is no installation required. Just copy the content of this folder to your
preferred location and add the directory to the PATH environment variable.

## Prerequisites

This script relies on *paramedir* and *Dimemas* being installed and available
through the PATH environment variable.

* *paramedir* available at https://tools.bsc.es/paraver
* *Dimemas* available at https://tools.bsc.es/dimemas

If not already done, install both tools and add them to the PATH environment
variable with:

```
export PATH=<paraver-install-dir>/bin:$PATH
export PARAVER_HOME=<paraver-install-dir>
export PATH=<dimemas-install-dir>/bin:$PATH
export DIMEMAS_HOME=<dimemas-install-dir>

```

## Usage example

Usage: modelfactors.py <list-of-traces>

The <list-of-traces> accepts any list of files including wild cards and
automatically filters for valid Paraver traces.
