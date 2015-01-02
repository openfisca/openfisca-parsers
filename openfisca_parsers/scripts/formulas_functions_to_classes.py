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


"""Convert Python formulas defined as functions to new syntax using classes."""


import argparse
import codecs
import importlib
import inspect
import itertools
import lib2to3.pgen2.driver  # , tokenize, token
import lib2to3.pygram
import lib2to3.pytree
import logging
import os
import sys
import textwrap

from openfisca_core import columns, conv, formulas, formulas_parsers_2to3


app_name = os.path.splitext(os.path.basename(__file__))[0]
log = logging.getLogger(app_name)
symbols = formulas_parsers_2to3.symbols
tokens = formulas_parsers_2to3.tokens


def extract_formula_function_infos(function, state = None):
    formula_function = conv.check(state.FormulaFunctionFileInput.parse)(function,
        state = state)
    definition_colon_node = formula_function.node.children[3]
    assert definition_colon_node.type == tokens.COLON
    comment = formula_function.node.children[3].get_suffix()
    if comment:
        comment = comment.decode('utf-8').strip().lstrip('#').lstrip()
        if comment:
            comment = u'  # ' + comment
    parameters_text = u', '.join(itertools.chain(
        [u'self'],
        (
            parameter_name
            for parameter_name in formula_function.positional_parameters
            if parameter_name != 'self'
            ),
        (
            u'{} = {}'.format(parameter_name, parameter_value)
            for parameter_name, parameter_value in formula_function.named_parameters.iteritems()
            if parameter_name != 'self'
            ),
        ))
    suite_node = formula_function.node.children[4]
    assert suite_node.type == symbols.suite
    body_text = u'        ' + '\n    '.join(textwrap.dedent(unicode(suite_node).strip()).split('\n'))

    return dict(
        body = body_text,
        comment = comment,
        parameters = parameters_text,
        )


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    # parser.add_argument('variable', help = u'Name of the variable to calculate. Example: "revdisp"')
    parser.add_argument('-c', '--country-package', default = 'openfisca_france',
        help = u'Name of the OpenFisca package to use for country-specific variables & formulas')
    parser.add_argument('-v', '--verbose', action = 'store_true', default = False, help = "increase output verbosity")
    parser.add_argument('-w', '--write', action = 'store_true', default = False,
        help = "replace content of source files")
    args = parser.parse_args()
    logging.basicConfig(level = logging.DEBUG if args.verbose else logging.WARNING, stream = sys.stdout)

    country_package = importlib.import_module(args.country_package)
    TaxBenefitSystem = country_package.init_country()
    tax_benefit_system = TaxBenefitSystem()
    state = formulas_parsers_2to3.State(
        driver = lib2to3.pgen2.driver.Driver(lib2to3.pygram.python_grammar, convert = lib2to3.pytree.convert,
            logger = log),
        tax_benefit_system = tax_benefit_system,
        )

    source_lines_by_path = {}
    for column in tax_benefit_system.column_by_name.itervalues():
        column_formula_class = column.formula_class
        if column_formula_class is None:
            # Input variable
            continue
        if issubclass(column_formula_class, formulas.AbstractEntityToEntity):
            # EntityToPerson or PersonToEntity converters
            continue
        if issubclass(column_formula_class, formulas.AlternativeFormula):
            continue  # TODO
            formula_column_class_name = u'AlternativeFormulaColumn'
        elif issubclass(column_formula_class, formulas.DatedFormula):
            formula_column_class_name = u'DatedFormulaColumn'
        elif issubclass(column_formula_class, formulas.SelectFormula):
            continue  # TODO
            formula_column_class_name = u'SelectFormulaColumn'
        else:
            assert issubclass(column_formula_class, formulas.SimpleFormula), column_formula_class
            formula_column_class_name = u'SimpleFormulaColumn'

        try:
            source_lines, line_number = inspect.getsourcelines(column_formula_class)
        except IOError:
            # IOError: could not find class definition. The formula is defined using obsolete build_..._formula
            # function.
            pass
        else:
            # Skip classes build using ...FormulaColumn classes.
            continue

        print column.name
        state.column = column

        for attribute_name, attribute_value in column.__dict__.iteritems():
            assert attribute_name in (
                'cerfa_field',
                'default',
                'end',
                'entity',
                'entity_key_plural',
                'enum',
                'formula_class',
                'label',
                'name',
                'start',
                'url',
                ), "Unexpected attribute {} = {} in column".format(attribute_name, attribute_value)
        default_text = column.default if column.default is not None else None
        if isinstance(column, columns.EnumCol):
            item_first_index = iter(column.enum).next()[1]
            items = u'\n'.join(
                u'            "{}",'.format(item_key)
                for item_key, item_index in column.enum
                )
            column_text = u"""{name}({default}enum = Enum(
        [
{items}
            ],
        {start}))""".format(
                default = u'default = {}, '.format(default_text) if default_text is not None else u'',
                items = items,
                name = column.__class__.__name__,
                start = u'start = {},\n        '.format(item_first_index) if item_first_index > 0 else u'',
                )
        elif default_text is not None:
            column_text = u'{name}(default = {default})'.format(
                default = default_text,
                name = column.__class__.__name__,
                )
        else:
            column_text = unicode(column.__class__.__name__)
        label = column.label
        label_text = u'u"""{}"""'.format(label) if u'"' in label else u'u"{}"'.format(label)

        attributes = []
        if column.cerfa_field is not None:
            TODO  # Handle non-string Cerfa fields.
            attributes.append((u'cerfa_field', u'"{}"'.format(column.cerfa_field)))
        attributes.append((u'column', column_text))
        attributes.append((u'entity_class',
            tax_benefit_system.entity_class_by_key_plural[column.entity_key_plural].__name__))
        attributes.append((u'label', label_text))
        if column.start is not None:
            attributes.append((u'start_date', u"date({}, {}, {})".format(column.start.year, column.start.month,
                column.start.day)))
        if column.end is not None:
            attributes.append((u'stop_date', u"date({}, {}, {})".format(column.end.year, column.end.month,
                column.end.day)))
        if column.url is not None:
            attributes.append((u'url', u'"{}"'.format(column.url)))

        formula_column_text = u"""\
@reference_formula
class {name}({class_name}):
{attributes}""".format(
            attributes = u''.join(
                u'    {} = {}\n'.format(name, value)
                for name, value in attributes
                ),
            class_name = formula_column_class_name,
            name = column.name,
            )

        if issubclass(column_formula_class, formulas.AlternativeFormula):
            TODO
            formulas_function = [
                formula_class.function
                for formula_class in column_formula_class.alternative_formulas_class
                ]
        elif issubclass(column_formula_class, formulas.DatedFormula):
            formulas_function = []
            for dated_formula_class in column_formula_class.dated_formulas_class:
                formula_function = dated_formula_class['formula_class'].function
                formula_function_infos = extract_formula_function_infos(formula_function, state = state)
                start_date = dated_formula_class['start_instant'].date
                start_triple = (start_date.year, start_date.month, start_date.day)
                stop_date = dated_formula_class['stop_instant'].date
                stop_triple = (stop_date.year, stop_date.month, stop_date.day)
                formula_column_text += u"""
    @dated_function(start = date{start_triple}, stop = date{stop_triple})
    def function_{start_name}_{stop_name}({parameters}):{comment}
{body}
""".format(
                    start_name = u'{:04d}{:02d}{:02d}'.format(*start_triple),
                    start_triple = start_triple,
                    stop_name = u'{:04d}{:02d}{:02d}'.format(*stop_triple),
                    stop_triple = stop_triple,
                    **formula_function_infos)
                formulas_function.append(formula_function)
        elif issubclass(column_formula_class, formulas.SelectFormula):
            TODO
            formulas_function = [
                select_formula_class.function
                for select_formula_class in column_formula_class.formula_class_by_main_variable_name.itervalues()
                ]
        else:
            assert issubclass(column_formula_class, formulas.SimpleFormula), column_formula_class
            formula_function_infos = extract_formula_function_infos(column_formula_class.function, state = state)
            formula_column_text += u"""
    def function({parameters}):{comment}
{body}
""".format(**formula_function_infos)
            formulas_function = [column_formula_class.function]

        formula_column_text += u"""
    def get_output_period(self, period):
        return period.start.offset('first-of', 'month').period('year')
"""

        if args.verbose:
            print formula_column_text

        for formula_function_index, formula_function in enumerate(formulas_function):
            module = inspect.getmodule(formula_function)
            source_file_path = module.__file__
            if source_file_path.endswith('.pyc'):
                source_file_path = source_file_path[:-1]
            function_source_lines, line_number = inspect.getsourcelines(formula_function)
            source_lines = source_lines_by_path.get(source_file_path)
            if source_lines is None:
                with codecs.open(source_file_path, "r", encoding = 'utf-8') as source_file:
                    source_text = source_file.read()
                    source_lines_by_path[source_file_path] = source_lines = source_text.split(u'\n')
            if formula_function_index == 0:
                source_lines[line_number - 1:line_number - 1 + len(function_source_lines)] = [formula_column_text] \
                    + [None] * (len(function_source_lines) - 1)
            else:
                source_lines[line_number - 1:line_number - 1 + len(function_source_lines)] \
                    = [None] * len(function_source_lines)

    if args.write:
        for source_file_path, source_lines in source_lines_by_path.iteritems():
            with codecs.open(source_file_path, "w", encoding = 'utf-8') as source_file:
                source_file.write(u'\n'.join(
                    line
                    for line in source_lines
                    if line is not None
                    ))

    return 0


if __name__ == "__main__":
    sys.exit(main())
