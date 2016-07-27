#! /usr/bin/env python
# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015, 2016 OpenFisca Team
# https://github.com/openfisca
#
# This file is part of OpenFisca.
#
# OpenFisca is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# OpenFisca is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""
Convert M language AST to a graph.
"""


import argparse
import json
import logging
import os
import sys

from toolz.curried import assoc, concat, filter, get, groupby, pipe, pluck, valmap

from openfisca_parsers.json_graph import asg_to_json_graph
from openfisca_parsers import show_json


log = logging.getLogger(__name__)


# Helpers

def is_node(node):
    return isinstance(node, dict) and 'type' in node


# Transform functions

def filter_application(application_name):
    def transform(root_node):
        new_regles = list(filter(
            lambda regle: application_name in regle['applications'],
            root_node['regles'],
            ))
        return assoc(root_node, 'regles', new_regles)
    return transform


def resolve_symbols(root_node):
    def transform(node, path):
        if isinstance(node, list):
            for index, item in enumerate(node):
                transform(item, path={'parent': node, 'key': index})
        elif is_node(node):
            if node['type'] == 'symbol':
                formula_node = formula_node_by_name.get(node['value'])
                if formula_node is None:
                    log.warning(u'Formula "{}" not found'.format(node['value']))
                else:
                    # log.warning(u'Formula "{}" found'.format(node['value']))
                    path['parent'][path['key']] = formula_node
            else:
                for key, value in node.items():
                    transform(value, path={'parent': node, 'key': key})

    formulas = pipe(
        root_node['regles'],
        pluck('formulas'),
        concat,
        filter(lambda node: node['type'] == 'formula'),  # TODO Handle other types, ie `pour_formula`.
        list,
        )
    formula_node_by_name = pipe(
        formulas,
        groupby('name'),
        valmap(get(0)),  # groupby creates lists.
        )
    transformed_node = transform(root_node, path={'parent': None, 'keys': []})
    return transformed_node


# Main function for script


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('m_ast_json_file_path', help=u'Path of the JSON M language AST (example: chap-83.json)')
    parser.add_argument('--no-module-node', action='store_true', default=False,
                        help="Do not include a Module node in the graph, simplify visualization.")
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    with open(args.m_ast_json_file_path) as m_ast_json_file:
        m_ast_str = m_ast_json_file.read()
    regles_nodes = json.loads(m_ast_str)
    module_node = {
        'type': 'Module',
        'name': os.path.basename(args.m_ast_json_file_path),
        'regles': regles_nodes,
        }
    module_node_1 = filter_application('batch')(module_node)
    resolve_symbols(module_node_1)
    json_graph = asg_to_json_graph(
        module_node_1['regles']
        if args.no_module_node
        else module_node_1
        )
    show_json(json_graph)

    return 0


if __name__ == "__main__":
    sys.exit(main())
