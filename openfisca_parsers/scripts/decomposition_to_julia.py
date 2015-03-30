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


"""Convert XML decomposition to Julia."""


import argparse
import codecs
import importlib
import logging
import os
import sys
import textwrap
import xml.etree

from biryani.baseconv import check
from openfisca_core import decompositionsxml


julia_file_header = textwrap.dedent(u"""\
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
    """)


def transform_julia_list_tree_to_julia_source_code(node, depth = 0):
    indent_level = 2
    return u'{depth}{node[name]} "{node[label]}" "{node[short_label]}" [{node[color]}]{children}\n'.format(
        children = '' if node['children'] is None else u' [\n{inner_children}{depth}]'.format(
            depth = ' ' * indent_level * depth,
            inner_children = ''.join(
                transform_julia_list_tree_to_julia_source_code(child_node, depth + 1)
                for child_node in node['children']
                ),
            ),
        depth = ' ' * indent_level * depth,
        node = node,
        )


def transform_node_xml_json_to_julia_list_tree(node_xml_json):
    children_variables_name = map(transform_node_xml_json_to_julia_list_tree, node_xml_json['NODE']) \
        if node_xml_json.get('NODE') \
        else None
    return {
        'children': children_variables_name,
        'color': node_xml_json.get('color') or u'0,0,0',
        'label': node_xml_json['desc'],
        'name': node_xml_json['code'],
        'short_label': node_xml_json['shortname'],
        }


def xml_to_julia(tax_benefit_system, tree):
    xml_json = check(decompositionsxml.xml_decomposition_to_json)(tree.getroot())
    xml_json = check(decompositionsxml.make_validate_node_xml_json(tax_benefit_system))(xml_json)
    julia_list_tree = transform_node_xml_json_to_julia_list_tree(xml_json)
    julia_source_code = transform_julia_list_tree_to_julia_source_code(julia_list_tree)
    return julia_source_code


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('julia_package_dir', help = u'path of the directory of the OpenFisca Julia package')
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-d', '--decomposition', default = None,
        help = u'file path of the decomposition XML to convert')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)
    TaxBenefitSystem = country_package.init_country()
    tax_benefit_system = TaxBenefitSystem()

    xml_file_path = os.path.join(tax_benefit_system.DECOMP_DIR, tax_benefit_system.DEFAULT_DECOMP_FILE) \
        if args.decomposition is None else args.decomposition
    tree = xml.etree.ElementTree.parse(xml_file_path)
    decomposition_julia = u'default_decomposition = @define_decomposition ' + xml_to_julia(tax_benefit_system, tree)

    julia_path = os.path.join(args.julia_package_dir, 'src', 'decompositions.jl')
    with codecs.open(julia_path, 'w', encoding = 'utf-8') as julia_file:
        julia_file.write(julia_file_header)
        julia_file.write(u'\n\n')
        julia_file.write(
            textwrap.dedent(u"""\
                # Generated by openfisca-parsers script "{script}"
                # From XML decomposition "{xml_source}" in "{country_package}"
                # WARNING: Any manual modification may be lost.
                """.format(
                country_package = args.country_package,
                script = __file__,
                xml_source = os.path.basename(xml_file_path),
                ))
            )
        julia_file.write(u'\n\n')
        julia_file.write(decomposition_julia)

    return 0


if __name__ == "__main__":
    sys.exit(main())
