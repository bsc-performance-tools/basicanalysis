# Installation

There is no installation required. Just copy the content of this folder to your
preferred location and add the directory to the PATH environment variable.

## Prerequisites

Basicanalysis requires Python 3 and relies on 
*paramedir* and *Dimemas* being installed and available
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

Additionally, plotting relies on the according SciPy(>= 0.17.0),
NumPy, pandas, searborn and matplotlib (>= 3.x) modules for Python 3.
Furthermore, the gnuplot output requires gnuplot version 5.0 or higher.
