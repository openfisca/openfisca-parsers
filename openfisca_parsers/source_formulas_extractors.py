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


"""Extract input variables from Python formulas using lib2to3."""


import lib2to3.pgen2.driver
import lib2to3.pygram
import lib2to3.pytree
import logging

from openfisca_core import formulas

from . import formulas_parsers_2to3


log = logging.getLogger(__name__)


class Call(formulas_parsers_2to3.Call):
    def __init__(self, container = None, hint = None, keyword_argument = None, named_arguments = None, node = None,
            parser = None, positional_arguments = None, star_argument = None, subject = None):
        super(Call, self).__init__(container = container, hint = hint, keyword_argument = keyword_argument,
            named_arguments = named_arguments, node = node, parser = parser,
            positional_arguments = positional_arguments, star_argument = star_argument, subject = subject)

        if self.subject.name in ('calculate', 'calculate_add', 'calculate_add_divide', 'calculate_divide', 'compute',
                'compute_add', 'compute_add_divide', 'compute_divide', 'get_array'):
            # TODO: Guess input_variable instead of assuming that it is a string with a "value" attribute.
            input_variable = self.positional_arguments[0]
            while isinstance(input_variable, parser.Variable):
                input_variable = input_variable.value
            if input_variable is None:
                # print "Missing input variable name while calling {} in {}".format(self.subject.name,
                #     parser.column.name)
                return
            elif isinstance(input_variable, parser.Attribute) and input_variable.name == '__name__':
                # Assume this is "self.__class__.__name__".
                input_variable_name = parser.column.name
                assert input_variable_name is not None
                parser.source_formulas.add(input_variable_name)
                return
            elif isinstance(input_variable, parser.String):
                input_variable_name = input_variable.value
                # Note: input_variable_name may be None when parsing salbrut, chomage_brut & retraite_brute.
                if input_variable_name is not None:
                    parser.source_formulas.add(input_variable_name)
                    return
            assert False, "Unexpected class for input variable: {}".format(input_variable)


class Parser(formulas_parsers_2to3.Parser):
    Call = Call

    def get_source_formulas(self, column):
        formula_class = column.formula_class
        assert formula_class is not None, "Column {} has no formula".format(column.name)
        if issubclass(formula_class, formulas.AbstractEntityToEntity):
            return set([formula_class.variable_name])
        if issubclass(formula_class, formulas.SimpleFormula) and formula_class.function is None:
            # Input variable
            return None
        self.column = column
        self.source_formulas = source_formulas = set()
        try:
            self.FormulaClassFileInput.parse(formula_class, parser = self)
        except AssertionError:
            # When parsing fails, assume that all input variables have already been parsed.
            pass
        del self.column
        del self.source_formulas
        self.python_module_by_name.clear()
        return source_formulas


def extract_source_formulas(tax_benefit_system, name):
    extractor = setup(tax_benefit_system)

    source_formulas = set()
    remaining_names = set([name])
    while remaining_names:
        name = remaining_names.pop()
        column = tax_benefit_system.column_by_name[name]
        new_names = extractor.get_source_formulas(column)
        if new_names is not None:
            source_formulas.add(name)
            for new_name in new_names:
                if new_name not in source_formulas:
                    remaining_names.add(new_name)
    return source_formulas


def setup(tax_benefit_system):
    return Parser(
        driver = lib2to3.pgen2.driver.Driver(lib2to3.pygram.python_grammar, convert = lib2to3.pytree.convert,
            logger = log),
        tax_benefit_system = tax_benefit_system,
        )
