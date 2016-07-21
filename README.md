# OpenFisca Parsers

OpenFisca Parsers is part of the [OpenFisca](http://www.openfisca.fr/) project,
a versatile microsimulation free software.

This repository contains is a bunch of Python scripts which analyze the AST (abstract syntax tree)
of the OpenFisca formulas.

## Concepts

- AST: Abstract Syntax Tree (see [Wikipedia](https://en.wikipedia.org/wiki/Abstract_syntax_tree))
- ASG: Abstract Semantic Graph (see [Wikipedia](https://en.wikipedia.org/wiki/Abstract_semantic_graph))
- ASG normalization: rewrite the graph by flattening the references between entities (see [normalizr](https://github.com/paularmstrong/normalizr))
- NASG: Normalized ASG
- JGF: JSON Graph Format (see [spec](https://github.com/jsongraph/json-graph-specification) and [jgf-dot tool](https://github.com/jsongraph/jgf-dot))

Data flow:
```
Python source → AST → ASG → NASG → JGF → DOT
```

## Installation

This repo relies upon both Python and JavaScript (nodejs) technologies.

```
git clone https://github.com/openfisca/openfisca-parsers.git
cd openfisca-parsers
pip install --editable .
npm install
```

Dependencies for ASG visualization:

```
# First install dependencies (under Debian):
sudo apt install xdot
```

## Using

Extract the AST from Python source code:

```
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py

# Hide parse errors
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --on-parse-error=hide

# Limit to a variable name
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati

# Limit to many variable names
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati isf_imm_non_bati
```

Transform the AST to an ASG:

```
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py > isf.ast.json
npm run ast_to_asg isf.ast.json
```

Visualize ASG:

```
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py | \
  npm run ast_to_asg | npm run asg_to_nasg | npm run nasg_to_jgf | jgfdot > isf.dot
xdot isf.dot

# Or the shortcut:
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py | npm run ast_to_dot > isf.dot
xdot isf.dot

# To draw Python variables as labels in graph:
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --with-pyvariables | npm run ast_to_dot > isf.dot
xdot isf.dot

# To visualize the graph produced by a unit test:
nosetests -s openfisca_parsers.tests.test_visitors:test_split_by_roles | npm run ast_to_dot > isf.dot
xdot isf.dot

# To save a PDF:
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py | npm run ast_to_dot > isf.dot
dot -Tpdf -o isf.pdf isf.dot
```

## Tests

```
$ nosetests
```
