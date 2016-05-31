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


"""Convert Python formulas to JSON using lib2to3."""


import argparse
import codecs
import collections
import datetime
import importlib
import inspect
import itertools
import json
from pprint import pprint
import lib2to3.pgen2.driver  # , tokenize, token
import lib2to3.pygram
import lib2to3.pytree
import logging
import os
import sys
import textwrap
import traceback

import numpy as np
from openfisca_core import base_functions, formulas

from openfisca_parsers import formulas_parsers_2to3


app_name = os.path.splitext(os.path.basename(__file__))[0]
log = logging.getLogger(app_name)


# Formula-specific classes


class FormulaClass(formulas_parsers_2to3.FormulaClass):
    def to_json(self):
        node = {
            'type': self.__class__.__name__
            }
        node.update(self.__dict__)
        return node


# JSON parser & compiler


class Parser(formulas_parsers_2to3.Parser):
    FormulaClass = FormulaClass


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('json_dir', help = u'path of the directory of the output JSON files')
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-f', '--formula',
        help = u'name of the OpenFisca variable to convert (all are converted by default)')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)
    tax_benefit_system = country_package.init_tax_benefit_system()

    parser = Parser(
        country_package = country_package,
        driver = lib2to3.pgen2.driver.Driver(lib2to3.pygram.python_grammar, convert = lib2to3.pytree.convert,
            logger = log),
        tax_benefit_system = tax_benefit_system,
        )

    json_by_name_by_module_name = {}
    if args.formula:
        columns = [tax_benefit_system.column_by_name[args.formula]]
    else:
        columns = tax_benefit_system.column_by_name.itervalues()
    for column in columns:
        log.debug(u'Converting "{}" to JSON'.format(column.name))
        parser.column = column

        column_formula_class = column.formula_class
        assert column_formula_class is not None

        if issubclass(column_formula_class, formulas.SimpleFormula) and column_formula_class.function is None:
            # Input variable
            # input_variable_definition_julia_source_by_name[column.name] = parser.source_julia_column_without_function()
            continue

        try:
            formula_class_wrapper = parser.FormulaClassFileInput.parse(column_formula_class, parser = parser)
        except:
            # Stop conversion of columns, but write the existing results to JSON files.
            traceback.print_exc()
            break

        try:
            formula_class_json = formula_class_wrapper.to_json()
        except:
            node = formula_class_wrapper.node
            if node is not None:
                print(u"An exception occurred while jsonifying formula {}:\n{}\n\n{}".format(column.name, repr(node),
                    unicode(node).encode('utf-8')))
            raise

        module_name = formula_class_wrapper.containing_module.python.__name__
        assert module_name.startswith('openfisca_france.model.')
        module_name = module_name[len('openfisca_france.model.'):]
        json_by_name_by_module_name.setdefault(module_name, {})[column.name] = formula_class_json

    if args.formula:
        for module_name, json_by_name in json_by_name_by_module_name.iteritems():
            for column_name, formula_class_json in sorted(json_by_name.iteritems()):
                pprint(formula_class_json)
    else:
        for module_name, json_by_name in json_by_name_by_module_name.iteritems():
            json_relative_path = os.path.join(*module_name.split('.')) + '.json'
            json_path = os.path.join(args.json_dir, 'formulas', json_relative_path)
            json_dir = os.path.dirname(json_path)
            if not os.path.exists(json_dir):
                os.makedirs(json_dir)
            with codecs.open(json_path, 'w', encoding = 'utf-8') as json_file:
                json_file.write(json.dumps(json_by_name, indent = 2, sort_keys = True))
            log.debug(u'"{}" written'.format(json_path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
