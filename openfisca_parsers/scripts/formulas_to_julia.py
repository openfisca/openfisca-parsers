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


"""Convert Python formulas to Julia using lib2to3."""


import argparse
import codecs
import collections
import datetime
import importlib
import lib2to3.pgen2.driver  # , tokenize, token
import lib2to3.pygram
import lib2to3.pytree
import logging
import os
import sys
import textwrap

import numpy as np
from openfisca_core import formulas

from openfisca_parsers import formulas_parsers_2to3


app_name = os.path.splitext(os.path.basename(__file__))[0]
log = logging.getLogger(app_name)


class FormulaClass(formulas_parsers_2to3.FormulaClass):
    def to_julia(self, state = None):
        return textwrap.dedent(u"""
            {call} do variable, period
              period = MonthPeriod(firstdayofmonth(period.start))
              date = period.start
              if date < Date(2010, 1, 1)
                array = zeros(variable)
              else
                @divide_year(salaire_imposable, period)
                if date < Date(2011, 1, 1)
                  array = (salaire_imposable .< 500) * 100
                elseif date < Date(2013, 1, 1)
                  array = (salaire_imposable .< 500) * 200
                else
                  array = (salaire_imposable .< 500) * 300
                end
              end
              return period, array
            end
            """).format(
            call = column_to_julia_without_function(state = state),
            )


class State(formulas_parsers_2to3.State):
    FormulaClass = FormulaClass


def column_to_julia_without_function(state = None):
    column = state.column
    tax_benefit_system = state.tax_benefit_system

    column_attributes_name = set(column.__dict__.keys())
    unexpected_attributes_name = column_attributes_name.difference((
        'cerfa_field',
        'default',
        'dtype',
        'end',
        'entity',
        'entity_key_plural',
        'enum',
        'formula_class',
        'is_permanent',
        'label',
        'max_length',
        'name',
        'start',
        'url',
        'val_type',
        ))
    assert not unexpected_attributes_name, "Unexpected attributes in column {}: {}".format(column.name,
        ", ".join(sorted(unexpected_attributes_name)))

    cell_type = {
        bool: 'Bool',
        float: 'Float32',
        np.float32: 'Float32',
        np.int16: 'Int16',
        np.int32: 'Int32',
        object: 'UTF8String',
        'datetime64[D]': 'Date',
        '|S5': 'UTF8String',  # TODO
        }.get(column.dtype)
    assert cell_type is not None, "Unexpected dtype in column {}: {}".format(column.name, column.dtype)

    cerfa_field = column.cerfa_field
    if isinstance(cerfa_field, basestring):
        cerfa_field_str = u'"{}"'.format(cerfa_field)
    elif isinstance(cerfa_field, dict):
        cerfa_field_str = u'[{}]'.format(u', '.join(
            u'{} => "{}"'.format(role, field)
            for role, field in sorted(cerfa_field.iteritems())
            ))
    else:
        assert cerfa_field is None
        cerfa_field_str = None

    default = column.__dict__.get('default')
    if default is None:
        default_str = None
    elif default is True:
        default_str = "true"
    elif isinstance(default, datetime.date):
        default_str = u"Date({}, {}, {})".format(default.year, default.month, default.day)
    elif isinstance(default, (float, int)):
        default_str = str(default)
    elif default == '':
        default_str = '""'
    else:
        assert default is None, "Unexpected default value: {} (type: {})".format(default, type(default))

    enum = column.__dict__.get('enum')
    if enum is None:
        values_str = None
    else:
        values_str = u"[\n{}  ]".format(u''.join(
            u'    {} => "{}",\n'.format(index, symbol)
            for index, symbol in sorted(
                (index1, symbol1)
                for symbol1, index1 in enum
                )
            ))

    # max_length = column.__dict__.get('max_length')  TODO?

    start_date = column.start
    stop_date = column.end

    named_arguments = u''.join(
        u'  {},\n'.format(named_argument)
        for named_argument in [
            u'cell_default = {}'.format(default_str) if default_str is not None else None,
            u'cell_format = "{}"'.format(column.val_type) if column.val_type is not None else None,
            u'cerfa_field = {}'.format(cerfa_field_str) if cerfa_field_str is not None else None,
            u"label = {}".format(u'"""{}"""'.format(column.label)
                if u'"' in column.label
                else u'"{}"'.format(column.label)) if column.label not in (u'', column.name) else None,
            # u'max_length = {}'.format(max_length) if max_length is not None else None,  TODO?
            "permanent = true" if column.is_permanent else None,
            u"start_date = Date({}, {}, {})".format(start_date.year, start_date.month,
                start_date.day) if start_date is not None else None,
            u"stop_date = Date({}, {}, {})".format(stop_date.year, stop_date.month,
                stop_date.day) if stop_date is not None else None,
            (u"url = {}".format(u'"""{}"""'.format(column.url)
                if u'"' in column.url
                else u'"{}"'.format(column.url))) if column.url not in (None, u'', column.url) else None,
            u"values = {}".format(values_str) if values_str is not None else None,
            ]
        if named_argument is not None
        )
    if named_arguments:
        named_arguments = u',\n{}'.format(named_arguments)
    return textwrap.dedent(u"""@define_variable({name}, {entity}_definition, {cell_type}{named_arguments})""").format(
        cell_type = cell_type,
        entity = tax_benefit_system.entity_class_by_key_plural[column.entity_key_plural].key_singular,
        name = column.name,
        named_arguments = named_arguments,
        )


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('julia_package_dir', help = u'path of the directory of the OpenFisca Julia package')
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)
    TaxBenefitSystem = country_package.init_country()
    tax_benefit_system = TaxBenefitSystem()
    state = State(
        driver = lib2to3.pgen2.driver.Driver(lib2to3.pygram.python_grammar, convert = lib2to3.pytree.convert,
            logger = log),
        tax_benefit_system = tax_benefit_system,
        )

    input_variable_definition_julia_str_by_name = collections.OrderedDict()
    for column in tax_benefit_system.column_by_name.itervalues():
        print column.name
        state.column = column

        column_formula_class = column.formula_class
        if column_formula_class is None:
            # Input variable
            input_variable_definition_julia_str_by_name[column.name] = column_to_julia_without_function(state = state)
            continue
        if issubclass(column_formula_class, formulas.AbstractEntityToEntity):
            # EntityToPerson or PersonToEntity converters
            continue

        formula_class_wrapper = state.FormulaClassFileInput.parse(column_formula_class, state = state)
        # if issubclass(column_formula_class, formulas.DatedFormula):
        #     function_functions = []
        #     for name, value in formula_class_wrapper.value_by_name.iteritems():
        #         if isinstance(value, state.Decorator) and value.name == u'dated_function':
        #             function_function = value.decorated
        #             assert isinstance(function_function, state.Function)
        #             assert name.startswith('function_') or name == 'function', name
        #             function_functions.append(function_function)
        # else:
        #     assert issubclass(column_formula_class, formulas.SimpleFormula), column_formula_class
        #     function_functions = [formula_class_wrapper.value_by_name['function']]
        print formula_class_wrapper.to_julia(state = state)

    input_variables_julia_path = os.path.join(args.julia_package_dir, 'src', 'input_variables.jl')
    with codecs.open(input_variables_julia_path, 'w', encoding = 'utf-8') as input_variables_julia_file:
        input_variables_julia_file.write(textwrap.dedent(u"""\
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
            """))
        input_variables_julia_file.write(u'\n')
        for input_variable_definition_julia_str in input_variable_definition_julia_str_by_name.itervalues():
            input_variables_julia_file.write(u'\n')
            input_variables_julia_file.write(input_variable_definition_julia_str)
            input_variables_julia_file.write(u'\n')
    return 0


if __name__ == "__main__":
    sys.exit(main())
