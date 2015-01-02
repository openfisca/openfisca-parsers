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
import traceback

import numpy as np
from openfisca_core import formulas

from openfisca_parsers import formulas_parsers_2to3


app_name = os.path.splitext(os.path.basename(__file__))[0]
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
log = logging.getLogger(app_name)


class AndExpression(formulas_parsers_2to3.AndExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            operands = [
                operand.juliaize()
                for operand in self.operands
                ],
            operator = self.operator,
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u' {} '.format(self.operator).join(
            operand.source_julia(depth = depth)
            for operand in self.operands
            )


class ArithmeticExpression(formulas_parsers_2to3.ArithmeticExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            items = [
                item if item_index & 1 else item.juliaize()
                for item_index, item in enumerate(self.items)
                ],
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u' '.join(
            item if item_index & 1 else item.source_julia(depth = depth)
            for item_index, item in enumerate(self.items)
            )


class Assert(formulas_parsers_2to3.Assert):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            error = self.error.juliaize() if self.error is not None else None,
            guess = self._guess,
            parser = self.parser,
            test = self.test.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u'@assert {test}{error}'.format(
            error = u', {}'.format(self.error.source_julia(depth = depth + 1)) if self.error is not None else u'',
            test = self.test.source_julia(depth = depth + 1),
            )


class Assignment(formulas_parsers_2to3.Assignment):
    def juliaize(self):
        parser = self.parser
        left = []
        for left_item in self.left:
            if isinstance(left_item, parser.Variable) and left_item.value is not None:
                # Convert variables to Julia only once, during assignment.
                left.append(left_item.__class__(
                    container = left_item.container,
                    guess = left_item._guess,
                    name = left_item.name,
                    parser = parser,
                    value = left_item.value.juliaize(),
                    ).juliaize())
            else:
                left.append(left_item.juliaize())
            left_item = left_item.juliaize()
        right = [
            right_item.juliaize()
            for right_item in self.right
            ]
        if len(left) == 1:
            variable = left[0]
            if isinstance(left, parser.Variable) and isinstance(variable.value, parser.Call):
                call = variable.value
                call_subject = call.subject
                if isinstance(call_subject, parser.Attribute):
                    method_name = call_subject.name
                    if method_name == 'calculate':
                        method_subject = call_subject.subject
                        if isinstance(method_subject, parser.Variable) and method_subject.name == 'simulation':
                            assert len(call.positional_arguments) >= 1, call.positional_arguments
                            assert len(call.named_arguments) == 0, call.named_arguments
                            requested_variable_string = call.positional_arguments[0]
                            if isinstance(requested_variable_string, parser.String):
                                assert requested_variable_string.value == variable.name, str((variable.name,
                                    requested_variable_string.value))
                                return parser.Call(
                                    container = self.container,
                                    # guess = parser.ArrayHandle(parser = parser),  TODO
                                    parser = parser,
                                    positional_arguments = [Variable(
                                        container = self.container,
                                        # guess = parser.ArrayHandle(parser = parser),  TODO
                                        name = variable.name,
                                        parser = parser,
                                        )] + call.positional_arguments[1:],
                                    subject = parser.Variable(  # TODO: Use Macro or MacroCall.
                                        name = u'@calculate',
                                        parser = parser,
                                        ),
                                    )
        return self.__class__(
            container = self.container,
            guess = self._guess,
            left = left,
            operator = self.operator,
            parser = self.parser,
            right = right,
            )

    def source_julia(self, depth = 0):
        left_str = u', '.join(
            left_item.source_julia(depth = depth + 1)
            for left_item in self.left
            )
        right_str = u', '.join(
            right_item.source_julia(depth = depth + 1)
            for right_item in self.right
            )
        return u'{} {} {}'.format(left_str, self.operator, right_str)


class Attribute(formulas_parsers_2to3.Attribute):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            name = self.name,
            parser = self.parser,
            subject = self.subject.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u"{}.{}".format(
            self.subject.source_julia(depth = depth),
            self.name,
            )


class Call(formulas_parsers_2to3.Call):
    def juliaize(self):
        parser = self.parser
        keyword_argument = self.keyword_argument.juliaize() if self.keyword_argument is not None else None
        named_arguments = collections.OrderedDict(
            (parser.juliaize_name(argument_name), argument_value.juliaize())
            for argument_name, argument_value in self.named_arguments.iteritems()
            )
        positional_arguments = [
            argument_value.juliaize()
            for argument_value in self.positional_arguments
            ]
        star_argument = self.star_argument.juliaize() if self.star_argument is not None else None
        subject = self.subject.juliaize()
        if isinstance(subject, parser.Attribute):
            method_name = subject.name
            if method_name == 'offset':
                method_subject = subject.subject.juliaize()
                method_subject_guess = method_subject.guess
                if isinstance(method_subject_guess, parser.Instant):
                    assert len(self.positional_arguments) == 2, self.positional_arguments
                    delta, unit = self.positional_arguments
                    if isinstance(delta, parser.String) and delta.value == 'first-of':
                        if isinstance(unit, parser.String) and unit.value == 'month':
                            return parser.Call(
                                container = self.container,
                                guess = parser.Instant(parser = parser),
                                parser = parser,
                                positional_arguments = [method_subject],
                                subject = parser.Variable(
                                    name = u'firstdayofmonth',
                                    parser = parser,
                                    ),
                                )
                        if isinstance(unit, parser.String) and unit.value == 'year':
                            return parser.Call(
                                container = self.container,
                                guess = parser.Instant(parser = parser),
                                parser = parser,
                                positional_arguments = [method_subject],
                                subject = parser.Variable(
                                    name = u'firstdayofyear',
                                    parser = parser,
                                    ),
                                )
            if method_name == 'period':
                method_subject = subject.subject.juliaize()
                method_subject_guess = method_subject.guess
                if isinstance(method_subject_guess, parser.Instant):
                    assert len(self.positional_arguments) >= 1, self.positional_arguments
                    unit = self.positional_arguments[0]
                    if isinstance(unit, parser.String) and unit.value == 'month':
                        return parser.Call(
                            container = self.container,
                            guess = parser.Period(parser = parser),
                            parser = parser,
                            positional_arguments = [method_subject] + self.positional_arguments[1:],
                            subject = parser.Variable(
                                name = u'MonthPeriod',
                                parser = parser,
                                ),
                            )
                    if isinstance(unit, parser.String) and unit.value == 'year':
                        return parser.Call(
                            container = self.container,
                            guess = parser.Period(parser = parser),
                            parser = parser,
                            positional_arguments = [method_subject] + self.positional_arguments[1:],
                            subject = parser.Variable(
                                name = u'YearPeriod',
                                parser = parser,
                                ),
                            )
        elif isinstance(subject, parser.Variable):
            function_name = subject.name
            if function_name == 'date':
                assert len(self.positional_arguments) == 3, self.positional_arguments
                return parser.Call(
                    container = self.container,
                    guess = parser.Date(parser = parser),
                    parser = parser,
                    positional_arguments = self.positional_arguments,
                    subject = parser.Variable(
                        name = u'Date',
                        parser = parser,
                        ),
                    )
        return self.__class__(
            container = self.container,
            guess = self._guess,
            keyword_argument = keyword_argument,
            named_arguments = named_arguments,
            parser = self.parser,
            positional_arguments = positional_arguments,
            star_argument = star_argument,
            subject = subject,
            )

    def source_julia(self, depth = 0):
        star = ([u'{}...'.format(self.star_argument.source_julia(depth = depth + 2))]
            if self.star_argument is not None
            else [])
        keyword = ([u'{}...'.format(self.keyword_argument.source_julia(depth = depth + 2))]
            if self.keyword_argument is not None
            else [])
        arguments_str = [
            argument_value.source_julia(depth = depth)
            for argument_value in self.positional_arguments
            ] + star + [
            u'{} = {}'.format(argument_name, argument_value.source_julia(depth = depth))
            for argument_name, argument_value in self.named_arguments.iteritems()
            ] + keyword
        return u"{}({})".format(
            self.subject.source_julia(depth = depth),
            u', '.join(arguments_str),
            )


class Class(formulas_parsers_2to3.Class):
    pass


class Comparison(formulas_parsers_2to3.Comparison):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            left = self.left.juliaize(),
            operator = self.operator,
            parser = self.parser,
            right = self.right.juliaize(),
            )

    def source_julia(self, depth = 0):
        operator = self.operator
        if operator == u'not in':
            return u'!({} in {})'.format(self.left.source_julia(depth = depth), self.right.source_julia(depth = depth))
        if operator == u'is':
            operator = u'==='
        elif operator == u'is not':
            operator = u'!=='
        return u'{} {} {}'.format(self.left.source_julia(depth = depth), operator,
            self.right.source_julia(depth = depth))


class Continue(formulas_parsers_2to3.Continue):
    def juliaize(self):
        return self  # Conversion of variable to Julia is done only once, during assignment.

    def source_julia(self, depth = 0):
        return u'continue'


class Expression(formulas_parsers_2to3.Expression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            operands = [
                operand.juliaize()
                for operand in self.operands
                ],
            operator = self.operator,
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u' {} '.format(self.operator).join(
            operand.source_julia(depth = depth)
            for operand in self.operands
            )


class Factor(formulas_parsers_2to3.Factor):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            operand = self.operand.juliaize(),
            operator = self.operator,
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u'{}{}'.format(self.operator, self.operand.source_julia(depth = depth))


class For(formulas_parsers_2to3.For):
    def juliaize(self):
        parser = self.parser
        # Convert variables to Julia only once, during assignment.
        variable_by_name = collections.OrderedDict(
            (
                name,
                variable.__class__(
                    container = variable.container,
                    guess = variable._guess,
                    name = variable.name,
                    parser = parser,
                    value = variable.value.juliaize() if variable.value is not None else None,
                    ),
                )
            for name, variable in self.variable_by_name.iteritems()
            )

        return self.__class__(
            container = self.container,
            guess = self._guess,
            body = [
                statement.juliaize()
                for statement in self.body
                ],
            iterator = self.iterator.juliaize(),
            parser = parser,
            variable_by_name = variable_by_name,
            )

    def source_julia(self, depth = 0):
        variables_name = list(self.variable_by_name.iterkeys())
        return u'for {variables} in {iterator}\n{body}{indent}end'.format(
            body = u''.join(
                u'{}{}\n'.format(u'  ' * (depth + 1), statement.source_julia(depth = depth + 1))
                for statement in self.body
                ),
            indent = u'  ' * depth,
            iterator = self.iterator.source_julia(depth = depth + 1),
            variables = u'({})'.format(u', '.join(variables_name)) if len(variables_name) > 1 else variables_name[0],
            )


class Function(formulas_parsers_2to3.Function):
    def juliaize(self):
        parser = self.parser
        # Convert variables to Julia only once, during assignment.
        variable_by_name = collections.OrderedDict(
            (
                name,
                variable.__class__(
                    container = variable.container,
                    guess = variable._guess,
                    name = variable.name,
                    parser = parser,
                    value = variable.value.juliaize() if variable.value is not None else None,
                    ) if isinstance(variable, parser.Variable) else variable.juliaize(),
                )
            for name, variable in self.variable_by_name.iteritems()
            )

        return self.__class__(
            container = self.container,
            guess = self._guess,
            body = [
                statement.juliaize()
                for statement in self.body
                ],
            keyword_name = self.keyword_name,
            name = self.name,
            named_parameters = collections.OrderedDict(
                (name, value.juliaize())
                for name, value in self.named_parameters.iteritems()
                ),
            parser = parser,
            positional_parameters = self.positional_parameters,
            # returns = self.returns
            star_name = self.star_name,
            variable_by_name = variable_by_name,
            )

    def source_julia(self, depth = 0):
        positional_parameters = []
        if self.positional_parameters:
            positional_parameters.extend(self.positional_parameters)
        if self.star_name:
            positional_parameters.append(u'{}...'.format(self.star_name))
        named_parameters = []
        if self.named_parameters:
            named_parameters.extend(
                '{} = {}'.format(name, value.source_julia(depth = depth + 2))
                for name, value in self.named_parameters.iteritems()
                )
        if self.keyword_name:
            named_parameters.append(u'{}...'.format(self.keyword_name))
        return u'\n{indent}function {name}({positional_parameters}{named_parameters})\n{body}{indent}end\n'.format(
            body = self.source_julia_statements(depth = depth + 1),
            indent = u'  ' * depth,
            name = self.name,
            named_parameters = u'; {}'.format(u', '.join(named_parameters)) if named_parameters else u'',
            positional_parameters = u', '.join(positional_parameters),
            )

    def source_julia_statements(self, depth = 0):
        parser = self.parser
        statements = []
        for statement in self.body:
            if isinstance(statement, parser.String):
                # Strip and reindent docstring.
                value = statement.value.strip()
                if u'\n' in value:
                    lines = value.split(u'\n')
                    while all(index == 0 or not line or line.startswith(u'    ') for index, line in enumerate(lines)):
                        lines = [
                            (line[4:] if line else u'') if index > 0 else line
                            for index, line in enumerate(lines)
                            ]
                        if any(line.startswith(u'    ') for line in lines):
                            continue
                        break
                    value = u'\n'.join(
                        u'{}{}'.format(u'  ' * depth, line) if line else u''
                        for line in lines
                        ).strip()
                    if u'\n' in value:
                        value += u'\n{}'.format(u'  ' * depth)
                statement.value = value
            statements.append(u'{}{}\n'.format(u'  ' * depth, statement.source_julia(depth = depth + 1)))
        return u''.join(statements)


class FunctionFileInput(formulas_parsers_2to3.FunctionFileInput):
    @classmethod
    def parse(cls, function, parser = None):
        function_wrapper = super(FunctionFileInput, cls).parse(function, parser = parser)
        parser.non_formula_function_by_name[function_wrapper.name] = function_wrapper
        return function_wrapper


class If(formulas_parsers_2to3.If):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            items = [
                (
                    test.juliaize() if test is not None else None,
                    [
                        statement.juliaize()
                        for statement in body
                        ],
                    )
                for test, body in self.items
                ],
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u''.join(
            u'{word}{test}\n{body}'.format(
                body = u''.join(
                    u'{}{}\n'.format(u'  ' * (depth + 1), statement.source_julia(depth = depth + 1))
                    for statement in body
                    ),
                test = u' {}'.format(test.source_julia(depth = depth + 2)) if test is not None else u'',
                word = (u'{}else' if test is None else u'if' if index == 0 else u'{}elseif').format(u'  ' * depth),
                )
            for index, (test, body) in enumerate(self.items)
            ) + u'{}end'.format(u'  ' * depth)


class Instant(formulas_parsers_2to3.Instant):
    def juliaize(self):
        return self


class Key(formulas_parsers_2to3.Key):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            parser = self.parser,
            subject = self.subject.juliaize(),
            value = self.value.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u"{}[{}]".format(
            self.subject.source_julia(depth = depth),
            self.value.source_julia(depth = depth),
            )


class Lambda(formulas_parsers_2to3.Lambda):
    def juliaize(self):
        parser = self.parser
        # Convert variables to Julia only once, during assignment.
        variable_by_name = collections.OrderedDict(
            (
                name,
                variable.__class__(
                    container = variable.container,
                    guess = variable._guess,
                    name = variable.name,
                    parser = parser,
                    value = variable.value.juliaize() if variable.value is not None else None,
                    ),
                )
            for name, variable in self.variable_by_name.iteritems()
            )

        return self.__class__(
            container = self.container,
            guess = self._guess,
            expression = self.expression.juliaize(),
            parser = parser,
            positional_parameters = self.positional_parameters,
            variable_by_name = variable_by_name,
            )

    def source_julia(self, depth = 0):
        return u'({parameters}) -> {expression}'.format(
            expression = self.expression.source_julia(depth = depth + 1),
            parameters = u', '.join(self.positional_parameters),
            )


class List(formulas_parsers_2to3.List):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            parser = self.parser,
            value = [
                item.juliaize()
                for item in self.value
                ],
            )

    def source_julia(self, depth = 0):
        return u'[{}]'.format(u', '.join(
            item.source_julia(depth = depth)
            for item in self.value
            ))


class Not(formulas_parsers_2to3.Not):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            parser = self.parser,
            value = self.value.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u"!{}".format(
            self.value.source_julia(depth = depth),
            )


class Number(formulas_parsers_2to3.Number):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        return unicode(self.value)


class ParentheticalExpression(formulas_parsers_2to3.ParentheticalExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            parser = self.parser,
            value = self.value.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u"({})".format(
            self.value.source_julia(depth = depth),
            )


class Period(formulas_parsers_2to3.Period):
    def juliaize(self):
        return self


class Return(formulas_parsers_2to3.Return):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            parser = self.parser,
            value = self.value.juliaize(),
            )

    def source_julia(self, depth = 0):
        if isinstance(self.value, self.parser.Tuple):
            return u'return {}'.format(u', '.join(
                item.source_julia(depth = depth)
                for item in self.value.value
                ))
        return u"return {}".format(self.value.source_julia(depth = depth))


class Simulation(formulas_parsers_2to3.Simulation):
    def juliaize(self):
        return self


class String(formulas_parsers_2to3.String):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        return generate_string_julia_source(self.value)


class Term(formulas_parsers_2to3.Term):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            items = [
                item if item_index & 1 else item.juliaize()
                for item_index, item in enumerate(self.items)
                ],
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u' '.join(
            item if item_index & 1 else item.source_julia(depth = depth)
            for item_index, item in enumerate(self.items)
            )


class Test(formulas_parsers_2to3.Test):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            false_value = self.false_value.juliaize(),
            guess = self._guess,
            parser = self.parser,
            test = self.test.juliaize(),
            true_value = self.true_value.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u'{test} ? {true_value} : {false_value}'.format(
            false_value = self.false_value.source_julia(depth = depth + 1),
            test = self.test.source_julia(depth = depth + 1),
            true_value = self.true_value.source_julia(depth = depth + 1),
            )


class Tuple(formulas_parsers_2to3.Tuple):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            guess = self._guess,
            parser = self.parser,
            value = tuple(
                item.juliaize()
                for item in self.value
                ),
            )

    def source_julia(self, depth = 0):
        return u'({})'.format(u', '.join(
            item.source_julia(depth = depth)
            for item in self.value
            ))


class Variable(formulas_parsers_2to3.Variable):
    def juliaize(self):
        return self  # Conversion of variable to Julia is done only once, during assignment.

    def source_julia(self, depth = 0):
        return self.parser.juliaize_name(self.name)


# Formula-specific classes


class FormulaClass(Class, formulas_parsers_2to3.FormulaClass):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        parser = self.parser
        statements = None
        for formula in self.variable_by_name.itervalues():
            if isinstance(formula, parser.FormulaFunction):
                # Simple formula
                statements = formula.juliaize().source_julia_statements(depth = depth + 1)
                break
        else:
            # Dated formula
            dated_functions_decorator = [
                decorator
                for decorator in self.variable_by_name.itervalues()
                if isinstance(decorator, parser.Decorator) and decorator.name == 'dated_function'
                ]
            statements_blocks = []
            for decorator in dated_functions_decorator:
                call = decorator.subject
                assert isinstance(call, parser.Call)
                assert call.keyword_argument is None
                assert call.star_argument is None
                start_date = call.positional_arguments[0] \
                    if len(call.positional_arguments) >= 1 \
                    else call.named_arguments.get('start')
                stop_date = call.positional_arguments[1] \
                    if len(call.positional_arguments) >= 2 \
                    else call.named_arguments.get('stop')
                assert start_date is not None or stop_date is not None
                if start_date is None:
                    test = u'{optional_else}if period.start <= {stop_date}'.format(
                        optional_else = u'else' if statements_blocks else u'',
                        stop_date = stop_date.juliaize().source_julia(depth = depth + 2),
                        )
                elif stop_date is None:
                    test = u'{optional_else}if {start_date} <= period.start'.format(
                        optional_else = u'else' if statements_blocks else u'',
                        start_date = start_date.juliaize().source_julia(depth = depth + 2),
                        )
                else:
                    test = u'{optional_else}if {start_date} <= period.start && period.start <= {stop_date}'.format(
                        optional_else = u'else' if statements_blocks else u'',
                        start_date = start_date.juliaize().source_julia(depth = depth + 2),
                        stop_date = stop_date.juliaize().source_julia(depth = depth + 2),
                        )

                function = decorator.decorated
                assert isinstance(function, parser.FormulaFunction)
                statements_blocks.append(u"{indent}  {test}\n{statements}".format(
                    indent = u'  ' * depth,
                    statements = function.juliaize().source_julia_statements(depth = depth + 2),
                    test = test,
                    ))
            statements_blocks.append(textwrap.dedent(u"""\
                {indent}  else
                {indent}    return period, default_array(variable)
                {indent}  end
                """).format(
                indent = u'  ' * depth,
                ))
            statements = u''.join(statements_blocks)

        return textwrap.dedent(u"""
            {call} do simulation, variable, period
            {statements}end
            """).format(
            call = parser.source_julia_column_without_function(),
            statements = statements or u'',
            )


class FormulaFunction(Function, formulas_parsers_2to3.FormulaFunction):
    pass


# Julia parser & compiler


class Parser(formulas_parsers_2to3.Parser):
    AndExpression = AndExpression
    ArithmeticExpression = ArithmeticExpression
    Assert = Assert
    Assignment = Assignment
    Attribute = Attribute
    Call = Call
    Class = Class
    Comparison = Comparison
    Continue = Continue
    Expression = Expression
    Factor = Factor
    For = For
    FormulaClass = FormulaClass
    FormulaFunction = FormulaFunction
    Function = Function
    FunctionFileInput = FunctionFileInput
    If = If
    Instant = Instant
    Key = Key
    Lambda = Lambda
    List = List
    non_formula_function_by_name = None
    Not = Not
    Number = Number
    ParentheticalExpression = ParentheticalExpression
    Period = Period
    Return = Return
    Simulation = Simulation
    String = String
    Term = Term
    Test = Test
    Tuple = Tuple
    Variable = Variable

    def __init__(self, country_package = None, driver = None, tax_benefit_system = None):
        super(Parser, self).__init__(country_package = country_package, driver = driver,
            tax_benefit_system = tax_benefit_system)
        self.non_formula_function_by_name = collections.OrderedDict()

    def juliaize_name(self, name):
        if name == u'function':
            name = u'func'
        return name

    def source_julia_column_without_function(self):
        column = self.column
        tax_benefit_system = self.tax_benefit_system

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
                (u"label = {}".format(generate_string_julia_source(column.label))
                    if column.label not in (u'', column.name) else None),
                # u'max_length = {}'.format(max_length) if max_length is not None else None,  TODO?
                "permanent = true" if column.is_permanent else None,
                u"start_date = Date({}, {}, {})".format(start_date.year, start_date.month,
                    start_date.day) if start_date is not None else None,
                u"stop_date = Date({}, {}, {})".format(stop_date.year, stop_date.month,
                    stop_date.day) if stop_date is not None else None,
                (u"url = {}".format(generate_string_julia_source(column.url))
                    if column.url is not None
                    else None),
                u"values = {}".format(values_str) if values_str is not None else None,
                ]
            if named_argument is not None
            )
        if named_arguments:
            named_arguments = u',\n{}'.format(named_arguments)
        return u"""@define_variable({name}, {entity}_definition, {cell_type}{named_arguments})""".format(
            cell_type = cell_type,
            entity = tax_benefit_system.entity_class_by_key_plural[column.entity_key_plural].key_singular,
            name = column.name,
            named_arguments = named_arguments,
            )


def generate_date_range_value_julia_source(date_range_value_json):
    for key in date_range_value_json.iterkeys():
        assert key in (
            'comment',
            'start',
            'stop',
            'value',
            ), "Unexpected item key for date range value: {}".format(key)
    comment = date_range_value_json.get('comment')
    return u'DateRangeValue({start_date}, {stop_date}, {value}{comment})'.format(
        comment = u', comment = {}'.format(generate_string_julia_source(comment)) if comment else u'',
        start_date = u'Date({}, {}, {})'.format(*date_range_value_json['start'].split(u'-')),
        stop_date = u'Date({}, {}, {})'.format(*date_range_value_json['stop'].split(u'-')),
        value = unicode(date_range_value_json['value']).lower(),  # Method lower() is used for True and False.
        )


def generate_legislation_node_julia_source(node_json, check_start_date_julia_source = None,
        check_stop_date_julia_source = None, comments = None, descriptions = None, julia_source_by_path = None,
        path_fragments = None):
    if node_json['@type'] == 'Node':
        for key in node_json.iterkeys():
            assert key in (
                '@context',
                '@type',
                'children',
                'comment',
                'description',
                'start',
                'stop',
                ), "Unexpected item key for node: {}".format(key)
        for child_code, child_json in node_json['children'].iteritems():
            generate_legislation_node_julia_source(
                child_json,
                check_start_date_julia_source = check_start_date_julia_source,
                check_stop_date_julia_source = check_stop_date_julia_source,
                comments = comments + [node_json.get('comment')],
                descriptions = descriptions + [node_json.get('description')],
                julia_source_by_path = julia_source_by_path,
                path_fragments = path_fragments + [child_code],
                )
    elif node_json['@type'] == 'Parameter':
        for key in node_json.iterkeys():
            assert key in (
                '@type',
                'comment',
                'description',
                'format',
                'unit',
                'values',
                ), "Unexpected item key for parameter: {}".format(key)

        format = node_json.get('format')
        type_str = {
            None: u'Float32',
            'boolean': u'Bool',
            'float': u'Float32',
            'integer': u'Int32',
            'rate': u'Float32',
            }[format]

        named_arguments = collections.OrderedDict()

        unit = node_json.get('unit')
        if unit is not None:
            named_arguments['unit'] = u'"{}"'.format(unit)

        named_arguments['check_start_date'] = check_start_date_julia_source
        named_arguments['check_stop_date'] = check_stop_date_julia_source

        description = u' ; '.join(
            fragment
            for fragment in descriptions + [node_json.get('description')]
            if fragment
            )
        if description:
            named_arguments['description'] = generate_string_julia_source(description)

        comment = u' ; '.join(
            fragment
            for fragment in comments + [node_json.get('comment')]
            if fragment
            )
        if comment:
            named_arguments['comment'] = generate_string_julia_source(comment)

        julia_source_by_path[u'.'.join(path_fragments)] = textwrap.dedent(u"""
            {name} = Parameter{{{type}}}(
              [
            {values}  ],
            {named_arguments})
            """).format(
            name = u'_'.join(path_fragments),
            named_arguments = u''.join(
                u'  {} = {},\n'.format(argument_name, argument_str)
                for argument_name, argument_str in named_arguments.iteritems()
                ),
            type = type_str,
            values = u''.join(
                u'    {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                for date_range_value_json in reversed(node_json['values'])
                ),
            )
    elif node_json['@type'] == 'Scale':
        for key in node_json.iterkeys():
            assert key in (
                '@type',
                'brackets',
                'comment',
                'description',
                'option',
                'unit',
                ), "Unexpected item key for tax scale: {}".format(key)

        tax_scale_type = None
        brackets_julia_source = []
        for bracket_json in node_json['brackets']:
            for bracket_key in bracket_json.iterkeys():
                assert bracket_key in (
                    'amount',
                    'base',
                    'rate',
                    'threshold',
                    ), "Unexpected item key for bracket: {}".format(bracket_key)

            amount_json = bracket_json.get('amount')
            if amount_json is None:
                amount_julia_source = u''
            else:
                if tax_scale_type is None:
                    tax_scale_type = u'AmountScale'
                else:
                    assert tax_scale_type == u'AmountScale'
                date_range_values_julia_source = u'\n'.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in amount_json
                    )
                amount_julia_source = u'      amount = [\n{}      ],\n'.format(date_range_values_julia_source)

            base_json = bracket_json.get('base')
            if base_json is None:
                base_julia_source = u''
            else:
                date_range_values_julia_source = u'\n'.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in base_json
                    )
                base_julia_source = u'      base = [\n{}      ],\n'.format(date_range_values_julia_source)

            rate_json = bracket_json.get('rate')
            if rate_json is None:
                rate_julia_source = u''
            else:
                if tax_scale_type is None:
                    tax_scale_type = u'MarginalRateScale'
                else:
                    assert tax_scale_type == u'MarginalRateScale'
                date_range_values_julia_source = u'\n'.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in rate_json
                    )
                rate_julia_source = u'      rate = [\n{}      ],\n'.format(date_range_values_julia_source)

            threshold_json = bracket_json.get('threshold')
            if threshold_json is None:
                threshold_julia_source = u''
            else:
                date_range_values_julia_source = u'\n'.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in threshold_json
                    )
                threshold_julia_source = u'      threshold = [\n{}      ],\n'.format(date_range_values_julia_source)

            if tax_scale_type == 'AmountScale':
                bracket_julia_source = u'    AmountBracket(\n{threshold}{amount}{base}    ),\n'.format(
                    amount = amount_julia_source,
                    base = base_julia_source,
                    threshold = threshold_julia_source,
                    )
            else:
                bracket_julia_source = u'    RateBracket(\n{threshold}{rate}{base}    ),\n'.format(
                    base = base_julia_source,
                    rate = rate_julia_source,
                    threshold = threshold_julia_source,
                    )
            brackets_julia_source.append(bracket_julia_source)

        option = node_json.get('option')
        assert option in (
            None,
            'contrib',
            'main-d-oeuvre',
            'noncontrib',
            ), "Unexpected option for tax scale: {}".format(option)
        # TODO

        named_arguments = collections.OrderedDict()

        unit = node_json.get('unit')
        if unit is not None:
            named_arguments['unit'] = u'"{}"'.format(unit)

        named_arguments['check_start_date'] = check_start_date_julia_source
        named_arguments['check_stop_date'] = check_stop_date_julia_source

        description = u' ; '.join(
            fragment
            for fragment in descriptions + [node_json.get('description')]
            if fragment
            )
        if description:
            named_arguments['description'] = generate_string_julia_source(description)

        comment = u' ; '.join(
            fragment
            for fragment in comments + [node_json.get('comment')]
            if fragment
            )
        if comment:
            named_arguments['comment'] = generate_string_julia_source(comment)

        julia_source_by_path[u'.'.join(path_fragments)] = textwrap.dedent(u"""
            {name} = {tax_scale_type}(
              [
            {brackets}  ],
            {named_arguments})
            """).format(
            brackets = u''.join(brackets_julia_source),
            name = u'_'.join(path_fragments),
            named_arguments = u''.join(
                u'  {} = {},\n'.format(argument_name, argument_str)
                for argument_name, argument_str in named_arguments.iteritems()
                ),
            tax_scale_type = tax_scale_type,
            )
    else:
        assert False, "Unexpected type for node: {}".format(node_json['@type'])


def generate_string_julia_source(s):
    if u'\n' in s:
        return u'"""{}"""'.format(s.replace(u'"', u'\\"'))
    return u'"{}"'.format(s.replace(u'"', u'\\"'))


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

    parser = Parser(
        country_package = country_package,
        driver = lib2to3.pgen2.driver.Driver(lib2to3.pygram.python_grammar, convert = lib2to3.pytree.convert,
            logger = log),
        tax_benefit_system = tax_benefit_system,
        )

    legislation_json = tax_benefit_system.legislation_json
    parameter_julia_source_by_path = collections.OrderedDict()
    generate_legislation_node_julia_source(
        legislation_json,
        check_start_date_julia_source = u'Date({}, {}, {})'.format(*legislation_json['start'].split(u'-')),
        check_stop_date_julia_source = u'Date({}, {}, {})'.format(*legislation_json['stop'].split(u'-')),
        comments = [],
        descriptions = [],
        julia_source_by_path = parameter_julia_source_by_path,
        path_fragments = [],
        )
    julia_path = os.path.join(args.julia_package_dir, 'src', 'parameters.jl')
    with codecs.open(julia_path, 'w', encoding = 'utf-8') as julia_file:
        julia_file.write(julia_file_header)
        julia_file.write(u'\n')
        for parameter_julia_source in parameter_julia_source_by_path.itervalues():
            julia_file.write(parameter_julia_source)

    input_variable_definition_julia_source_by_name = collections.OrderedDict()
    julia_source_by_name_by_module_name = {}
    for column in tax_benefit_system.column_by_name.itervalues():
        print column.name
        parser.column = column

        column_formula_class = column.formula_class
        if column_formula_class is None:
            # Input variable
            input_variable_definition_julia_source_by_name[column.name] = parser.source_julia_column_without_function()
            continue
        if issubclass(column_formula_class, formulas.AbstractEntityToEntity):
            # EntityToPerson or PersonToEntity converters
            continue

        if column.name in (
                'zone_apl',
                ):
            # Skip formulas that can't be easily converted to Julia and handle them as input variables.
            input_variable_definition_julia_source_by_name[column.name] = parser.source_julia_column_without_function()
            continue

        try:
            formula_class_wrapper = parser.FormulaClassFileInput.parse(column_formula_class, parser = parser)
        except:
            # Stop conversion of columns, but write the existing results to Julia files.
            traceback.print_exc()
            break
        # if issubclass(column_formula_class, formulas.DatedFormula):
        #     function_functions = []
        #     for name, value in formula_class_wrapper.value_by_name.iteritems():
        #         if isinstance(value, parser.Decorator) and value.name == u'dated_function':
        #             function_function = value.decorated
        #             assert isinstance(function_function, parser.Function)
        #             assert name.startswith('function_') or name == 'function', name
        #             function_functions.append(function_function)
        # else:
        #     assert issubclass(column_formula_class, formulas.SimpleFormula), column_formula_class
        #     function_functions = [formula_class_wrapper.value_by_name['function']]

        try:
            julia_source = formula_class_wrapper.juliaize().source_julia(depth = 0)
        except:
            node = formula_class_wrapper.node
            if node is not None:
                print "An exception occurred When juliaizing formula {}:\n{}\n\n{}".format(column.name, repr(node),
                    unicode(node).encode('utf-8'))
            raise

        module_name = formula_class_wrapper.containing_module.python.__name__
        assert module_name.startswith('openfisca_france.model.')
        module_name = module_name[len('openfisca_france.model.'):]
        julia_source_by_name_by_module_name.setdefault(module_name, {})[column.name] = julia_source

    # Add non-formula functions to modules.
    for function_wrapper in parser.non_formula_function_by_name.itervalues():
        try:
            julia_source = function_wrapper.juliaize().source_julia(depth = 0)
        except:
            node = function_wrapper.node
            if node is not None:
                print "An exception occurred When juliaizing function {}:\n{}\n\n{}".format(function_wrapper.name,
                    repr(node), unicode(node).encode('utf-8'))
            raise

        module_name = function_wrapper.containing_module.python.__name__
        assert module_name.startswith('openfisca_france.model.')
        module_name = module_name[len('openfisca_france.model.'):]
        julia_source_by_name_by_module_name.setdefault(module_name, {})[function_wrapper.name] = julia_source

    julia_path = os.path.join(args.julia_package_dir, 'src', 'input_variables.jl')
    with codecs.open(julia_path, 'w', encoding = 'utf-8') as julia_file:
        julia_file.write(julia_file_header)
        julia_file.write(u'\n')
        for input_variable_definition_julia_source in input_variable_definition_julia_source_by_name.itervalues():
            julia_file.write(u'\n')
            julia_file.write(input_variable_definition_julia_source)
            julia_file.write(u'\n')

    julia_path = os.path.join(args.julia_package_dir, 'src', 'formulas.jl')
    with codecs.open(julia_path, 'w', encoding = 'utf-8') as julia_file:
        julia_file.write(julia_file_header)
        julia_file.write(u'\n\n')
        for module_name in sorted(julia_source_by_name_by_module_name.iterkeys()):
            julia_file.write(u'include("formulas/{}.jl")\n'.format(module_name.replace(u'.', u'/')))

    for module_name, julia_source_by_name in julia_source_by_name_by_module_name.iteritems():
        julia_relative_path = os.path.join(*module_name.split('.')) + '.jl'
        julia_path = os.path.join(args.julia_package_dir, 'src', 'formulas', julia_relative_path)
        julia_dir = os.path.dirname(julia_path)
        if not os.path.exists(julia_dir):
            os.makedirs(julia_dir)
        with codecs.open(julia_path, 'w', encoding = 'utf-8') as julia_file:
            julia_file.write(julia_file_header)
            for column_name, julia_source in sorted(julia_source_by_name.iteritems()):
                julia_file.write(u'\n')
                julia_file.write(julia_source)

    return 0


if __name__ == "__main__":
    sys.exit(main())
