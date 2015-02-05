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

        subject = self.subject
        if self.subject.name in ('calculate', 'compute', 'divide_calculate', 'divide_compute', 'get_array',
                'sum_calculate', 'sum_compute'):
            # TODO: Guess input_variable instead of assuming that it is a string with a "value" attribute.
            input_variable = self.positional_arguments[0].value
            # Note: input_variable may be None when parsing salbrut, chobrut & rstbrut.
            if input_variable is not None:
                parser.input_variables.add(input_variable)


class Parser(formulas_parsers_2to3.Parser):
    Call = Call

    def get_input_variables(self, column):
        formula_class = column.formula_class
        if formula_class is None:
            # Input variable
            return None
        if issubclass(formula_class, formulas.AbstractEntityToEntity):
            return set([formula_class.variable_name])
        self.column = column
        self.input_variables = input_variables = set()
        self.FormulaClassFileInput.parse(formula_class, parser = self)
        del self.column
        del self.input_variables
        self.python_module_by_name.clear()
        return input_variables


def setup(tax_benefit_system):
    return Parser(
        driver = lib2to3.pgen2.driver.Driver(lib2to3.pygram.python_grammar, convert = lib2to3.pytree.convert,
            logger = log),
        tax_benefit_system = tax_benefit_system,
        )
