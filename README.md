# eas-3d-pattern

[![PyPI version](https://img.shields.io/pypi/v/eas-3d-pattern.svg)](https://pypi.org/project/eas-3d-pattern/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/eas-3d-pattern.svg)](https://pypi.org/project/eas-3d-pattern/)
[![PyPI - License](https://img.shields.io/pypi/l/eas-3d-pattern.svg)](https://github.com/Ericsson/eas-3d-pattern/blob/main/LICENSE)
[![Linter: Ruff](https://img.shields.io/badge/Linter-Ruff-blue.svg)](https://github.com/astral-sh/ruff)

eas-3d-pattern is python library to **visualize** and make simple **beam efficiency calculations** on **3D antenna pattern data** which follows the NGMN BASTA schema.


## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install eas-3d-pattern.

```bash
pip install eas-3d-pattern
```

## Usage
```python
from eas_3d_pattern import AntennaPattern, SAMPLE_JSON

pattern = AntennaPattern(SAMPLE_JSON[0], validate=True) # reads a JSON and validates schema
pattern.calculate_beam_efficiency() # Calculates beam efficiency for standard EAS regions
pattern.plot() # plots an interactive heatmap of the normalized antenna pattern
```

### For further examples, please check the [example notebooks](https://github.com/Ericsson/eas-3d-pattern/tree/main/notebooks)


## Resources
*   [NGMN BASTA schema](https://www.ngmn.org/schema/basta/NGMN_BASTA_AA_3drp_JSON_Schema_WP3_0_latest.json)
*   [Example JSON files](https://www.ngmn.org/schema/basta/)
*   [Example of Beam Efficiency Report / EAS Definitions](https://erilink.internal.ericsson.com/eridoc/erl/objectId/09004cffd60af4fb?docno=2%2F0363-KRE2014818%2F21&option=download&format=pdf)

## Features
*   Loads and validates NGMN JSON schema from NGMN homepage (fallback if no internet access)
*   Parses various JSON structures from different sources with ease
*   Beam efficiency calculation
*   Custom rectangular and default sector definitions
*   Interactive visualization of 3D antenna pattern

## To-Do
*   Add tests / CICD
*   Add different calculation methods
*   Add more complex sector shapes
*   Plot sector regions
*   Improve interface to work with multiple JSON files
