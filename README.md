# lcolamps

![Versions](https://img.shields.io/badge/python->3.7-blue)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://readthedocs.org/projects/sdss-lcolamps/badge/?version=latest)](https://sdss-lcolamps.readthedocs.io/en/latest/?badge=latest)
[![Tests Status](https://github.com/sdss/lcolamps/workflows/Test/badge.svg)](https://github.com/sdss/lcolamps/actions)
[![codecov](https://codecov.io/gh/sdss/lcolamps/branch/master/graph/badge.svg)](https://codecov.io/gh/sdss/lcolamps)

A library to control the LCO M2 lamps.

## Installation

In general you should be able to install ``lcolamps`` by doing

```console
pip install sdss-lcolamps
```

To build from source, use

```console
git clone git@github.com:sdss/lcolamps
cd lcolamps
pip install .[docs]
```

## Development

`lcolamps` uses [poetry](http://poetry.eustace.io/) for dependency management and packaging. To work with an editable install it's recommended that you setup `poetry` and install `lcolamps` in a virtual environment by doing

```console
poetry install
```

Pip does not support editable installs with PEP-517 yet. That means that running `pip install -e .` will fail because `poetry` doesn't use a `setup.py` file. As a workaround, you can use the `create_setup.py` file to generate a temporary `setup.py` file. To install `lcolamps` in editable mode without `poetry`, do

```console
pip install --pre poetry
python create_setup.py
pip install -e .
```
