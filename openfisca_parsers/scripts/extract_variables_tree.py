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


"""Extract and print the location of input & computed variables."""


import argparse
import codecs
import importlib
import logging
import os
import pyclbr
import re
import sys


app_name = os.path.splitext(os.path.basename(__file__))[0]
build_column_re = re.compile(ur'(?ms)build_column\(\s*(?P<quoted_variable_name>[^,]+),')
log = logging.getLogger(app_name)
reference_input_variable_re = re.compile(
    ur'(?ms)reference_input_variable\(.+?name\s*=\s*(?P<quoted_variable_name>[^,)\s]+)')


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-i', '--input', action = 'store_true', default = False, help = "extract input variables")
    parser.add_argument('-o', '--computed', action = 'store_true', default = False, help = "extract computed variables")
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)

    variables_tree = create_variables_tree(country_package, input_variables = args.input,
        computed_variables = args.computed)

    print_variables_node(variables_tree)

    return 0


def create_variables_tree(country_package, input_variables = False, computed_variables = False):

    root_dir = os.path.dirname(country_package.__file__)
    variables_tree = {}

    if input_variables:
        for (dir, directories_name, filenames) in os.walk(root_dir):
            for filename in filenames:
                if filename.endswith('.py'):
                    python_file_path = os.path.join(dir, filename)
                    with codecs.open(python_file_path, encoding = 'utf-8') as python_file:
                        python_source = python_file.read()
                    module_variables_name = []
                    for match in build_column_re.finditer(python_source):
                        quoted_variable_name = match.group('quoted_variable_name')
                        variable_name = quoted_variable_name[1:-1]
                        module_variables_name.append(variable_name)
                    for match in reference_input_variable_re.finditer(python_source):
                        quoted_variable_name = match.group('quoted_variable_name')
                        variable_name = quoted_variable_name[1:-1]
                        module_variables_name.append(variable_name)
                    if module_variables_name:
                        module_path = [
                            module_name
                            for module_name in os.path.splitext(python_file_path)[0][len(root_dir):].split(u'/')
                            if module_name
                            ]
                        variables_node = variables_tree
                        for module_name in module_path:
                            variables_node = variables_node.setdefault('children', {}).setdefault(module_name, {})
                        if 'variables' in variables_node:
                            module_variables_name += variables_node['variables']
                        module_variables_name.sort()
                        variables_node['variables'] = module_variables_name

    if computed_variables:
        TaxBenefitSystem = country_package.init_country()
        tax_benefit_system = TaxBenefitSystem()

        for module_name in sys.modules.keys():
            if module_name.startswith(country_package.__name__) and not module_name.endswith('.__future__'):
                try:
                    class_data_by_name = pyclbr.readmodule(module_name)
                except ImportError:
                    continue
                module_variables_name = []
                for class_name, class_data in class_data_by_name.iteritems():
                    if class_name in tax_benefit_system.column_by_name:
                        module_variables_name.append(class_name)
                if module_variables_name:
                    module_path = [
                        name
                        for name in module_name[len(country_package.__name__):].split(u'.')
                        if name
                        ]
                    variables_node = variables_tree
                    for module_name in module_path:
                        variables_node = variables_node.setdefault('children', {}).setdefault(module_name, {})
                    if 'variables' in variables_node:
                        module_variables_name += variables_node['variables']
                    module_variables_name.sort()
                    variables_node['variables'] = module_variables_name

    return variables_tree


def print_variables_node(variables_node, indent = 0):
    for variable_name in (variables_node.get('variables') or []):
        print '{}{}'.format(u'    ' * indent, variable_name)
    for module_name, module_node in sorted((variables_node.get('children') or {}).iteritems()):
        print '{}* {}'.format(u'    ' * indent, module_name)
        print_variables_node(module_node, indent = indent + 1)


if __name__ == "__main__":
    sys.exit(main())
