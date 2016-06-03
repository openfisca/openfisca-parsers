# OpenFisca Parsers

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
pip install --editable .
```

## Using

Run the parser:

```
python openfisca_parsers/scripts/variables_to_json.py ~/Dev/openfisca/openfisca-france/**/isf.py

# Hide parse errors
python openfisca_parsers/scripts/variables_to_json.py ~/Dev/openfisca/openfisca-france/**/isf.py --on-parse-error=hide

# Limit to a variable name
python openfisca_parsers/scripts/variables_to_json.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati

# Limit to many variable names
python openfisca_parsers/scripts/variables_to_json.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati isf_imm_non_bati
```

Normalize the AST JSON output by the parser:

```
npm run normalize isf_imm_bati.json
```

Parse and normalize and display both:

```
python openfisca_parsers/scripts/variables_to_ast_json.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati | tee /dev/tty | npm run normalize
```

Visualize graph:

```
# First install dependencies (under Debian):
sudo apt install xdot
sudo npm install -g jgf-dot

# Then (under the "fish" shell):
xdot (npm run ast_to_graph variable1_normalized.json | jgfdot | psub)

# More complex:
python openfisca_parsers/scripts/variables_to_ast_json.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_non_bati > isf_imm_non_bati.json
xdot (npm run normalize isf_imm_non_bati.json | npm run ast_to_graph | jgfdot | psub)
# For big files:
xdot (npm run normalize isf_imm_non_bati.json | npm run ast_to_graph | jq -c . | jgfdot | psub)

# To save a PDF:
dot -Tpdf -o isf_imm_non_bati.pdf (npm run normalize isf_imm_non_bati.json | npm run ast_to_graph | jgfdot | psub)


```

## Enrich the web API

The [OpenFisca web API](https://github.com/openfisca/openfisca-web-api) outputs more information if OpenFisca Parsers
is installed: see
[Web API introspection with parsers](https://github.com/openfisca/openfisca-web-api#introspection-with-parsers).

## OpenFisca in Julia

OpenFisca Parsers is used in particular to generate dynamically the formulas of the port of OpenFisca
in the [Julia language](http://julialang.org/).

For example [OpenFiscaFrance.jl](https://github.com/openfisca/OpenFiscaFrance.jl)
