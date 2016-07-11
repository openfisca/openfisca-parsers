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
import inspect
import itertools
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
name_by_role_by_entity_key_singular = dict(
    famille = {
        0: u'CHEF',
        },
    foyer_fiscal = {
        0: u'VOUS',
        },
    )


# Abstract Wrappers


class JuliaCompilerMixin(object):
    def testize(self, allow_array = False):
        container = self.container
        parser = self.parser
        if self.guess(parser.Dictionary) is not None or self.guess(parser.List) is not None \
                or self.guess(parser.Tuple) is not None or self.guess(parser.UniformDictionary) is not None:
            return parser.NotTest(
                container = container,
                parser = parser,
                value = parser.Call(
                    container = container,
                    parser = parser,
                    positional_arguments = [self],
                    subject = parser.Variable(
                        container = container,
                        name = u'isempty',
                        parser = parser,
                        ),
                    ),
                )
        if self.guess(parser.Boolean) is not None:
            return self
        if self.guess(parser.Number) is not None:
            return parser.Comparison(
                container = container,
                left = parser.ParentheticalExpression(
                    container = container,
                    parser = parser,
                    value = self,
                    ),
                operator = u'!=',
                parser = parser,
                right = parser.Number(
                    container = container,
                    parser = parser,
                    value = 0,
                    ),
                )
        if allow_array:
            array = self.guess(parser.Array)
            if array is not None:
                cell = array.cell
                if cell.guess(parser.Boolean) is not None:
                    return self
                if cell.guess(parser.Number) is not None:
                    return parser.Comparison(
                        container = container,
                        left = parser.ParentheticalExpression(
                            container = container,
                            parser = parser,
                            value = self,
                            ),
                        operator = u'.!=',
                        parser = parser,
                        right = parser.Number(
                            container = container,
                            parser = parser,
                            value = 0,
                            ),
                        )
        assert False, "{} has a non-boolean value: {}\n{}".format(self.__class__.__name__,
            unicode(self.node).encode('utf-8'), self.__dict__)


# Concrete Wrappers


class AndTest(JuliaCompilerMixin, formulas_parsers_2to3.AndTest):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            operands = [
                operand.juliaize()
                for operand in self.operands
                ],
            operator = self.operator,
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u' && '.join(
            operand.source_julia(depth = depth)
            for operand in self.operands
            )


class AndExpression(JuliaCompilerMixin, formulas_parsers_2to3.AndExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            operands = [
                operand.juliaize().testize(allow_array = True)
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


class ArithmeticExpression(JuliaCompilerMixin, formulas_parsers_2to3.ArithmeticExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            items = [
                item if item_index & 1 else item.juliaize()
                for item_index, item in enumerate(self.items)
                ],
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        array_expression = self.guess(self.parser.Array) is not None
        return u' '.join(
            (u'.{}'.format(item) if array_expression else item) if item_index & 1 else item.source_julia(depth = depth)
            for item_index, item in enumerate(self.items)
            )


class Array(JuliaCompilerMixin, formulas_parsers_2to3.Array):
    def juliaize(self):
        return self


class Assert(JuliaCompilerMixin, formulas_parsers_2to3.Assert):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            error = self.error.juliaize() if self.error is not None else None,
            hint = self.hint,
            parser = self.parser,
            test = self.test.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u'@assert {test}{error}'.format(
            error = u', {}'.format(self.error.source_julia(depth = depth + 1)) if self.error is not None else u'',
            test = self.test.source_julia(depth = depth + 1),
            )


class Assignment(JuliaCompilerMixin, formulas_parsers_2to3.Assignment):
    def juliaize(self):
        container = self.container
        parser = self.parser
        # New variables are not created, but the value of the existing ones are replaced (using right value), otherwise
        # all references to this variable (in other expressions) will continue using the non julialized version.
        left = self.left
        operator = self.operator
        right = [
            right_item.juliaize()
            for right_item in self.right
            ]
        if len(left) == len(right) and operator == '=':
            for left_item, right_item in itertools.izip(left, right):
                if isinstance(left_item, parser.Variable):
                    assert left_item is not right_item
                    left_item.value = right_item

        if len(left) == 1:
            variable = left[0]
            if isinstance(variable, parser.Variable) and isinstance(variable.value, parser.Call):
                call = variable.value
                call_subject = call.subject
                if isinstance(call_subject, parser.Attribute):
                    method_name = call_subject.name
                    if method_name in ('calculate', 'calculate_add', 'calculate_add_divide', 'calculate_divide',
                            'compute', 'compute_add', 'compute_add_divide', 'compute_divide'):
                        method_julia_name = dict(
                            compute = u'calculate',
                            compute_add = u'calculate_add',
                            compute_add_divide = u'calculate_add_divide',
                            compute_divide = u'calculate_divide',
                            ).get(method_name, method_name)
                        variable_name = variable.name
                        # if variable_name.endswith(u'_holder'):
                        #     variable_name = variable_name[:-len(u'_holder')]
                        method_subject = call_subject.subject
                        if method_subject.guess(parser.Simulation):
                            assert len(call.positional_arguments) >= 1, call.positional_arguments
                            assert len(call.named_arguments) <= 1, call.named_arguments
                            if len(call.named_arguments) == 1:
                                assert u'accept_other_period' in call.named_arguments
                            requested_variable = call.positional_arguments[0]
                            if isinstance(requested_variable, parser.String):
                                if requested_variable.value == variable_name:
                                    # @calculate(x, ...)
                                    return parser.Call(
                                        container = container,
                                        hint = call.hint,
                                        named_arguments = call.named_arguments,
                                        parser = parser,
                                        positional_arguments = [
                                            parser.Variable(
                                                container = container,
                                                # hint = parser.ArrayHandle(parser = parser),  TODO
                                                name = requested_variable.value,
                                                parser = parser,
                                                ),
                                            ] + call.positional_arguments[1:],
                                        subject = parser.Variable(  # TODO: Use Macro or MacroCall.
                                            name = u'@{}'.format(method_julia_name),
                                            parser = parser,
                                            ),
                                        )
                            # y = calculate("x", ...)
                            return parser.Assignment(
                                container = container,
                                left = [
                                    parser.Variable(container = container, name = variable_name, parser = parser),
                                    ],
                                operator = u'=',
                                parser = parser,
                                right = [
                                    parser.Call(
                                        container = container,
                                        hint = call.hint,
                                        named_arguments = call.named_arguments,
                                        parser = parser,
                                        positional_arguments = [
                                            method_subject,
                                            requested_variable,
                                            ] + call.positional_arguments[1:],
                                        subject = parser.Variable(  # TODO: Use function call.
                                            name = method_julia_name,
                                            parser = parser,
                                            ),
                                        ),
                                    ],
                                )
                    elif method_name == 'get_array':
                        method_subject = call_subject.subject
                        if method_subject.guess(parser.Simulation):
                            assert len(call.positional_arguments) >= 1, call.positional_arguments
                            assert len(call.named_arguments) == 0, call.named_arguments
                            requested_variable = call.positional_arguments[0]
                            if isinstance(requested_variable, parser.String):
                                if requested_variable.value == variable.name:
                                    # @variable_at(x, ...)
                                    return parser.Call(
                                        container = container,
                                        hint = call.hint,
                                        parser = parser,
                                        positional_arguments = [
                                            parser.Variable(
                                                container = container,
                                                # hint = parser.ArrayHandle(parser = parser),  TODO
                                                name = requested_variable.value,
                                                parser = parser,
                                                ),
                                            ] + call.positional_arguments[1:] + [
                                            # Add nothing as default value.
                                            parser.NoneWrapper(
                                                container = container,
                                                parser = parser,
                                                ),
                                            ],
                                        subject = parser.Variable(  # TODO: Use Macro or MacroCall.
                                            name = u'@variable_at',
                                            parser = parser,
                                            ),
                                        )
                            # y = variable_at("x", ...)
                            return parser.Assignment(
                                container = container,
                                left = [
                                    parser.Variable(container = container, name = variable.name, parser = parser),
                                    ],
                                operator = u'=',
                                parser = parser,
                                right = [
                                    parser.Call(
                                        container = container,
                                        hint = call.hint,
                                        parser = parser,
                                        positional_arguments = [
                                            method_subject,
                                            requested_variable,
                                            ] + call.positional_arguments[1:] + [
                                            # Add nothing as default value.
                                            parser.NoneWrapper(
                                                container = container,
                                                parser = parser,
                                                ),
                                            ],
                                        subject = parser.Variable(  # TODO: Use function call.
                                            name = u'variable_at',
                                            parser = parser,
                                            ),
                                        ),
                                    ],
                                )
        return self.__class__(
            container = container,
            hint = self.hint,
            left = left,
            operator = operator,
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


class Attribute(JuliaCompilerMixin, formulas_parsers_2to3.Attribute):
    def juliaize(self):
        parser = self.parser
        subject = self.subject.juliaize()
        parent_node = subject.guess(parser.CompactNode)
        if parent_node is not None:
            key = self.name
            assert key is not None
            key = unicode(key)
            if key not in ('iterkeys', 'iteritems', 'itervalues', 'keys', 'items', 'values'):
                node_value = parent_node.value['children'].get(key)
                if node_value is None:
                    # Dirty hack for tax_hab formula.
                    if key == u'taux':
                        node_value = parent_node.value['children']['taux_plein']
                    else:
                        assert key in (u'taux_plein', u'taux_reduit'), key
                        node_value = parent_node.value['children']['taux']
                node_type = node_value['@type']
                if node_type == u'Node':
                    hint = parser.CompactNode(
                        is_reference = parent_node.is_reference,
                        name = unicode(key),
                        parent = parent_node,
                        parser = parser,
                        value = node_value,
                        )
                elif node_type == u'Parameter':
                    if node_value.get('format') == 'boolean':
                        hint = parser.Boolean(
                            parser = parser,
                            )
                    else:
                        hint = parser.Number(
                            parser = parser,
                            )
                else:
                    assert node_type == u'Scale'
                    hint = parser.TaxScale(
                        parser = parser,
                        )
                return parser.Key(
                    container = self.container,
                    hint = hint,
                    parser = parser,
                    subject = subject,
                    value = parser.String(
                        container = self.container,
                        parser = parser,
                        value = key,
                        ).juliaize(),
                    )
        elif subject.guess(parser.Instant) is not None:
            if self.name in (u'day', u'month', u'year'):
                return parser.Call(
                    container = self.container,
                    hint = parser.Number(parser = parser),
                    parser = parser,
                    positional_arguments = [subject],
                    subject = parser.Variable(
                        name = self.name,
                        parser = parser,
                        ),
                    )
        elif subject.guess(parser.Period) is not None:
            if self.name == u'stop':
                return parser.Call(
                    container = self.container,
                    hint = parser.Instant(parser = parser),
                    parser = parser,
                    positional_arguments = [subject],
                    subject = parser.Variable(
                        name = u'stop_date',
                        parser = parser,
                        ),
                    )
        else:
            formula = subject.guess(parser.Formula)
            if formula is not None:
                if self.name == u'__class__':
                    return parser.Variable(
                        name = u'variable.definition',
                        parser = parser,
                        value = self
                        )
                elif self.name == u'holder':
                    return parser.Variable(
                        # hint = parser.Holder(
                        #     column = formula.column,
                        #     parser = parser,
                        #     ),
                        name = u'variable',
                        parser = parser,
                        value = self
                        )
            formula_class = subject.guess(parser.FormulaClass)
            if formula_class is not None:
                if self.name == u'__name__':
                    return self.__class__(
                        container = self.container,
                        hint = self.hint,
                        name = u'name',
                        parser = parser,
                        subject = subject,
                        )
            holder = subject.guess(parser.Holder)
            if holder is not None:
                if self.name == u'entity':
                    return parser.Call(
                        container = self.container,
                        hint = parser.Entity(
                            entity_class = parser.tax_benefit_system.entity_class_by_key_plural[
                                holder.column.entity_key_plural],
                            parser = parser,
                            ),
                        parser = parser,
                        positional_arguments = [subject],
                        subject = parser.Variable(
                            name = u'get_entity',
                            parser = parser,
                            ),
                        )
            parent_node = subject.guess(parser.StemNode)
            if parent_node is not None:
                hint = parser.StemNode(
                    is_reference = parent_node.is_reference,
                    parent = parent_node,
                    parser = parser,
                    )
        return self.__class__(
            container = self.container,
            hint = self.hint,
            name = self.name,
            parser = parser,
            subject = subject,
            )

    def source_julia(self, depth = 0):
        return u"{}.{}".format(
            self.subject.source_julia(depth = depth),
            self.name,
            )


class Boolean(JuliaCompilerMixin, formulas_parsers_2to3.Boolean):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        return u'true' if self.value else u'false'


class Call(JuliaCompilerMixin, formulas_parsers_2to3.Call):
    def guess(self, expected):
        guessed = super(Call, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name in (u'any_person_in_entity', u'sum_person_in_entity'):
                    variable = self.positional_arguments[0].guess(parser.Variable)
                    if variable is None:
                        cell_wrapper = None
                    else:
                        variable_name = variable.name
                        if variable_name.endswith(u'_holder'):
                            variable_name = variable_name[:-len(u'_holder')]
                        tax_benefit_system = parser.tax_benefit_system
                        column = tax_benefit_system.column_by_name[variable_name]
                        cell_wrapper = parser.get_cell_wrapper(container = self.container, type = column.dtype)
                    return parser.Array(
                        cell = cell_wrapper,
                        entity_class = parser.entity_class,
                        parser = parser,
                        )
                elif function.name == u'entity_to_person':
                    variable = self.positional_arguments[0].guess(parser.Variable)
                    if variable is None:
                        cell_wrapper = None
                    else:
                        variable_name = variable.name
                        if variable_name.endswith(u'_holder'):
                            variable_name = variable_name[:-len(u'_holder')]
                        tax_benefit_system = parser.tax_benefit_system
                        column = tax_benefit_system.column_by_name[variable_name]
                        cell_wrapper = parser.get_cell_wrapper(container = self.container, type = column.dtype)
                    return parser.Array(
                        cell = cell_wrapper,
                        entity_class = parser.person_class,
                        parser = parser,
                        )
                elif function.name in (u'max', u'min'):
                    for argument in self.positional_arguments:
                        array = argument.guess(parser.Array)
                        if array is not None:
                            return parser.Array(
                                cell = parser.Number(
                                    parser = parser,
                                    ),
                                entity_class = array.entity_class,
                                parser = parser,
                                )
                elif function.name == u'single_person_in_entity':
                    variable = self.positional_arguments[0].guess(parser.Variable)
                    if variable is None:
                        cell_wrapper = None
                    else:
                        variable_name = variable.name
                        if variable_name.endswith(u'_holder'):
                            variable_name = variable_name[:-len(u'_holder')]
                        tax_benefit_system = parser.tax_benefit_system
                        column = tax_benefit_system.column_by_name[variable_name]
                        cell_wrapper = parser.get_cell_wrapper(container = self.container, type = column.dtype)
                    return parser.Array(
                        cell = cell_wrapper,
                        entity_class = parser.entity_class,
                        parser = parser,
                        )
                elif function.name == u'zeros':
                    assert len(self.positional_arguments) <= 2, self.positional_arguments
                    assert len(self.named_arguments) <= 1, self.named_arguments
                    dtype_wrapper = self.named_arguments.get('dtype')
                    if dtype_wrapper is None:
                        cell_type = None
                    else:
                        dtype_wrapper = dtype_wrapper.guess(parser.String) or dtype_wrapper.guess(parser.Type)
                        cell_type = dtype_wrapper.value
                    cell_wrapper = parser.get_cell_wrapper(container = self.container, type = cell_type)
                    return parser.Array(
                        cell = cell_wrapper,
                        parser = parser,
                        )
        elif issubclass(parser.Boolean, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name in (u'all', u'any', u'isempty'):
                    return parser.Boolean(
                        parser = parser,
                        )
        elif issubclass(parser.Number, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name == 'length':
                    return parser.Number(parser = parser)
        elif issubclass(parser.UniformDictionary, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name == u'split_person_by_role':
                    variable = self.positional_arguments[0].guess(parser.Variable)
                    if variable is None:
                        cell_wrapper = None
                    else:
                        variable_name = variable.name
                        if variable_name.endswith(u'_holder'):
                            variable_name = variable_name[:-len(u'_holder')]
                        tax_benefit_system = parser.tax_benefit_system
                        column = tax_benefit_system.column_by_name[variable_name]
                        cell_wrapper = parser.get_cell_wrapper(container = self.container, type = column.dtype)
                    return parser.UniformDictionary(
                        julia = True,
                        key = parser.Role(
                            parser = parser,
                            ),
                        parser = parser,
                        value = parser.Array(
                            cell = cell_wrapper,
                            entity_class = parser.entity_class,
                            parser = parser,
                            ),
                        )
        elif issubclass(parser.UniformIterator, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name == u'keys':
                    uniform_dictionary = self.positional_arguments[0].guess(parser.UniformDictionary)
                    if uniform_dictionary is not None:
                        return parser.UniformIterator(
                            items = [uniform_dictionary.key],
                            parser = parser,
                            )
                elif function.name == 'values':
                    uniform_dictionary = self.positional_arguments[0].guess(parser.UniformDictionary)
                    if uniform_dictionary is not None:
                        return parser.UniformIterator(
                            items = [uniform_dictionary.value],
                            parser = parser,
                            )

            uniform_dictionary = self.guess(parser.UniformDictionary)
            if uniform_dictionary is not None:
                uniform_iterator = uniform_dictionary.guess(parser.UniformIterator)
                if uniform_iterator is not None:
                    return uniform_iterator

        return None

    def juliaize(self):
        container = self.container
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
            if method_name in ('all', 'any'):
                method_subject = subject.subject
                if method_subject.guess(parser.Array):
                    return parser.Call(
                        container = container,
                        hint = self.hint,
                        keyword_argument = keyword_argument,
                        named_arguments = named_arguments,
                        parser = parser,
                        positional_arguments = [method_subject.testize(allow_array = True)] + positional_arguments,
                        star_argument = star_argument,
                        subject = parser.Variable(
                            name = method_name,
                            parser = parser,
                            ),
                        )
            elif method_name == 'any_by_roles':
                method_subject = subject.subject
                if isinstance(method_subject, parser.Variable) and method_subject.name == 'self':
                    assert len(positional_arguments) == 1, positional_arguments
                    assert len(named_arguments) == 0, named_arguments
                    requested_variable = positional_arguments[0]
                    # any_person_in_entity(x, get_entity(variable), period)
                    return parser.Call(
                        container = container,
                        hint = self.hint,
                        parser = parser,
                        positional_arguments = [
                            requested_variable,
                            parser.Variable(
                                container = container,
                                name = u'get_entity(variable)',
                                parser = parser,
                                ),
                            parser.Variable(
                                container = container,
                                name = u'period',
                                parser = parser,
                                ),
                            ],
                        subject = parser.Variable(  # TODO: Use function call.
                            name = u'any_person_in_entity',
                            parser = parser,
                            ),
                        )
            elif method_name == 'astype':
                assert len(positional_arguments) == 1, positional_arguments
                argument_string = positional_arguments[0].guess(parser.String)
                if argument_string is not None:
                    if argument_string.value == u'timedelta64[M]':
                        return parser.Call(
                            container = container,
                            parser = parser,
                            positional_arguments = [
                                parser.Term(
                                    items = [
                                        parser.Call(
                                            container = container,
                                            parser = parser,
                                            positional_arguments = [
                                                subject.subject,
                                                ],
                                            subject = parser.Variable(
                                                name = u'int',
                                                parser = parser,
                                                ),
                                            ),
                                        u'*',
                                        parser.Number(
                                            parser = parser,
                                            value = 12,
                                            ),
                                        u'/',
                                        parser.Number(
                                            parser = parser,
                                            value = 365.25,
                                            ),
                                        ],
                                    parser = parser,
                                    ),
                                ],
                            subject = parser.Variable(
                                name = u'floor',
                                parser = parser,
                                ),
                            )
                    elif argument_string.value == u'timedelta64[Y]':
                        return parser.Call(
                            container = container,
                            parser = parser,
                            positional_arguments = [
                                parser.Term(
                                    items = [
                                        parser.Call(
                                            container = container,
                                            parser = parser,
                                            positional_arguments = [
                                                subject.subject,
                                                ],
                                            subject = parser.Variable(
                                                name = u'int',
                                                parser = parser,
                                                ),
                                            ),
                                        u'/',
                                        parser.Number(
                                            parser = parser,
                                            value = 365.25,
                                            ),
                                        ],
                                    parser = parser,
                                    ),
                                ],
                            subject = parser.Variable(
                                name = u'floor',
                                parser = parser,
                                ),
                            )
                else:
                    argument_variable = positional_arguments[0].guess(parser.Variable)
                    if argument_variable is not None:
                        if argument_variable.name == u'int16':
                            return parser.Call(
                                container = container,
                                parser = parser,
                                positional_arguments = [subject.subject],
                                subject = parser.Variable(
                                    name = u'int16',
                                    parser = parser,
                                    ),
                                )
            elif method_name == 'calc':
                method_subject = subject.subject
                return parser.Call(
                    container = container,
                    hint = self.hint,
                    keyword_argument = keyword_argument,
                    named_arguments = named_arguments,
                    parser = parser,
                    positional_arguments = [method_subject] + positional_arguments,
                    star_argument = star_argument,
                    subject = parser.Variable(
                        name = u'apply_tax_scale',
                        parser = parser,
                        ),
                    )
            elif method_name in ('cast_from_entity_to_role', 'cast_from_entity_to_roles'):
                method_subject = subject.subject
                if isinstance(method_subject, parser.Variable) and method_subject.name == 'self':
                    assert len(positional_arguments) == 1, positional_arguments
                    assert len(named_arguments) <= 1, named_arguments
                    if len(named_arguments) == 1:
                        assert 'role' in named_arguments or 'roles' in named_arguments
                        roles_arguments = [
                            (named_arguments.get('role') or named_arguments.get('roles')),
                            ]
                    else:
                        roles_arguments = []
                    requested_variable = positional_arguments[0]
                    # entity_to_person(x, period, role)
                    return parser.Call(
                        container = container,
                        hint = self.hint,
                        parser = parser,
                        positional_arguments = [
                            requested_variable,
                            parser.Variable(
                                container = container,
                                name = u'period',
                                parser = parser,
                                ),
                            ] + roles_arguments,
                        subject = parser.Variable(  # TODO: Use function call.
                            name = u'entity_to_person',
                            parser = parser,
                            ),
                        )
            elif method_name == 'filter_role':
                method_subject = subject.subject
                if isinstance(method_subject, parser.Variable) and method_subject.name == 'self':
                    assert len(positional_arguments) == 1, positional_arguments
                    assert len(named_arguments) == 1, named_arguments
                    assert 'role' in named_arguments
                    requested_variable = positional_arguments[0]
                    # single_person_in_entity(x, get_entity(variable), period, role)
                    return parser.Call(
                        container = container,
                        hint = self.hint,
                        parser = parser,
                        positional_arguments = [
                            requested_variable,
                            parser.Variable(
                                container = container,
                                name = u'get_entity(variable)',
                                parser = parser,
                                ),
                            parser.Variable(
                                container = container,
                                name = u'period',
                                parser = parser,
                                ),
                            named_arguments['role'],
                            ],
                        subject = parser.Variable(  # TODO: Use function call.
                            name = u'single_person_in_entity',
                            parser = parser,
                            ),
                        )
            elif method_name == 'floor':
                method_subject = subject.subject
                if isinstance(method_subject, parser.Variable) and method_subject.name == 'math':
                    assert len(named_arguments) == 0, named_arguments
                    return parser.Call(
                        container = container,
                        parser = parser,
                        positional_arguments = positional_arguments,
                        subject = parser.Variable(
                            name = u'floor',
                            parser = parser,
                            ),
                        )
            elif method_name == 'get':
                method_subject = subject.subject
                assert len(named_arguments) == 0, named_arguments
                assert 1 <= len(positional_arguments) <= 2, positional_arguments
                return parser.Call(
                    container = container,
                    parser = parser,
                    positional_arguments = [method_subject] + positional_arguments + ([
                        parser.Variable(
                            name = u'nothing',
                            parser = parser,
                            ),
                        ] if len(positional_arguments) < 2 else []),
                    subject = parser.Variable(
                        name = u'get',
                        parser = parser,
                        ),
                    )
            elif method_name == 'iterkeys':
                method_subject = subject.subject
                assert len(named_arguments) == 0, named_arguments
                assert len(positional_arguments) == 0, positional_arguments
                return parser.Call(
                    container = container,
                    parser = parser,
                    positional_arguments = [method_subject],
                    subject = parser.Variable(
                        name = u'keys',
                        parser = parser,
                        ),
                    )
            elif method_name == 'iteritems':
                method_subject = subject.subject
                assert len(named_arguments) == 0, named_arguments
                assert len(positional_arguments) == 0, positional_arguments
                return method_subject
            elif method_name == 'itervalues':
                method_subject = subject.subject
                assert len(named_arguments) == 0, named_arguments
                assert len(positional_arguments) == 0, positional_arguments
                return parser.Call(
                    container = container,
                    parser = parser,
                    positional_arguments = [method_subject],
                    subject = parser.Variable(
                        name = u'values',
                        parser = parser,
                        ),
                    )
            elif method_name == 'legislation_at':
                method_subject = subject.subject
                if method_subject.guess(parser.Simulation):
                    assert len(positional_arguments) == 1, positional_arguments
                    instant = positional_arguments[0].guess(parser.Instant)
                    if instant is not None:
                        assert len(named_arguments) <= 1, named_arguments
                        reference = named_arguments.get('reference')
                        return parser.Call(
                            container = container,
                            hint = parser.CompactNode(
                                is_reference = bool(reference),
                                parser = parser,
                                value = parser.tax_benefit_system.get_legislation(),
                                ),
                            named_arguments = dict(reference = reference) if reference is not None else None,
                            parser = parser,
                            positional_arguments = [method_subject, positional_arguments[0]],
                            subject = parser.Variable(
                                name = u'legislation_at',
                                parser = parser,
                                ),
                            )
            elif method_name == 'offset':
                method_subject = subject.subject
                if method_subject.guess(parser.Instant):
                    assert len(positional_arguments) == 2, positional_arguments
                    delta, unit = positional_arguments
                    if isinstance(delta, (parser.Factor, parser.Number)) and isinstance(unit, parser.String) \
                            and unit.value is not None:
                        if isinstance(delta, parser.Factor):
                            assert delta.operator == u'-'
                            delta = -int(delta.operand.value)
                        else:
                            delta = int(delta.value)
                        return parser.ParentheticalExpression(
                            container = container,
                            parser = parser,
                            value = parser.ArithmeticExpression(
                                container = container,
                                hint = parser.Instant(parser = parser),
                                items = [
                                    method_subject,
                                    u'+' if delta >= 0 else u'-',
                                    parser.Call(
                                        container = container,
                                        parser = parser,
                                        positional_arguments = [
                                            parser.Number(
                                                parser = parser,
                                                value = abs(delta),
                                                ),
                                            ],
                                        subject = parser.Variable(
                                            name = dict(
                                                day = u'Day',
                                                month = u'Month',
                                                year = u'Year',
                                                )[unit.value],
                                            parser = parser,
                                            ),
                                        ),
                                    ],
                                parser = parser,
                                ),
                            )
                    elif isinstance(delta, parser.String) and delta.value == 'first-of':
                        if isinstance(unit, parser.String) and unit.value == 'month':
                            return parser.Call(
                                container = container,
                                hint = parser.Instant(parser = parser),
                                parser = parser,
                                positional_arguments = [method_subject],
                                subject = parser.Variable(
                                    name = u'firstdayofmonth',
                                    parser = parser,
                                    ),
                                )
                        if isinstance(unit, parser.String) and unit.value == 'year':
                            return parser.Call(
                                container = container,
                                hint = parser.Instant(parser = parser),
                                parser = parser,
                                positional_arguments = [method_subject],
                                subject = parser.Variable(
                                    name = u'firstdayofyear',
                                    parser = parser,
                                    ),
                                )
                elif method_subject.guess(parser.Period):
                    unit = method_subject.guess(parser.Period).unit
                    assert len(positional_arguments) == 1, positional_arguments
                    delta = positional_arguments[0]
                    if isinstance(delta, (parser.Factor, parser.Number)):
                        if isinstance(delta, parser.Factor):
                            assert delta.operator == u'-'
                            delta = -int(delta.operand.value)
                        else:
                            delta = int(delta.value)
                        return parser.ArithmeticExpression(
                            container = container,
                            hint = parser.Period(parser = parser, unit = unit),
                            items = [
                                method_subject,
                                u'+' if delta >= 0 else u'-',
                                parser.Call(
                                    container = container,
                                    parser = parser,
                                    positional_arguments = [
                                        parser.Number(
                                            parser = parser,
                                            value = abs(delta),
                                            ),
                                        ],
                                    subject = parser.Variable(
                                        name = dict(
                                            day = u'Day',
                                            month = u'Month',
                                            year = u'Year',
                                            )[unit],
                                        parser = parser,
                                        ),
                                    ),
                                ],
                            parser = parser,
                            )
                    elif isinstance(delta, parser.String) and delta.value == 'first-of':
                        return parser.Call(
                            container = container,
                            hint = parser.Period(parser = parser, unit = unit),
                            parser = parser,
                            positional_arguments = [method_subject],
                            subject = parser.Variable(
                                name = u'first_day',
                                parser = parser,
                                ),
                            )
            elif method_name == 'period':
                method_subject = subject.subject
                if method_subject.guess(parser.Instant):
                    assert len(positional_arguments) >= 1, positional_arguments
                    unit = positional_arguments[0]
                    if isinstance(unit, parser.String) and unit.value == 'month':
                        return parser.Call(
                            container = container,
                            hint = parser.Period(parser = parser, unit = unit.value),
                            parser = parser,
                            positional_arguments = [method_subject] + positional_arguments[1:],
                            subject = parser.Variable(
                                name = u'MonthPeriod',
                                parser = parser,
                                ),
                            )
                    if isinstance(unit, parser.String) and unit.value == 'year':
                        return parser.Call(
                            container = container,
                            hint = parser.Period(parser = parser, unit = unit.value),
                            parser = parser,
                            positional_arguments = [method_subject] + positional_arguments[1:],
                            subject = parser.Variable(
                                name = u'YearPeriod',
                                parser = parser,
                                ),
                            )
            elif method_name == 'split_by_roles':
                method_subject = subject.subject
                if isinstance(method_subject, parser.Variable) and method_subject.name == 'self':
                    assert len(positional_arguments) == 1, positional_arguments
                    requested_variable = positional_arguments[0]
                    assert len(named_arguments) <= 1, named_arguments
                    if len(named_arguments) == 1:
                        assert 'roles' in named_arguments
                        roles_arguments = [named_arguments['roles']]
                    else:
                        roles_arguments = []
                    # split_person_by_role(x, get_entity(variable), period, roles)
                    return parser.Call(
                        container = container,
                        hint = self.hint,
                        parser = parser,
                        positional_arguments = [
                            requested_variable,
                            parser.Variable(
                                container = container,
                                name = u'get_entity(variable)',
                                parser = parser,
                                ),
                            parser.Variable(
                                container = container,
                                name = u'period',
                                parser = parser,
                                ),
                            ] + roles_arguments,
                        subject = parser.Variable(  # TODO: Use function call.
                            name = u'split_person_by_role',
                            parser = parser,
                            ),
                        )
            elif method_name == 'sum_by_entity':
                method_subject = subject.subject
                if isinstance(method_subject, parser.Variable) and method_subject.name == 'self':
                    assert len(positional_arguments) == 1, positional_arguments
                    assert len(named_arguments) <= 1, named_arguments
                    if len(named_arguments) == 1:
                        roles = named_arguments.get('roles')
                        assert roles is not None, named_arguments
                    else:
                        roles = None
                    requested_variable = positional_arguments[0]
                    # sum_person_in_entity(x, get_entity(variable), period)
                    return parser.Call(
                        container = container,
                        hint = self.hint,
                        parser = parser,
                        positional_arguments = [
                            requested_variable,
                            parser.Variable(
                                container = container,
                                name = u'get_entity(variable)',
                                parser = parser,
                                ),
                            parser.Variable(
                                container = container,
                                name = u'period',
                                parser = parser,
                                ),
                            ] + ([roles] if roles is not None else []),
                        subject = parser.Variable(  # TODO: Use function call.
                            name = u'sum_person_in_entity',
                            parser = parser,
                            ),
                        )
        elif isinstance(subject, parser.Variable):
            function_name = subject.name
            if function_name == 'and_':
                assert len(positional_arguments) == 2, positional_arguments
                left, right = positional_arguments
                return parser.ParentheticalExpression(
                    container = container,
                    parser = parser,
                    value = parser.AndExpression(
                        container = container,
                        operands = [
                            parser.ParentheticalExpression(
                                container = container,
                                parser = parser,
                                value = left.testize(allow_array = True),
                                ),
                            parser.ParentheticalExpression(
                                container = container,
                                parser = parser,
                                value = right.testize(allow_array = True),
                                ),
                            ],
                        operator = u'&',
                        parser = parser,
                        ),
                    )
            elif function_name == 'around':
                assert len(positional_arguments) == 1, positional_arguments
                return parser.Call(
                    container = container,
                    hint = positional_arguments[0].hint,
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'round',
                        parser = parser,
                        ),
                    )
            elif function_name == 'date':
                assert len(positional_arguments) == 3, positional_arguments
                return parser.Call(
                    container = container,
                    hint = parser.Date(parser = parser),
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'Date',
                        parser = parser,
                        ),
                    )
            elif function_name == 'datetime64':
                assert len(positional_arguments) == 1, positional_arguments
                argument = positional_arguments[0]
                assert argument.guess(parser.Date) is not None or argument.guess(parser.Instant) is not None, argument
                return argument
            elif function_name == 'len':
                assert len(positional_arguments) == 1, positional_arguments
                return parser.Call(
                    container = container,
                    hint = self.hint,
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'length',
                        parser = parser,
                        ),
                    )
            elif function_name == 'max_':
                return parser.Call(
                    container = container,
                    hint = self.hint,
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'max',
                        parser = parser,
                        ),
                    )
            elif function_name == 'min_':
                return parser.Call(
                    container = container,
                    hint = self.hint,
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'min',
                        parser = parser,
                        ),
                    )
            elif function_name == 'not_':
                assert len(positional_arguments) == 1, positional_arguments
                value = positional_arguments[0]
                return parser.NotTest(
                    container = container,
                    value = parser.ParentheticalExpression(
                        container = container,
                        parser = parser,
                        value = value.testize(allow_array = True),
                        ),
                    parser = parser,
                    )
            elif function_name == 'or_':
                assert len(positional_arguments) == 2, positional_arguments
                left, right = positional_arguments
                return parser.ParentheticalExpression(
                    container = container,
                    parser = parser,
                    value = parser.Expression(
                        container = container,
                        operands = [
                            parser.ParentheticalExpression(
                                container = container,
                                parser = parser,
                                value = left.testize(allow_array = True),
                                ),
                            parser.ParentheticalExpression(
                                container = container,
                                parser = parser,
                                value = right.testize(allow_array = True),
                                ),
                            ],
                        operator = u'|',
                        parser = parser,
                        ),
                    )
            elif function_name == 'round_':
                assert 1 <= len(positional_arguments) <= 2, positional_arguments
                return parser.Call(
                    container = container,
                    hint = positional_arguments[0].hint,
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'round',
                        parser = parser,
                        ),
                    )
            elif function_name == 'startswith':
                assert len(positional_arguments) == 2, positional_arguments
                assert len(named_arguments) == 0, named_arguments
                return parser.Call(
                    container = container,
                    hint = self.hint,
                    parser = parser,
                    positional_arguments = positional_arguments,
                    subject = parser.Variable(
                        name = u'beginswith',
                        parser = parser,
                        ),
                    )
            elif function_name == 'xor_':
                assert len(positional_arguments) == 2, positional_arguments
                left, right = positional_arguments
                return parser.ParentheticalExpression(
                    container = container,
                    parser = parser,
                    value = parser.XorExpression(
                        container = container,
                        operands = [
                            parser.ParentheticalExpression(
                                container = container,
                                parser = parser,
                                value = left.testize(allow_array = True),
                                ),
                            parser.ParentheticalExpression(
                                container = container,
                                parser = parser,
                                value = right.testize(allow_array = True),
                                ),
                            ],
                        operator = u'$',
                        parser = parser,
                        ),
                    )
            elif function_name == u'zeros':
                assert len(positional_arguments) == 1, positional_arguments
                length = positional_arguments[0].juliaize()
                assert len(named_arguments) <= 1, named_arguments
                dtype_wrapper = named_arguments.get('dtype')
                if dtype_wrapper is None:
                    cell_type = None
                else:
                    dtype_wrapper = dtype_wrapper.guess(parser.String) or dtype_wrapper.guess(parser.Type)
                    cell_type = dtype_wrapper.value
                cell_wrapper = parser.get_cell_wrapper(container = self.container, type = cell_type)
                return parser.Call(
                    container = container,
                    parser = parser,
                    positional_arguments = [
                        cell_wrapper.typeize(),
                        length,
                        ],
                    subject = parser.Variable(
                        name = u'zeros',
                        parser = parser,
                        ),
                    )
        return self.__class__(
            container = container,
            hint = self.hint,
            keyword_argument = keyword_argument,
            named_arguments = named_arguments,
            parser = parser,
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


class Class(JuliaCompilerMixin, formulas_parsers_2to3.Class):
    pass


class Comparison(JuliaCompilerMixin, formulas_parsers_2to3.Comparison):
    def juliaize(self):
        container = self.container
        parser = self.parser
        right = self.right.juliaize()
        if self.operator in (u'in', u'not in'):
            if right.guess(parser.CompactNode) is not None or right.guess(parser.StemNode) is not None \
                    or right.guess(parser.UniformDictionary) is not None:
                return self.__class__(
                    container = container,
                    hint = self.hint,
                    left = self.left.juliaize(),
                    operator = self.operator,
                    parser = parser,
                    right = parser.Call(
                        container = container,
                        parser = parser,
                        positional_arguments = [right],
                        subject = parser.Variable(
                            name = u'keys',
                            parser = parser,
                            ),
                        ),
                    )
        return self.__class__(
            container = container,
            hint = self.hint,
            left = self.left.juliaize(),
            operator = self.operator,
            parser = parser,
            right = right,
            )

    def source_julia(self, depth = 0):
        operator = self.operator
        if operator == u'not in':
            return u'!({} in {})'.format(self.left.source_julia(depth = depth), self.right.source_julia(depth = depth))
        if operator == u'is':
            operator = u'==='
        elif operator == u'is not':
            operator = u'!=='
        elif operator in (u'==', u'>', u'>=', u'<', u'<=', u'!=') and self.guess(self.parser.Array) is not None:
            operator = u'.{}'.format(operator)
        return u'{} {} {}'.format(self.left.source_julia(depth = depth), operator,
            self.right.source_julia(depth = depth))


class Continue(JuliaCompilerMixin, formulas_parsers_2to3.Continue):
    def juliaize(self):
        return self  # Conversion of variable to Julia is done only once, during assignment.

    def source_julia(self, depth = 0):
        return u'continue'


class Expression(JuliaCompilerMixin, formulas_parsers_2to3.Expression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            operands = [
                operand.juliaize().testize(allow_array = True)
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


class Factor(JuliaCompilerMixin, formulas_parsers_2to3.Factor):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            operand = self.operand.juliaize(),
            operator = self.operator,
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        return u'{}{}'.format(self.operator, self.operand.source_julia(depth = depth))


class For(JuliaCompilerMixin, formulas_parsers_2to3.For):
    def juliaize(self):
        parser = self.parser

        for variable in self.variable_by_name.itervalues():
            if variable.value is not None:
                variable.value = variable.value.juliaize()

        return self.__class__(
            container = self.container,
            hint = self.hint,
            body = [
                statement.juliaize()
                for statement in self.body
                ],
            iterator = self.iterator.juliaize(),
            parser = parser,
            variable_by_name = self.variable_by_name,
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


class Formula(JuliaCompilerMixin, formulas_parsers_2to3.Formula):
    def juliaize(self):
        # A formula is never used as is. Only its attributes are used, so it is not converted to Julia.
        return self


class Function(JuliaCompilerMixin, formulas_parsers_2to3.Function):
    def juliaize(self):
        parser = self.parser

        for variable in self.variable_by_name.itervalues():
            if variable.value is not None:
                variable.value = variable.value.juliaize()

        return self.__class__(
            container = self.container,
            hint = self.hint,
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
            returns = [
                statement.juliaize()
                for statement in self.returns
                ] if self.returns else None,
            star_name = self.star_name,
            variable_by_name = self.variable_by_name,
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
            statements.append(u'{}{}\n'.format(u'  ' * depth, statement.source_julia(depth = depth)))
        return u''.join(statements)


class FunctionFileInput(JuliaCompilerMixin, formulas_parsers_2to3.FunctionFileInput):
    @classmethod
    def parse(cls, function, parser = None):
        function_wrapper = super(FunctionFileInput, cls).parse(function, parser = parser)
        parser.non_formula_function_by_name[function_wrapper.name] = function_wrapper
        return function_wrapper


class If(JuliaCompilerMixin, formulas_parsers_2to3.If):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            items = [
                (
                    test.juliaize().testize() if test is not None else None,
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


class Instant(JuliaCompilerMixin, formulas_parsers_2to3.Instant):
    def juliaize(self):
        return self


class Key(JuliaCompilerMixin, formulas_parsers_2to3.Key):
    def juliaize(self):
        parser = self.parser
        subject = self.subject.juliaize()
        parent_node = subject.guess(parser.CompactNode)
        if parent_node is not None:
            value = self.value.guess(parser.String)
            key = value.value if value is not None else None
            if key is None:
                hint = parser.StemNode(
                    is_reference = parent_node.is_reference,
                    parent = parent_node,
                    parser = parser,
                    )
            else:
                key = unicode(key)
                node_value = parent_node.value['children'].get(key)
                if node_value is None:
                    # Dirty hack for tax_hab formula.
                    if key == u'taux':
                        node_value = parent_node.value['children']['taux_plein']
                    else:
                        assert key in (u'taux_plein', u'taux_reduit'), key
                        node_value = parent_node.value['children']['taux']
                node_type = node_value['@type']
                if node_type == u'Node':
                    hint = parser.CompactNode(
                        is_reference = parent_node.is_reference,
                        name = unicode(key),
                        parent = parent_node,
                        parser = parser,
                        value = node_value,
                        )
                elif node_type == u'Parameter':
                    if node_value.get('format') == 'boolean':
                        hint = parser.Boolean(
                            parser = parser,
                            )
                    else:
                        hint = parser.Number(
                            parser = parser,
                            )
                else:
                    assert node_type == u'Scale'
                    hint = parser.TaxScale(
                        parser = parser,
                        )
            return self.__class__(
                container = self.container,
                hint = hint,
                parser = parser,
                subject = subject,
                value = self.value.juliaize(),
                )
        else:
            parent_node = subject.guess(parser.StemNode)
            if parent_node is not None:
                hint = parser.StemNode(
                    is_reference = parent_node.is_reference,
                    parent = parent_node,
                    parser = parser,
                    )
        return self.__class__(
            container = self.container,
            hint = self.hint,
            parser = parser,
            subject = subject,
            value = self.value.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u"{}[{}]".format(
            self.subject.source_julia(depth = depth),
            self.value.source_julia(depth = depth),
            )


class Lambda(JuliaCompilerMixin, formulas_parsers_2to3.Lambda):
    def juliaize(self):
        parser = self.parser
        # Convert variables to Julia only once, during assignment.
        variable_by_name = collections.OrderedDict(
            (
                name,
                variable.__class__(
                    container = variable.container,
                    hint = variable.hint,
                    name = variable.name,
                    parser = parser,
                    value = variable.value.juliaize() if variable.value is not None else None,
                    ).juliaize(),
                )
            for name, variable in self.variable_by_name.iteritems()
            )

        return self.__class__(
            container = self.container,
            hint = self.hint,
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


class List(JuliaCompilerMixin, formulas_parsers_2to3.List):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
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


class NoneWrapper(JuliaCompilerMixin, formulas_parsers_2to3.NoneWrapper):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        return u'nothing'


class NotTest(JuliaCompilerMixin, formulas_parsers_2to3.NotTest):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            parser = self.parser,
            value = self.value.juliaize().testize(),
            )

    def source_julia(self, depth = 0):
        parser = self.parser
        value = self.value
        if isinstance(value, parser.NotTest):
            return value.value.source_julia(depth = depth)
        return u"!{}".format(value.source_julia(depth = depth))


class Number(JuliaCompilerMixin, formulas_parsers_2to3.Number):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        return unicode(self.value)

    def typeize(self):
        parser = self.parser
        return parser.Variable(
            name = {
                None: u'Float32',
                np.float32: u'Float32',
                np.int16: u'Int16',
                np.int32: u'Int32',
                }[self.type],
            parser = parser,
            )


class ParentheticalExpression(JuliaCompilerMixin, formulas_parsers_2to3.ParentheticalExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            parser = self.parser,
            value = self.value.juliaize(),
            )

    def source_julia(self, depth = 0):
        parser = self.parser
        value = self.value
        if isinstance(value, (parser.NotTest, parser.Number, parser.ParentheticalExpression, parser.Variable)):
            return value.source_julia(depth = depth)
        return u"({})".format(value.source_julia(depth = depth))


class Period(JuliaCompilerMixin, formulas_parsers_2to3.Period):
    def juliaize(self):
        return self


class Return(JuliaCompilerMixin, formulas_parsers_2to3.Return):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
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


class Role(JuliaCompilerMixin, formulas_parsers_2to3.Role):
    def juliaize(self):
        return self  # A role never appears in formulas => julialize is a fake one.


class Simulation(JuliaCompilerMixin, formulas_parsers_2to3.Simulation):
    def juliaize(self):
        return self


class String(JuliaCompilerMixin, formulas_parsers_2to3.String):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        return generate_string_julia_source(self.value)


class TaxScale(JuliaCompilerMixin, formulas_parsers_2to3.TaxScale):
    def juliaize(self):
        return self  # A tax-scale never appears in formulas => julialize is a fake one.


class Term(JuliaCompilerMixin, formulas_parsers_2to3.Term):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            items = [
                item if item_index & 1 else item.juliaize()
                for item_index, item in enumerate(self.items)
                ],
            parser = self.parser,
            )

    def source_julia(self, depth = 0):
        items = self.items
        if len(items) == 3 and items[1] == u'//':
            return u'div({}, {})'.format(items[0].source_julia(depth = depth), items[2].source_julia(depth = depth))
        array_expression = self.guess(self.parser.Array) is not None
        return u' '.join(
            (u'.{}'.format(item) if array_expression else item) if item_index & 1 else item.source_julia(depth = depth)
            for item_index, item in enumerate(items)
            )


class Test(JuliaCompilerMixin, formulas_parsers_2to3.Test):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            false_value = self.false_value.juliaize(),
            hint = self.hint,
            parser = self.parser,
            test = self.test.juliaize().testize(),
            true_value = self.true_value.juliaize(),
            )

    def source_julia(self, depth = 0):
        return u'{test} ? {true_value} : {false_value}'.format(
            false_value = self.false_value.source_julia(depth = depth + 1),
            test = self.test.source_julia(depth = depth + 1),
            true_value = self.true_value.source_julia(depth = depth + 1),
            )


class Tuple(JuliaCompilerMixin, formulas_parsers_2to3.Tuple):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
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


class UniformDictionary(JuliaCompilerMixin, formulas_parsers_2to3.UniformDictionary):
    julia = False

    def __init__(self, container = None, julia = False, key = None, node = None, parser = None, value = None):
        super(UniformDictionary, self).__init__(container = container, key = key, node = node, parser = parser,
            value = value)
        assert isinstance(julia, bool)
        if julia:
            self.julia = julia

    def guess(self, expected):
        if self.julia:
            # When iterating on a Julia dictionary, the iterator is a (key, value) couple, not a key only (as in
            # Python).
            parser = self.parser
            if issubclass(parser.UniformIterator, expected):
                return parser.UniformIterator(
                    items = [
                        self.key,
                        self.value,
                        ],
                    parser = parser,
                    )

        return super(UniformDictionary, self).guess(expected)


class Variable(JuliaCompilerMixin, formulas_parsers_2to3.Variable):
    def juliaize(self):
        # Cloning variable and doing value = self.value.juliaize() may create an infinite loop (for expressions like
        # period = period). So instead of juliazing value, we reuse the value already juliaized during variable
        # assignement.
        # self.value = self.container.variable_by_name[self.name]
        return self
        # return self.__class__(
        #     container = self.container,
        #     hint = self.hint,
        #     name = self.name,
        #     parser = self.parser,
        #     # Doing value = self.value.juliaize() may create an infinite loop (for expressions like period = period)
        #     # So instead of juliazing value, we reuse the value already juliaized during variable assignement.
        #     value = self.container.variable_by_name[self.name],
        #     ).juliaize()

    def source_julia(self, depth = 0):
        return self.parser.juliaize_name(self.name)


class XorExpression(JuliaCompilerMixin, formulas_parsers_2to3.XorExpression):
    def juliaize(self):
        return self.__class__(
            container = self.container,
            hint = self.hint,
            operands = [
                operand.juliaize().testize(allow_array = True)
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


# Formula-specific classes


class FormulaClass(Class, formulas_parsers_2to3.FormulaClass):
    def juliaize(self):
        return self

    def source_julia(self, depth = 0):
        parser = self.parser
        if parser.column.name == 'age':
            return textwrap.dedent(u"""
                {call} do simulation, variable, period
                  has_birth = !isempty(get_variable!(simulation, "birth").array)
                  if !has_birth
                    has_age_en_mois = !isemtpy(get_variable!(simulation, "age_en_mois").array_by_period)
                    if has_age_en_mois
                      return period, div(calculate(simulation, "age_en_mois", period), 12)
                    end

                    if !isempty(variable.array_by_period)
                      for (last_period, last_array) in sort(collect(variable.array_by_period), rev = true)
                        last_start = last_period.start
                        if day(last_start) == day(start)
                          return period, last_array .+ int(year(start) - year(last_start) +
                            (month(start) - month(last_start)) / 12)
                      end
                    end
                  end
                  @calculate(birth, period)
                  return period, Int[
                    year(period.start) - year(birth_cell)
                    for birth_cell in calculate(simulation, "birth", period)
                  ]
                end
                """).format(
                call = parser.source_julia_column_without_function(is_formula = True),
                )
        if parser.column.name == 'age_en_mois':
            return textwrap.dedent(u"""
                {call} do simulation, variable, period
                  if !isempty(variable.array_by_period)
                    for (last_period, last_array) in sort(collect(variable.array_by_period), rev = true)
                      last_start = last_period.start
                      if day(last_start) == day(start)
                        return period, last_array .+ ((year(start) - year(last_start)) * 12 +
                          (month(start) - month(last_start)))
                    end
                  end
                  has_birth = !isempty(get_variable!(simulation, "birth").array)
                  if !has_birth
                    has_age = !isemtpy(get_variable!(simulation, "age").array_by_period)
                    if has_age
                      return period, calculate(simulation, "age", period) * 12
                    end
                  end
                  @calculate(birth, period)
                  return period, Int[
                    (year(period.start) - year(birth_cell)) * 12 + month(period.start) - month(birth_cell)
                    for birth_cell in calculate(simulation, "birth", period)
                  ]
                end
                """).format(
                call = parser.source_julia_column_without_function(is_formula = True),
                )
        if parser.column.name == 'cmu_c_plafond':
            return textwrap.dedent(u"""
                {call} do simulation, variable, period
                  period = MonthPeriod(firstdayofmonth(period.start))
                  @calculate(age, period)
                  @calculate(alt, period)
                  @calculate(cmu_eligible_majoration_dom, period)
                  # @calculate(cmu_nbp_foyer, period)
                  P = legislation_at(simulation, period.start)["cmu"]

                  PAC = vcat([PART], ENFS)

                  # Calcul du coefficient personnes à charge, avec prise en compte de la garde alternée

                  # Tableau des coefficients
                  coefficients_array = vcat(
                    [P["coeff_p2"], P["coeff_p3_p4"], P["coeff_p3_p4"], P["coeff_p5_plus"]],
                    zeros(length(PAC) - 4),
                  )

                  # Tri des personnes à charge, le conjoint en premier, les enfants par âge décroissant
                  age_by_role = split_person_by_role(age, get_entity(variable), period, PAC)
                  alt_by_role = split_person_by_role(alt, get_entity(variable), period, PAC)

                  age_and_alt_matrix = hcat([
                    (role == PART) * 10000 .+ age_by_role[role] .* 10 .+ alt_by_role[role] .-
                      (age_by_role[role] .< 0) .* 999999
                    for role in sort(collect(keys(age_by_role)))
                  ]...)
                  for row_index in 1:size(age_and_alt_matrix, 1)
                    age_and_alt_matrix[row_index, :] = sort(age_and_alt_matrix[row_index, :], 2, rev = true)
                  end

                  # Calcule weighted_alt_matrix, qui vaut 0.5 pour les enfants en garde alternée, 1 sinon.
                  present_matrix = age_and_alt_matrix .>= 0
                  alt_matrix = (age_and_alt_matrix .% 10) .* present_matrix
                  weighted_alt_matrix = present_matrix .- alt_matrix .* 0.5

                  # Calcul final du coefficient
                  coeff_pac = weighted_alt_matrix * coefficients_array

                  return period, P["plafond_base"] .* (1 .+ cmu_eligible_majoration_dom .* P["majoration_dom"]) .*
                    (1 .+ coeff_pac)
                end
                """).format(
                call = parser.source_julia_column_without_function(is_formula = True),
                )
        if parser.column.name == 'nombre_jours_calendaires':
            return textwrap.dedent(u"""
                {call} do simulation, variable, period
                  period = MonthPeriod(firstdayofmonth(period.start))
                  @calculate(contrat_de_travail_arrivee, period)
                  @calculate(contrat_de_travail_depart, period)
                  debut_mois = firstdayofmonth(period.start)
                  fin_mois = lastdayofmonth(period.start)
                  jours_travailles = max(
                    int(min(contrat_de_travail_depart, fin_mois)) .- int(max(contrat_de_travail_arrivee, debut_mois))
                      .+ 1,
                    0,
                  )
                  return period, jours_travailles
                end
                """).format(
                call = parser.source_julia_column_without_function(is_formula = True),
                )
        if parser.column.name == 'zone_apl':
            del parser.non_formula_function_by_name['preload_zone_apl']
            return textwrap.dedent(u"""
                {call} do simulation, variable, period
                  @calculate(depcom, period)
                  return period, [
                    get(zone_apl_by_depcom, depcom_cell, 2)
                    for depcom_cell in depcom
                  ]
                end

                zone_apl_by_depcom = nothing

                function preload_zone_apl()
                  global zone_apl_by_depcom
                  if zone_apl_by_depcom === nothing
                    module_dir = Pkg.dir("OpenFiscaFrance")
                    array = readcsv(joinpath(module_dir, "assets/apl/20110914_zonage.csv"), String)
                    zone_apl_by_depcom = [
                      # Keep only first char of Zonage column because of 1bis value considered equivalent to 1.
                      depcom => Convertible(string(zone_apl_string[1])) |> input_to_int |> to_value
                      for (depcom, zone_apl_string) in zip(array[2:end, 1], array[2:end, 5])
                    ]
                    commune_depcom_by_subcommune_depcom = JSON.parsefile(
                      joinpath(module_dir, "assets/apl/commune_depcom_by_subcommune_depcom.json"))
                    for (subcommune_depcom, commune_depcom) in commune_depcom_by_subcommune_depcom
                      zone_apl_by_depcom[subcommune_depcom] = zone_apl_by_depcom[commune_depcom]
                    end
                  end
                end
                """).format(
                call = parser.source_julia_column_without_function(is_formula = True),
                )
        statements = None
        for variable in self.variable_by_name.itervalues():
            if isinstance(variable.value, parser.FormulaFunction):
                # Simple formula
                statements = variable.value.juliaize().source_julia_statements(depth = depth + 1)
                break
        else:
            # Dated formula
            dated_functions_decorator = [
                variable.value
                for variable in self.variable_by_name.itervalues()
                if isinstance(variable.value, parser.Decorator) and variable.name == 'dated_function'
                ]
            assert dated_functions_decorator
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
            call = parser.source_julia_column_without_function(is_formula = True),
            statements = statements or u'',
            )


class FormulaFunction(Function, formulas_parsers_2to3.FormulaFunction):
    pass


# Julia parser & compiler


class Parser(formulas_parsers_2to3.Parser):
    AndExpression = AndExpression
    AndTest = AndTest
    ArithmeticExpression = ArithmeticExpression
    Array = Array
    Assert = Assert
    Assignment = Assignment
    Attribute = Attribute
    Boolean = Boolean
    Call = Call
    Class = Class
    Comparison = Comparison
    Continue = Continue
    Expression = Expression
    Factor = Factor
    For = For
    Formula = Formula
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
    NoneWrapper = NoneWrapper
    NotTest = NotTest
    Number = Number
    ParentheticalExpression = ParentheticalExpression
    Period = Period
    Return = Return
    Role = Role
    Simulation = Simulation
    String = String
    TaxScale = TaxScale
    Term = Term
    Test = Test
    Tuple = Tuple
    UniformDictionary = UniformDictionary
    Variable = Variable
    XorExpression = XorExpression

    def __init__(self, country_package = None, driver = None, tax_benefit_system = None):
        super(Parser, self).__init__(country_package = country_package, driver = driver,
            tax_benefit_system = tax_benefit_system)
        self.non_formula_function_by_name = collections.OrderedDict()

    def juliaize_name(self, name):
        if name == u'function':
            name = u'func'
        # elif name.endswith(u'_holder'):
        #     name = name[:-len(u'_holder')]
        return name

    def source_julia_column_without_function(self, is_formula = False):
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
            'is_period_size_independent',
            'is_permanent',
            'label',
            'law_reference',
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

        if column.name in (
                entity.role_for_person_variable_name
                for entity in tax_benefit_system.entity_class_by_key_plural.itervalues()
                ):
            increment_role = True
        else:
            increment_role = False

        default = column.__dict__.get('default')
        if default is None:
            if increment_role:
                default_str = '1'
            else:
                default_str = None
        elif default is True:
            default_str = u"true"
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
                u'    "{}" => {},\n'.format(symbol, index + (1 if increment_role else 0))
                for index, symbol in sorted(
                    (index1, symbol1)
                    for symbol1, index1 in enum
                    )
                ))

        law_reference = column.law_reference
        if isinstance(law_reference, basestring):
            law_reference_str = u'"{}"'.format(law_reference)
        elif isinstance(law_reference, list):
            law_reference_str = u'[{}]'.format(u', '.join(
                u'"{}"'.format(field)
                for field in law_reference
                ))
        else:
            assert law_reference is None
            law_reference_str = None

        # max_length = column.__dict__.get('max_length')  TODO?

        start_date = column.start
        stop_date = column.end

        if column.name in ('age', 'age_en_mois'):
            assert default_str is None, default_str
            default_str = u"-9999"
            value_at_period_to_cell = textwrap.dedent(u"""\
            variable_definition::VariableDefinition -> pipe(
              value_at_period_to_integer(variable_definition),
              first_match(
                test_greater_or_equal(0),
                test_equal(-9999),
              ),
            )
            """).strip().replace(u'\n', u'\n  ')
        elif column.name == 'depcom':
            value_at_period_to_cell = textwrap.dedent(u"""\
            variable_definition::VariableDefinition -> pipe(
              condition(
                test_isa(Integer),
                call(string),
                test_isa(String),
                noop,
                fail(error = N_("Unexpected type for Insee depcom.")),
              ),
              condition(
                test(value -> length(value) == 4),
                call(value -> string('0', value)),
              ),
              test(value -> ismatch(r"^(\d{2}|2A|2B)\d{3}$", value),
                error = N_("Invalid Insee depcom format for commune.")),
            )
            """).strip().replace(u'\n', u'\n  ')
        else:
            value_at_period_to_cell = None

        formula_class = column.formula_class
        if issubclass(formula_class, formulas.AbstractEntityToEntity):
            base_function_str = u'entity_to_entity_period_value'
        elif formula_class.base_function.func_name in (
                formulas.last_duration_last_value.func_name,
                formulas.missing_value.func_name,
                base_functions.permanent_default_value.func_name,
                formulas.requested_period_default_value.func_name,
                formulas.requested_period_last_value.func_name,
                ):
            base_function_str = formula_class.base_function.func_name
        else:
            assert False, u"Unhandled base function in formula {}: {}".format(column.name,
                getattr(formula_class, 'base_function', None)).encode('utf-8')

        named_arguments = u''.join(
            u'  {},\n'.format(named_argument)
            for named_argument in [
                u'cell_default = {}'.format(default_str) if default_str is not None else None,
                u'cell_format = "{}"'.format(column.val_type) if column.val_type is not None else None,
                u'cerfa_field = {}'.format(cerfa_field_str) if cerfa_field_str is not None else None,
                (u"label = {}".format(generate_string_julia_source(column.label))
                    if column.label not in (u'', column.name)
                    else None),
                u'law_reference = {}'.format(law_reference_str) if law_reference_str is not None else None,
                # u'max_length = {}'.format(max_length) if max_length is not None else None,  TODO?
                u"permanent = true" if column.is_permanent else None,
                u"start_date = Date({}, {}, {})".format(start_date.year, start_date.month,
                    start_date.day) if start_date is not None else None,
                u"stop_date = Date({}, {}, {})".format(stop_date.year, stop_date.month,
                    stop_date.day) if stop_date is not None else None,
                (u"url = {}".format(generate_string_julia_source(column.url))
                    if column.url is not None
                    else None),
                (u"value_at_period_to_cell = {}".format(value_at_period_to_cell)
                    if value_at_period_to_cell is not None
                    else None),
                u"values = {}".format(values_str) if values_str is not None else None,
                ]
            if named_argument is not None
            )
        if named_arguments:
            named_arguments = u',\n{}'.format(named_arguments)

        return u"@define_{define_type}({name}, {entity}_definition, {cell_type}, {base_formula}{named_arguments})" \
            .format(
                base_formula = base_function_str,
                cell_type = cell_type,
                define_type = u'formula' if is_formula else u'variable',
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
            @define_parameter({name}, Parameter{{{type}}}(
              [
            {values}  ],
            {named_arguments}))
            """).format(
            name = u'.'.join(path_fragments),
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
                date_range_values_julia_source = u''.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in reversed(amount_json)
                    )
                amount_julia_source = u'      amount = [\n{}      ],\n'.format(date_range_values_julia_source)

            base_json = bracket_json.get('base')
            if base_json is None:
                base_julia_source = u''
            else:
                date_range_values_julia_source = u''.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in reversed(base_json)
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
                date_range_values_julia_source = u''.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in reversed(rate_json)
                    )
                rate_julia_source = u'      rate = [\n{}      ],\n'.format(date_range_values_julia_source)

            threshold_json = bracket_json.get('threshold')
            if threshold_json is None:
                threshold_julia_source = u''
            else:
                date_range_values_julia_source = u''.join(
                    u'        {},\n'.format(generate_date_range_value_julia_source(date_range_value_json))
                    for date_range_value_json in reversed(threshold_json)
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
            @define_parameter({name}, {tax_scale_type}(
              [
            {brackets}  ],
            {named_arguments}))
            """).format(
            brackets = u''.join(brackets_julia_source),
            name = u'.'.join(path_fragments),
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
    parser.add_argument('-f', '--formula',
        help = u'name of the OpenFisca variable to convert (all are converted by default)')
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
    if args.formula:
        columns = [tax_benefit_system.column_by_name[args.formula]]
    else:
        columns = tax_benefit_system.column_by_name.itervalues()
    for column in columns:
        print column.name
        parser.column = column

        column_formula_class = column.formula_class
        assert column_formula_class is not None
        if issubclass(column_formula_class, formulas.SimpleFormula) and column_formula_class.function is None:
            # Input variable
            input_variable_definition_julia_source_by_name[column.name] = parser.source_julia_column_without_function()
            continue
        if issubclass(column_formula_class, formulas.AbstractEntityToEntity):
            # EntityToPerson or PersonToEntity converters
            if issubclass(column_formula_class, formulas.PersonToEntity):
                entity = tax_benefit_system.entity_class_by_key_plural[column.entity_key_plural]
                if column_formula_class.operation is None:
                    role = column_formula_class.roles[0]
                    # print entity.key_singular, role
                    expression = u"single_person_in_entity({variable}, get_entity(variable), {role})".format(
                        role = name_by_role_by_entity_key_singular[entity.key_singular][role],
                        variable = column_formula_class.variable_name,
                        )
                elif column_formula_class.operation == u'add':
                    roles = column_formula_class.roles
                    # print entity.key_singular, roles
                    roles = u', [{}]'.format(u', '.join(
                        name_by_role_by_entity_key_singular[entity.key_singular][role]
                        for role in roles
                        )) if roles else u''
                    expression = u"sum_person_in_entity({variable}, get_entity(variable){roles})".format(
                        roles = roles,
                        variable = column_formula_class.variable_name,
                        )
                elif column_formula_class.operation == u'or':
                    roles = column_formula_class.roles
                    # print entity.key_singular, roles
                    roles = u', [{}]'.format(u', '.join(
                        name_by_role_by_entity_key_singular[entity.key_singular][role]
                        for role in roles
                        )) if roles else u''
                    expression = u"any_person_in_entity({variable}, get_entity(variable){roles})".format(
                        roles = roles,
                        variable = column_formula_class.variable_name,
                        )
                else:
                    assert False, u"Unexpected operation"
            else:
                roles = column_formula_class.roles
                # print entity.key_singular, roles
                roles = u', [{}]'.format(u', '.join(
                    name_by_role_by_entity_key_singular[entity.key_singular][role]
                    for role in roles
                    )) if roles else u''
                expression = u"entity_to_person({variable}{roles})".format(
                    roles = roles,
                    variable = column_formula_class.variable_name,
                    )
            julia_source = textwrap.dedent(u"""
                {call} do simulation, variable, period
                  @calculate({variable}, period, accept_other_period = true)
                  return period, {expression}
                end
                """).format(
                call = parser.source_julia_column_without_function(is_formula = True),
                expression = expression,
                variable = column_formula_class.variable_name,
                )
            module_name = inspect.getmodule(column_formula_class).__name__
            assert module_name.startswith('openfisca_france.model.')
            module_name = module_name[len('openfisca_france.model.'):]
            julia_source_by_name_by_module_name.setdefault(module_name, {})[column.name] = julia_source
            continue

        if column.name in (
                # 'age',  # custom Julia implementation
                # 'age_en_mois',  # custom Julia implementation
                # 'cmu_c_plafond',  # custom Julia implementation
                'coefficient_proratisation',
                # 'nombre_jours_calendaires',  # custom Julia implementation
                # 'remuneration_apprenti',
                # 'zone_apl',  # custom Julia implementation
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

    if args.formula:
        for module_name, julia_source_by_name in julia_source_by_name_by_module_name.iteritems():
            for column_name, julia_source in sorted(julia_source_by_name.iteritems()):
                print(julia_source)
    else:
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
