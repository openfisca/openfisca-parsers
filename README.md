# OpenFisca Parsers

OpenFisca Parsers is part of the [OpenFisca](http://www.openfisca.fr/) project,
a versatile microsimulation free software.

This repository contains is a bunch of Python and JavaScript (nodejs) scripts which analyze the AST (abstract syntax tree)
of the OpenFisca formulas, transform it to a graph and manipulate that graph.

## Concepts

- AST: Abstract Syntax Tree (see [Wikipedia](https://en.wikipedia.org/wiki/Abstract_syntax_tree))
- ASG: Abstract Semantic Graph (see [Wikipedia](https://en.wikipedia.org/wiki/Abstract_semantic_graph))
- ASG serialization: flatten the ASG in order to avoid displaying the same node many times, using JSON Graph Format.
- JGF: JSON Graph Format (see [spec](https://github.com/jsongraph/json-graph-specification) and [jgf-dot tool](https://github.com/jsongraph/jgf-dot))

Data flow:
```
Python source code → AST (RedBaron) → ASG
M source code → AST (m-language-parser project) → ASG
merge(ASG1, ASG2) → ASG3
ASG → JGF → DOT
```

An ASG should not be printed without being serialized, because each node would be printed as many times as the number of nodes referencing it.
This would lead to nodes duplication. Instead we serialize an ASG using JGF then we print it.

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

Extract the ASG from Python source code and serialize it in JSON Graph Format:

```bash
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py

# Hide parse errors
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --on-parse-error=hide

# Limit to a variable name
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati

# Limit to many variable names
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py --variable isf_imm_bati isf_imm_non_bati
```

Visualize ASG graphically:

```bash
python openfisca_parsers/scripts/python_to_asg.py --no-module-node ~/Dev/openfisca/openfisca-france/**/isf.py | jgfdot | xdot -

# To hide PythonVariableDeclaration nodes in the graph:
python openfisca_parsers/scripts/python_to_asg.py --no-module-node --no-python-variables ~/Dev/openfisca/openfisca-france/**/isf.py | jgfdot | xdot -

# To visualize the graph produced by a unit test:
nosetests -s openfisca_parsers.tests.test_visitors:test_split_by_roles | jgfdot | xdot -

# To save a PDF:
python openfisca_parsers/scripts/python_to_asg.py ~/Dev/openfisca/openfisca-france/**/isf.py | jgfdot | dot -Tpdf -o isf.pdf /dev/stdin
```

## Tests

```bash
nosetests
```
