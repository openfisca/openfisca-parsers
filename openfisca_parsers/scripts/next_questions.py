#! /usr/bin/env python
# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014 OpenFisca Team
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


"""Find next questions to ask to user by inspecting the abstract syntax tree of formula to calculate."""


import argparse
import importlib
import logging
import os
import sys

from openfisca_core import conv, formulas, formulas_parsers_ast


app_name = os.path.splitext(os.path.basename(__file__))[0]
log = logging.getLogger(app_name)


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    # parser.add_argument('variable', help = u'Name of the variable to calculate. Example: "revdisp"')
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'Name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)
    TaxBenefitSystem = country_package.init_country()
    tax_benefit_system = TaxBenefitSystem()
    state = formulas_parsers_ast.State()
    state.tax_benefit_system = tax_benefit_system

    for column in tax_benefit_system.column_by_name.itervalues():
        formula_class = column.formula_class
        if formula_class is None:
            # Input variable
            continue
        if issubclass(formula_class, formulas.AbstractEntityToEntity):
            # EntityToPerson or PersonToEntity converters
            continue
        if issubclass(formula_class, formulas.AlternativeFormula):
            formulas_class = formula_class.alternative_formulas_class
        elif issubclass(formula_class, formulas.DatedFormula):
            formulas_class = [
                dated_formula_class['formula_class']
                for dated_formula_class in formula_class.dated_formulas_class
                ]
        elif issubclass(formula_class, formulas.SelectFormula):
            formulas_class = [
                select_formula_class
                for select_formula_class in formula_class.formula_class_by_main_variable_name.itervalues()
                ]
        else:
            assert issubclass(formula_class, formulas.SimpleFormula), formula_class
            formulas_class = [formula_class]
        for formula_class in formulas_class:
            # source_lines, line_number = inspect.getsourcelines(formula_class)
            state.column = column
            print column.name
            if column.name in (
                    'cotsoc_noncontrib',
                    'scelli',
                    'zone_apl',
                    ):
                # TODO
                continue
            formula_function_definition = conv.check(state.FormulaFunctionModule.parse)(formula_class.function, state)
            conv.check(formula_function_definition.call_formula)(state)
            # print function_visitor.input_variable_by_name

    return 0


if __name__ == "__main__":
    sys.exit(main())
