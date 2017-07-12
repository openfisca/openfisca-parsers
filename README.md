# OpenFisca Parsers - DEPRECATED

## This package is deprecated

**This package isn't maintained anymore. It won't evolve, and it is not guaranteed to be compatible with future versions of OpenFisca.**

The aim of this package was to introduce instrospection tools for OpenFisca legislation code, for instance to build a dependency graph between OpenFisca variables.

However, after a few years of existence, it appeared:
  - That the algorithms built were not reliable
  - That the this package, untested and undocumented, was not maintainable
  - That we could find simpler alternatives to this complex introspection
 
## Introduction

OpenFisca Parsers is part of the [OpenFisca](http://www.openfisca.fr/) project,
a versatile microsimulation free software.

This repository contains is a bunch of Python scripts which analyze the AST (abstract syntax tree)
of the OpenFisca formulas.

## Installation

Clone the OpenFisca-Parsers Git repository on your machine and install the Python package.

Assuming you are in an `openfisca` working directory:

```
git clone https://github.com/openfisca/openfisca-parsers.git
cd openfisca-parsers
pip install --editable . --user # Microsoft Windows users must not use the `--user` option
```

## Enrich the web API

The [OpenFisca web API](https://github.com/openfisca/openfisca-web-api) outputs more information if OpenFisca Parsers
is installed: see
[Web API introspection with parsers](https://github.com/openfisca/openfisca-web-api#introspection-with-parsers).

## OpenFisca in Julia

OpenFisca Parsers is used in particular to generate dynamically the formulas of the port of OpenFisca
in the [Julia language](http://julialang.org/).

For example [OpenFiscaFrance.jl](https://github.com/openfisca/OpenFiscaFrance.jl)
