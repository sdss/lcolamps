# lcolamps

![Versions](https://img.shields.io/badge/python->3.10-blue)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Test status](https://github.com/sdss/lcolamps/actions/workflows/test.yml/badge.svg)](https://github.com/sdss/lcolamps/actions/workflows/test.yml)

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
