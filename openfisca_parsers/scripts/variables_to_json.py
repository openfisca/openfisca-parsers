#! /usr/bin/env python
# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015 OpenFisca Team
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
import pkg_resources

from redbaron import RedBaron

from openfisca_parsers import navigators, visitors


# Helpers


def show_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8'))


# Parsing functions


def parse_string(source_code):
    red = RedBaron(source_code)
    variable_class_rbnodes = navigators.find_all_variable_classes(red)
    context = {'ofnodes': []}
    ofnodes = [
        visitors.visit_rbnode(rbnode, context)
        for rbnode in variable_class_rbnodes
        ]
    return ofnodes


# Main function for script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # parser.add_argument('file_path', help=u'path of the file to parse')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    openfisca_france_location = pkg_resources.get_distribution('OpenFisca-France').location
    source_file_path = '{}/openfisca_france/model/prelevements_obligatoires/isf.py'.format(openfisca_france_location)
    with open(source_file_path) as source_file:
        source_code = source_file.read()

    ofnodes = parse_string(source_code)
    show_json(ofnodes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
