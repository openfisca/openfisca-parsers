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


"""Convert parameters of formulas to variables computed inside their formula."""


import argparse
import codecs
import copy
import importlib
import inspect
import itertools
import lib2to3.pgen2.driver  # , tokenize, token
import lib2to3.pygram
import lib2to3.pytree
import logging
import os
import sys

from openfisca_core import conv, formulas, formulas_parsers_2to3


app_name = os.path.splitext(os.path.basename(__file__))[0]
log = logging.getLogger(app_name)
symbols = formulas_parsers_2to3.symbols
type_symbol = formulas_parsers_2to3.type_symbol
tokens = formulas_parsers_2to3.tokens


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
        # if issubclass(column_formula_class, formulas.AlternativeFormula):
        #     continue  # TODO
        elif issubclass(column_formula_class, formulas.DatedFormula):
            pass
        # elif issubclass(column_formula_class, formulas.SelectFormula):
        #     continue  # TODO
        else:
            assert issubclass(column_formula_class, formulas.SimpleFormula), column_formula_class

        print column.name
        state.column = column

        formula_class_wrapper = conv.check(state.FormulaClassFileInput.parse)(column_formula_class, state = state)
        if issubclass(column_formula_class, formulas.DatedFormula):
            function_functions = []
            for name, value in formula_class_wrapper.value_by_name.iteritems():
                if isinstance(value, state.Decorator) and value.name == u'dated_function':
                    function_function = value.decorated
                    assert isinstance(function_function, state.Function)
                    assert name.startswith('function_') or name == 'function', name
                    function_functions.append(function_function)
        else:
            assert issubclass(column_formula_class, formulas.SimpleFormula), column_formula_class
            function_functions = [formula_class_wrapper.value_by_name['function']]

        get_output_period_function = formula_class_wrapper.get_value_by_name('get_output_period', default = None,
            state = state)
        if get_output_period_function is None:
            print 'Skipping variable without get_output_period method.'
            continue
        assert get_output_period_function.node.type == symbols.funcdef
        suite = get_output_period_function.node.children[4]
        assert suite.type == symbols.suite
        period_text = unicode(suite).strip()
        assert period_text.startswith('return ')
        period_text = period_text.replace(u'return ', 'period = ', 1)
        # Remove method get_output_period from Python source file.
        main_source_lines, main_line_number = inspect.getsourcelines(column_formula_class)
        function_line_number = get_output_period_function.node.get_lineno()
        function_lines_count = len(unicode(get_output_period_function.node).strip().split(u'\n'))
        function_first_line_number = main_line_number - 1 + function_line_number
        function_after_line_number = function_first_line_number + function_lines_count
        module = inspect.getmodule(column_formula_class)
        source_file_path = module.__file__
        if source_file_path.endswith('.pyc'):
            source_file_path = source_file_path[:-1]
        source_lines = source_lines_by_path.get(source_file_path)
        if source_lines is None:
            with codecs.open(source_file_path, "r", encoding = 'utf-8') as source_file:
                source_text = source_file.read()
                source_lines_by_path[source_file_path] = source_lines = source_text.split(u'\n')
        source_lines[function_first_line_number - 1:function_after_line_number - 1] = [None] * function_lines_count

        for function_function in function_functions:
            assert function_function.node.type == symbols.funcdef
            colon_node = function_function.node.children[3]
            assert colon_node.type == tokens.COLON
            comment = function_function.node.children[3].get_suffix()
            if comment:
                comment = comment.decode('utf-8').strip().lstrip('#').lstrip()
                if comment:
                    comment = u'  # ' + comment
            variables_name = [
                parameter_name
                for parameter_name in function_function.positional_parameters
                if parameter_name not in ('_defaultP', '_P', 'period', 'self')
                ]
            variables_line = []
            for variable_name in variables_name:
                if variable_name.endswith('_holder'):
                    line = u"{} = simulation.compute('{}', period)".format(variable_name,
                        variable_name[:-len('_holder')])
                else:
                    line = u"{} = simulation.calculate('{}', period)".format(variable_name, variable_name)
                variables_line.append(line)
            variables_text = u'        ' + u'\n        '.join(variables_line) if variables_line else u''

            law_node_lines = []
            if '_defaultP' in function_function.positional_parameters:
                law_node_lines.append(
                    u'        _defaultP = simulation.legislation_at(period.start, reference = True)\n')
            if '_P' in function_function.positional_parameters:
                law_node_lines.append(u'        _P = simulation.legislation_at(period.start)\n')
            law_node_by_name = {
                name: value
                for name, value in function_function.named_parameters.iteritems()
                }
            law_node_by_name = copy.deepcopy(function_function.named_parameters)
            for parameter_name, law_node in sorted(law_node_by_name.iteritems()):
                law_node_path = unicode(law_node).strip()
                assert law_node_path.startswith(u'law')
                law_node_path = law_node_path[len(u'law'):]
                law_node_lines.append(u'        {} = simulation.legislation_at(period.start){}\n'.format(parameter_name,
                    law_node_path))
            law_nodes_text = u''.join(law_node_lines)

            # Replace "return {array}" statements with "return period, {array}".
            if not function_function.returns:
                print "Missing return statement in {}".format(function_function.name)
            for return_wrapper in function_function.returns:
                # print "###{}###{}".format(return_wrapper.node, repr(return_wrapper.node))
                return_children = return_wrapper.node.children
                assert len(return_children) == 2
                return_value = return_children[1]
                del return_value.parent
                return_children[1] = lib2to3.pytree.Node(
                    symbols.testlist,
                    [
                        lib2to3.pytree.Leaf(tokens.NAME, 'period'),
                        lib2to3.pytree.Leaf(tokens.COMMA, ','),
                        return_value
                        ],
                    prefix = ' ',
                    )
                # print "###{}###{}".format(return_wrapper.node, repr(return_wrapper.node))

            suite = function_function.node.children[4]
            assert suite.type == symbols.suite
            body_index = None
            doc_text = u''
            for statement_index, statement in enumerate(suite.children):
                if statement.type in (tokens.INDENT, tokens.NEWLINE):
                    continue
                if statement.type in (symbols.funcdef, symbols.if_stmt):
                    body_index = statement_index
                    break
                assert statement.type == symbols.simple_stmt, type_symbol(statement.type)
                if statement.children:
                    statement_child = statement.children[0]
                    if statement_child.type == tokens.STRING:
                        doc_text = unicode(statement).rstrip() + u'\n        '
                        body_index = statement_index + 1
                        break
                body_index = statement_index
                break
            assert body_index is not None
            body_text = unicode(u''.join(
                unicode(statement)
                for statement in itertools.islice(suite.children, body_index, None)
                )).strip()

            function_text = u"""\
    def {name}(self, simulation, period):{comment}
        {doc}{period}
{variables}
{law_nodes}
        {body}\
""".format(
                body = body_text,
                doc = doc_text,
                comment = comment,
                law_nodes = law_nodes_text,
                name = function_function.name,
                period = period_text,
                variables = variables_text,
                )

            # Replace old method with new method in Python source file.
            function_line_number = function_function.node.get_lineno()
            function_lines_count = len(unicode(function_function.node).strip().split(u'\n'))
            function_first_line_number = main_line_number - 1 + function_line_number
            function_after_line_number = function_first_line_number + function_lines_count
            module = inspect.getmodule(column_formula_class)
            source_file_path = module.__file__
            if source_file_path.endswith('.pyc'):
                source_file_path = source_file_path[:-1]
            source_lines = source_lines_by_path.get(source_file_path)
            if source_lines is None:
                with codecs.open(source_file_path, "r", encoding = 'utf-8') as source_file:
                    source_text = source_file.read()
                    source_lines_by_path[source_file_path] = source_lines = source_text.split(u'\n')
            source_lines[function_first_line_number - 1:function_after_line_number - 1] = [function_text] \
                + [None] * (function_lines_count - 1)

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
