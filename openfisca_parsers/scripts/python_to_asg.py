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
Convert OpenFisca Python source files containing simulation variables
to an OpenFisca ASG (abstract semantic graph)
using the RedBaron library.
"""


import argparse
import logging
import os
import sys

from redbaron import RedBaron

from openfisca_parsers import contexts, rbnodes, visitors
from openfisca_parsers.json_graph import asg_to_json_graph
from openfisca_parsers import show_json


log = logging.getLogger(__name__)


# Parsing functions


def visit_variable_class_rbnodes(variable_class_rbnodes, context, on_parse_error, source_file_path):
    for variable_class_rbnode in variable_class_rbnodes:
        variable_name = variable_class_rbnode.name
        try:
            visitors.visit_rbnode(variable_class_rbnode, context)
        except (AssertionError, NotImplementedError) as exc:
            if on_parse_error == 'hide':
                pass
            else:
                message = u'Error parsing OpenFisca Variable "{}" at {}:{}'.format(
                    variable_name,
                    source_file_path,
                    variable_class_rbnode.absolute_bounding_box.top_left.line,
                    )
                if on_parse_error == 'abort':
                    log.error(message)
                    raise
                else:
                    assert on_parse_error == 'show', on_parse_error
                    # log.exception(textwrap.indent(u'{}: {}'.format(message, exc)), '    ')  # Python 3
                    log.exception(u'{}: {}'.format(message, exc))


def parse_source_file(source_file_path, on_parse_error='show', variable_names=None):
    with open(source_file_path) as source_file:
        source_code = source_file.read()
    red = RedBaron(source_code)
    context = contexts.create()
    variable_class_rbnodes = rbnodes.find_all_variable_classes(red, names=variable_names)
    visit_variable_class_rbnodes(variable_class_rbnodes, context, on_parse_error, source_file_path)
    return context


# Main function for script


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source_file_path', help=u'Path of the Python source file to parse')
    parser.add_argument('--on-parse-error', choices=['hide', 'abort', 'show'], default='show',
                        help=u'What to do in case of error while parsing a Variable')
    parser.add_argument('--no-module-node', action='store_true', default=False,
                        help="Do not include a Module node in the ASG. Helps graph visualization.")
    parser.add_argument('--no-python-variables', action='store_true', default=False,
                        help="Do not include PythonVariableDeclaration nodes in the ASG. Helps graph visualization.")
    parser.add_argument('--variable', dest='variable_names', metavar='VARIABLE',
                        nargs='+', help=u'Parse only this simulation Variable(s)')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    context = parse_source_file(
        args.source_file_path,
        on_parse_error=args.on_parse_error,
        variable_names=args.variable_names,
        )
    variable_ofnodes = context['variable_by_name'].values()
    pyvariable_ofnodes = context['pyvariables']
    ofnodes = variable_ofnodes
    if not args.no_python_variables:
        ofnodes += pyvariable_ofnodes
    if args.no_module_node:
        json_graph = asg_to_json_graph(ofnodes)
    else:
        module_ofnode = {
            'type': 'Module',
            'name': os.path.basename(args.source_file_path),
            'variables': ofnodes,
            }
        json_graph = asg_to_json_graph(module_ofnode)
    show_json(json_graph)

    return 0


if __name__ == "__main__":
    sys.exit(main())
