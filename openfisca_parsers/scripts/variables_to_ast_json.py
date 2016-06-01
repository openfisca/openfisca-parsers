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


"""Convert Python formulas to JSON using RedBaron."""


import argparse
import json
import logging
import sys

from redbaron import RedBaron

from openfisca_parsers import navigators, visitors


# Helpers


def show_ofnodes(ofnodes):
    print(json.dumps(ofnodes, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8'))


# Parsing functions


def parse_string(source_code, variable_name=None):
    def iter_ofnodes(rbnodes):
        for rbnode in rbnodes:
            variable_name = rbnode.name
            try:
                ofnode = visitors.visit_rbnode(rbnode, context)
            except NotImplementedError as exc:
                print u'Error parsing OpenFisca Variable "{}": {}'.format(variable_name, exc)
            yield ofnode

    red = RedBaron(source_code)
    context = visitors.make_initial_context()
    if variable_name is None:
        variable_class_rbnodes = navigators.find_all_variable_classes(red)
        ofnodes = list(iter_ofnodes(variable_class_rbnodes))
    else:
        variable_class_rbnode = navigators.find_variable_class(red, variable_name)
        ofnodes = [visitors.visit_rbnode(variable_class_rbnode, context)]
    return ofnodes


# Main function for script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_file_path', help=u'Path of the Python source file to parse')
    parser.add_argument('--variable', dest='variable_name', help=u'Parse only this simulation Variable')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    with open(args.source_file_path) as source_file:
        source_code = source_file.read()

    ofnodes = parse_string(source_code, args.variable_name)
    show_ofnodes(ofnodes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
