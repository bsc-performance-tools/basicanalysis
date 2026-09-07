# BasicAnalysis Documentation

This directory contains the user documentation for **BasicAnalysis**, a 
tool that automates the extraction of POP performance metrics from Paraver traces.

The documentation is built with Sphinx and covers the use of BasicAnalysis,
its analysis methodology and metrics, and the interpretation of the generated
performance reports.

## Documentation Structure

The documentation sources are located in the `source/` directory and are
organized into the following main sections:

- **Introduction** — overview and scope of BasicAnalysis.
- **Getting Started** — initial setup and basic usage.
- **Running BasicAnalysis** — command-line usage and analysis options.
- **Staged Workflow** — workflow for performing the analysis in stages.
- **Methodology** — performance-analysis methodology implemented by BasicAnalysis.
- **Metrics** — definitions and interpretation of the reported performance metrics.
- **Performance Report** — structure and use of the interactive performance report.
- **Output** — generated analysis outputs.
- **Limitations** — current limitations of the tool and analysis.

The documentation structure and navigation are defined in `source/index.rst`.

## Building the Documentation

The documentation is generated using **Sphinx** with the
**Read the Docs Sphinx theme**. Some diagrams are generated using
**Graphviz**.

Install the required Python packages if they are not already available:

```bash
pip install sphinx sphinx-rtd-theme
```

Graphviz must also be installed on the system. You can verify the
installation with:

```bash
dot -V
```

To generate the HTML documentation, run from the repository root:

```bash
make html
```

The generated HTML documentation is written to:

```text
build/html/
```

Open the following file in a web browser to view the documentation locally:

```text
build/html/index.html
```

To remove generated documentation files and rebuild from a clean state:

```bash
make clean
make html
```

A PDF version of the User Guide can be generated through the Sphinx
LaTeX builder:

```bash
make latexpdf
```

The generated pdf documentation is written to:

```text
build/latex/
```

Additional Sphinx build targets can be listed with:

```bash
make help
```

## Repository Structure

```text
doc/
├── source/
│   ├── _static/        # Custom styles and static resources
│   ├── images/         # Images used by the User Guide
│   ├── conf.py         # Sphinx configuration
│   ├── index.rst       # Main documentation index
│   └── *.rst           # User Guide sections
├── Makefile            # Sphinx build commands for Unix/Linux
├── make.bat            # Sphinx build commands for Windows
└── README.md
```

The `build/` directory contains generated Sphinx output and is not tracked
in the repository.