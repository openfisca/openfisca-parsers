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


"""Parsers for formula-specific lib2to3-based abstract syntax trees"""


from __future__ import division

import collections
import inspect
import itertools
import lib2to3.pgen2.token
import lib2to3.pygram
import lib2to3.pytree
import os
import textwrap

import numpy as np
from openfisca_core import conv


symbols = lib2to3.pygram.python_symbols  # Note: symbols is a module.
tokens = lib2to3.pgen2.token  # Note: tokens is a module.
type_symbol = lib2to3.pytree.type_repr  # Note: type_symbol is a function.


# Monkey patches to support utf-8 strings
lib2to3.pytree.Base.__str__ = lambda self: unicode(self).encode('utf-8')
lib2to3.pytree.Leaf.__unicode__ = lambda self: self.prefix.decode('utf-8') + (self.value.decode('utf-8')
    if isinstance(self.value, str)
    else unicode(self.value)
    )


# Abstract Wrappers


class AbstractWrapper(object):
    container = None  # The wrapper directly containing this wrapper
    hint = None  # A wrapper that is the hinted type of this wrapper
    node = None  # The lib2to3 node
    parser = None

    def __init__(self, container = None, hint = None, node = None, parser = None):
        if container is not None:
            assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
                repr(node), unicode(node).encode('utf-8'))
            self.container = container
        if hint is not None:
            assert isinstance(hint, AbstractWrapper), "Invalid hint {} for node:\n{}\n\n{}".format(hint, repr(node),
                unicode(node).encode('utf-8'))
            self.hint = hint
        if node is not None:
            assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            self.node = node
        assert isinstance(parser, Parser), "Invalid parser {} for node:\n{}\n\n{}".format(parser, repr(node),
            unicode(node).encode('utf-8'))
        self.parser = parser

    @property
    def containing_class(self):
        container = self.container
        if container is None:
            return None
        return container.containing_class

    @property
    def containing_function(self):
        container = self.container
        if container is None:
            return None
        return container.containing_function

    @property
    def containing_module(self):
        container = self.container
        if container is None:
            return None
        return container.containing_module

    def guess(self, expected):
        assert issubclass(expected, AbstractWrapper)
        if isinstance(self, expected):
            return self
        if self.hint is not None:
            guessed = self.hint.guess(expected)
            if guessed is not None:
                return guessed
        return None


# Level-1 Wrappers


class AndExpression(AbstractWrapper):
    operands = None
    operator = None

    def __init__(self, container = None, hint = None, node = None, operands = None, operator = None, parser = None):
        super(AndExpression, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(operands, list)
        self.operands = operands
        assert isinstance(operator, basestring)
        self.operator = operator

    def guess(self, expected):
        guessed = super(AndExpression, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            for operand in self.operands:
                array = operand.guess(parser.Array)
                if array is not None:
                    return parser.Array(
                        cell = parser.Boolean(
                            parser = parser,
                            ),
                        entity_class = array.entity_class,
                        parser = parser,
                        )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.and_expr, "Unexpected and expression type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 3 and (len(children) & 1), \
            "Unexpected length {} of children in and expression:\n{}\n\n{}".format(len(children), repr(node),
            unicode(node).encode('utf-8'))

        child_index = 0
        operands = []
        operator_symbol = None
        while child_index < len(children):
            child = children[child_index]
            operands.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            operator = children[child_index]
            assert operator.type == tokens.AMPER, "Unexpected operator type:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            if operator_symbol is None:
                operator_symbol = operator.value
            else:
                assert operator_symbol == operator.value, "Unexpected operator:\n{}\n\n{}".format(repr(node),
                    unicode(node).encode('utf-8'))
            child_index += 1

        return cls(container = container, node = node, parser = parser, operands = operands, operator = operator_symbol)


class AndTest(AbstractWrapper):
    operands = None
    operator = None

    def __init__(self, container = None, hint = None, node = None, operands = None, operator = None, parser = None):
        super(AndTest, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(operands, list)
        self.operands = operands
        assert isinstance(operator, basestring)
        self.operator = operator

    def guess(self, expected):
        guessed = super(AndTest, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Boolean, expected):
            return parser.Boolean(
                parser = parser,
                )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.and_test, "Unexpected and test type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 3 and (len(children) & 1), \
            "Unexpected length {} of children in and expression:\n{}\n\n{}".format(len(children), repr(node),
            unicode(node).encode('utf-8'))

        child_index = 0
        operands = []
        operator_symbol = None
        while child_index < len(children):
            child = children[child_index]
            operands.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            operator = children[child_index]
            assert operator.type == tokens.NAME and operator.value == u'and', \
                "Unexpected operator type:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            if operator_symbol is None:
                operator_symbol = operator.value
            else:
                assert operator_symbol == operator.value, "Unexpected operator:\n{}\n\n{}".format(repr(node),
                    unicode(node).encode('utf-8'))
            child_index += 1

        return cls(container = container, node = node, parser = parser, operands = operands, operator = operator_symbol)


class ArithmeticExpression(AbstractWrapper):
    items = None

    def __init__(self, container = None, hint = None, items = None, node = None, parser = None):
        super(ArithmeticExpression, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(items, list)
        assert len(items) >= 3 and (len(items) & 1)
        self.items = items

    def guess(self, expected):
        guessed = super(ArithmeticExpression, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            for index, item in enumerate(self.items):
                if index & 1:
                    continue
                array = item.guess(parser.Array)
                if array is not None:
                    return parser.Array(
                        cell = parser.Number(
                            parser = parser,
                            ),
                        entity_class = array.entity_class,
                        parser = parser,
                        )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.arith_expr, "Unexpected arithmetic expression type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 3 and (len(children) & 1), \
            "Unexpected length {} of children in arithmetic expression:\n{}\n\n{}".format(len(children), repr(node),
            unicode(node).encode('utf-8'))

        child_index = 0
        items = []
        while child_index < len(children):
            child = children[child_index]
            items.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            operator = children[child_index]
            assert operator.type in (tokens.MINUS, tokens.PLUS), "Unexpected operator type:\n{}\n\n{}".format(
                repr(node), unicode(node).encode('utf-8'))
            items.append(operator.value)
            child_index += 1

        return cls(container = container, items = items, node = node, parser = parser)


class Array(AbstractWrapper):
    """Wrapper for a NumPy array"""
    cell = None  # Cell wrapper
    entity_class = None
    value = None  # array value, as a numpy array

    def __init__(self, cell = None, container = None, entity_class = None, hint = None, node = None, parser = None,
            value = None):
        super(Array, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if cell is not None:
            assert isinstance(cell, AbstractWrapper), "Unexpected value for cell: {} of type {}".format(cell,
                type(cell))
            self.cell = cell
        if entity_class is not None:
            assert entity_class in parser.tax_benefit_system.entity_class_by_key_plural.itervalues(), \
                "Unexpected value for entity class: {} of type {}".format(entity_class, type(entity_class))
            self.entity_class = entity_class
        if value is not None:
            assert isinstance(value, np.ndarray), "Unexpected value for array: {} of type {}".format(value,
                type(value))
            self.value = value


# class ArrayLength(AbstractWrapper):
#     array = None
#
#     def __init__(self, node, array = None, parser = None):
#         super(ArrayLength, self).__init__(node, parser = parser)
#         if array is not None:
#             self.array = array


class Assert(AbstractWrapper):
    error = None
    test = None

    def __init__(self, container = None, error = None, hint = None, node = None, parser = None, test = None):
        super(Assert, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if error is not None:
            assert isinstance(error, AbstractWrapper)
            self.error = error
        assert isinstance(test, AbstractWrapper)
        self.test = test

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.assert_stmt, "Unexpected assert type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 2, "Unexpected length {} of children in assert:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        assert_word = children[0]
        assert assert_word.type == tokens.NAME and assert_word.value == 'assert'
        test = parser.parse_value(children[1], container = container)
        # TODO
        # error = parser.parse_value(error, container = container)
        error = None

        return cls(container = container, error = error, node = node, parser = parser, test= test)


class Assignment(AbstractWrapper):
    left = None
    operator = None
    right = None

    def __init__(self, container = None, hint = None, left = None, node = None, operator = None, parser = None,
            right = None):
        super(Assignment, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(left, list)
        self.left = left
        assert isinstance(operator, basestring)
        self.operator = operator
        assert isinstance(right, list)
        self.right = right

        if len(left) == len(right) and operator == '=':
            for left_item, right_item in itertools.izip(left, right):
                if isinstance(left_item, parser.Variable):
                    assert left_item is not right_item
                    left_item.value = right_item

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.expr_stmt, "Unexpected assignement type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in assignment:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        left, operator, right = children
        assert operator.type in (tokens.AMPEREQUAL, tokens.EQUAL, tokens.MINEQUAL, tokens.PLUSEQUAL,
            tokens.STAREQUAL), "Unexpected assignment operator:\n{}\n\n{}".format(repr(node), unicode(node).encode(
                'utf-8'))

        # Right items must be parsed before left ones, to avoid reuse of left variables (for example in statements like:
        # period = period).
        right_items = []
        if right.type == symbols.testlist_star_expr:
            assert operator.type == tokens.EQUAL
            right_children = right.children
            child_index = 0
            while child_index < len(right_children):
                right_child = right_children[child_index]
                right_items.append(parser.parse_value(right_child, container = container))
                child_index += 1
                if child_index >= len(right_children):
                    break
                assert right_children[child_index].type == tokens.COMMA
                child_index += 1
        else:
            right_items.append(parser.parse_value(right, container = container))

        left_items = []
        if left.type == symbols.testlist_star_expr:
            assert operator.type == tokens.EQUAL
            left_children = left.children
            child_index = 0
            while child_index < len(left_children):
                left_child = left_children[child_index]
                assert left_child.type == tokens.NAME
                variable = parser.Variable.parse(left_child, container = container, parser = parser)
                left_items.append(variable)
                container.variable_by_name[variable.name] = variable
                child_index += 1
                if child_index >= len(left_children):
                    break
                assert left_children[child_index].type == tokens.COMMA
                child_index += 1
        elif left.type == symbols.power:
            left_items.append(parser.parse_power(left, container = container))
        else:
            assert left.type == tokens.NAME, \
                "Unexpected assignment left operand:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            variable = parser.Variable.parse(left, container = container, parser = parser,
                value = None if operator.type == tokens.EQUAL else container.get_variable(left.value, parser = parser))
            left_items.append(variable)
            container.variable_by_name[variable.name] = variable

        return cls(container = container, left = left_items, node = node, operator = operator.value, parser = parser,
            right = right_items)


class Attribute(AbstractWrapper):
    name = None
    subject = None

    def __init__(self, container = None, hint = None, name = None, node = None, parser = None, subject = None):
        super(Attribute, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(name, basestring)
        self.name = name
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

    def guess(self, expected):
        guessed = super(Attribute, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Boolean, expected):
            compact_node_wrapper = self.subject.guess(parser.CompactNode)
            if compact_node_wrapper is not None:
                child_json = compact_node_wrapper.value['children'][self.name]
                child_type = child_json['@type']
                if child_type == u'Parameter' and child_json.get('format') == 'boolean':
                    return parser.Boolean(parser = parser)
        elif issubclass(parser.CompactNode, expected):
            compact_node = self.subject.guess(parser.CompactNode)
            if compact_node is not None:
                child_json = compact_node.value['children'].get(self.name)
                if child_json is not None:
                    child_type = child_json['@type']
                    if child_type == u'Node':
                        return parser.CompactNode(is_reference = compact_node.is_reference, name = self.name,
                            parent = compact_node, parser = parser, value = child_json)
        elif issubclass(parser.Date, expected):
            if self.name == 'date':
                period = self.subject.guess(parser.Period)
                if period is not None:
                    return parser.Date(parser = parser)
        elif issubclass(parser.Entity, expected):
            if self.name == 'entity':
                holder = self.subject.guess(parser.Holder)
                if holder is not None:
                    entity_class = parser.tax_benefit_system.entity_class_by_key_plural[holder.column.entity_key_plural]
                    return parser.Entity(entity_class = entity_class, parser = parser)
        elif issubclass(parser.FormulaClass, expected):
            if self.name == '__class__':
                formula = self.subject.guess(parser.Formula)
                if formula is not None:
                    return formula.formula_class
        elif issubclass(parser.Holder, expected):
            if self.name == 'holder':
                formula = self.subject.guess(parser.Formula)
                if formula is not None:
                    return parser.Holder(column = formula.column, parser = parser)
        elif issubclass(parser.Instant, expected):
            if self.name == 'start':
                    period = self.subject.guess(parser.Period)
                    if period is not None:
                        return parser.Instant(parser = parser)
        elif issubclass(parser.Number, expected):
            if self.name == 'count':
                entity = self.subject.guest(parser.Entity)
                if entity is not None:
                    return parser.Number(parser = parser)
            compact_node_wrapper = self.subject.guess(parser.CompactNode)
            if compact_node_wrapper is not None:
                child_json = compact_node_wrapper.value['children'][self.name]
                child_type = child_json['@type']
                if child_type == u'Parameter' and child_json.get('format') != 'boolean':
                    return parser.Number(parser = parser)
        elif issubclass(parser.String, expected):
            if self.name == '__name__':
                formula_class = self.subject.guess(parser.FormulaClass)
                if formula_class is not None:
                    return parser.String(parser = parser, value = parser.column.name)
        elif issubclass(parser.TaxScale, expected):
            compact_node_wrapper = self.subject.guess(parser.CompactNode)
            if compact_node_wrapper is not None:
                child_json = compact_node_wrapper.value['children'][self.name]
                child_type = child_json['@type']
                if child_type == u'Scale':
                    return parser.TaxScale(parser = parser)
        elif issubclass(parser.UniformDictionary, expected):
            if self.name == '_array_by_period':
                holder = self.subject.guess(parser.Holder)
                if holder is not None:
                    column = holder.column
                    entity_class = parser.tax_benefit_system.entity_class_by_key_plural[column.entity_key_plural]
                    cell_wrapper = parser.get_cell_wrapper(container = self.container, type = column.dtype)
                    return parser.UniformDictionary(
                        key = parser.Period(
                            parser = parser,
                            ),
                        parser = parser,
                        value = parser.Array(
                            cell = cell_wrapper,
                            entity_class = parser.entity_class,
                            parser = parser,
                            ),
                        )

        return None

    @classmethod
    def parse(cls, subject, node, container = None, parser = None):
        assert node.type == symbols.trailer, "Unexpected attribute type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, "Unexpected length {} of children in power attribute:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        dot, attribute = children
        assert dot.type == tokens.DOT, "Unexpected dot type:\n{}\n\n{}".format(repr(dot), unicode(dot).encode('utf-8'))
        assert attribute.type == tokens.NAME, "Unexpected attribute type:\n{}\n\n{}".format(repr(attribute),
            unicode(attribute).encode('utf-8'))
        return cls(container = container, name = attribute.value, node = node, parser = parser, subject = subject)


class Call(AbstractWrapper):
    keyword_argument = None
    named_arguments = None
    positional_arguments = None
    star_argument = None
    subject = None

    def __init__(self, container = None, hint = None, keyword_argument = None, named_arguments = None, node = None,
            parser = None, positional_arguments = None, star_argument = None, subject = None):
        super(Call, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if keyword_argument is not None:
            assert isinstance(keyword_argument, AbstractWrapper)
            self.keyword_argument = keyword_argument
        if named_arguments is None:
            named_arguments = collections.OrderedDict()
        else:
            assert isinstance(named_arguments, collections.OrderedDict)
        self.named_arguments = named_arguments
        if positional_arguments is None:
            positional_arguments = []
        else:
            assert isinstance(positional_arguments, list)
        self.positional_arguments = positional_arguments
        if star_argument is not None:
            assert isinstance(star_argument, AbstractWrapper)
            self.star_argument = star_argument
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

        function = subject.guess(parser.Function)
        if function is not None:
            function.parse_call(self)

    def guess(self, expected):
        guessed = super(Call, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser

        function = self.subject.guess(parser.Function)
        if function is not None:
            if issubclass(parser.Array, expected):
                if function.name in (u'age_aine', u'age_en_mois_benjamin', u'nb_enf'):
                    return parser.Array(
                        cell = parser.Number(
                            parser = parser,
                            ),
                        parser = parser,
                        )
            assert function.returns, "Function {} has no return statement".format(function.name)
            return function.returns[-1].guess(expected)

        if issubclass(parser.Array, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name in (u'and_', u'or_', u'xor_'):
                    for argument in self.positional_arguments:
                        array = argument.guess(parser.Array)
                        if array is not None:
                            return parser.Array(
                                cell = parser.Boolean(
                                    parser = parser,
                                    ),
                                entity_class = array.entity_class,
                                parser = parser,
                                )
                elif function.name in (u'floor', u'max_', u'min_', u'round_'):
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
                elif function.name == 'not_':
                    assert len(self.positional_arguments) == 1
                    argument = self.positional_arguments[0]
                    array = argument.guess(parser.Array)
                    if array is not None:
                        return parser.Array(
                            cell = parser.Boolean(
                                parser = parser,
                                ),
                            entity_class = array.entity_class,
                            parser = parser,
                            )
            else:
                method = self.subject.guess(parser.Attribute)
                if method is not None:
                    if method.name in ('all', 'any'):
                        return parser.Boolean(
                            parser = parser,
                            )
                    if method.name in ('any_by_roles', 'sum_by_entity'):
                        assert len(self.positional_arguments) == 1, self.positional_arguments
                        assert len(self.named_arguments) == 0, self.named_arguments
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
                    if method.name in ('calculate', 'calculate_add', 'calculate_add_divide', 'calculate_divide',
                            'get_array'):
                        assert len(self.positional_arguments) >= 1
                        variable_name_wrapper = self.positional_arguments[0].guess(parser.String)
                        if variable_name_wrapper is None:
                            cell_wrapper = None
                            entity_class = None
                        else:
                            tax_benefit_system = parser.tax_benefit_system
                            column = tax_benefit_system.column_by_name[variable_name_wrapper.value]
                            cell_wrapper = parser.get_cell_wrapper(container = self.container, type = column.dtype)
                            entity_class = tax_benefit_system.entity_class_by_key_plural[column.entity_key_plural]
                        return parser.Array(
                            cell = cell_wrapper,
                            entity_class = entity_class,
                            parser = parser,
                            )
                    if method.name in ('cast_from_entity_to_role', 'cast_from_entity_to_roles'):
                        assert len(self.positional_arguments) >= 1
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
                    if method.name == 'filter_role':
                        assert len(self.positional_arguments) >= 1
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
        elif issubclass(parser.Boolean, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name == 'hasattr':
                    return parser.Boolean(parser = parser)
        elif issubclass(parser.CompactNode, expected):
            method = self.subject.guess(parser.Attribute)
            if method is not None:
                if method.name == 'legislation_at':
                    method_subject = method.subject
                    if method_subject.guess(parser.Simulation):
                        positional_arguments = self.positional_arguments
                        assert len(positional_arguments) == 1, positional_arguments
                        instant = positional_arguments[0].guess(parser.Instant)
                        if instant is not None:
                            named_arguments = self.named_arguments
                            assert len(named_arguments) <= 1, named_arguments
                            reference = named_arguments.get('reference')
                            assert reference is None
                            return parser.CompactNode(
                                is_reference = bool(reference),
                                parser = parser,
                                value = parser.tax_benefit_system.get_legislation(),
                                )
        elif issubclass(parser.Date, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name == 'date':
                    return parser.Date(parser = parser)
        elif issubclass(parser.DatedHolder, expected):
            method = self.subject.guess(parser.Attribute)
            if method is not None:
                if method.name in ('compute', 'compute_add', 'compute_add_divide', 'compute_divide'):
                    assert len(self.positional_arguments) >= 1
                    variable_name_wrapper = self.positional_arguments[0].guess(parser.String)
                    if variable_name_wrapper is None:
                        column = None
                    else:
                        column = parser.tax_benefit_system.column_by_name[variable_name_wrapper.value]
                    return parser.DatedHolder(
                        column = column,
                        parser = parser,
                        )
        elif issubclass(parser.Instant, expected):
            method = self.subject.guess(parser.Attribute)
            if method is not None:
                if method.name == 'offset':
                    if method.subject.guess(parser.Instant) is not None:
                        return parser.Instant(parser = parser)
        elif issubclass(parser.Number, expected):
            function = self.subject.guess(parser.Variable)
            if function is not None:
                if function.name == 'len':
                    return parser.Number(parser = parser)
        elif issubclass(parser.Period, expected):
            method = self.subject.guess(parser.Attribute)
            if method is not None:
                if method.name == 'offset':
                    period = method.subject.guess(parser.Period)
                    if period is not None:
                        # period.offset(...)
                        return parser.Period(parser = parser, unit = period.unit)
                elif method.name == 'period':
                    if method.subject.guess(parser.Instant):
                        # instant.period(...)
                        assert len(self.positional_arguments) >= 1
                        unit = self.positional_arguments[0].guess(parser.String)
                        if unit is not None:
                            assert unit.value is not None, 'Missing value in unit string'
                            return parser.Period(parser = parser, unit = unit.value)
        elif issubclass(parser.TaxScale, expected):
            method = self.subject.guess(parser.Attribute)
            if method is not None:
                if method.name == 'calc':
                    if method.subject.guess(parser.Instant) is not None:
                        return parser.TaxScale(parser = parser)
        elif issubclass(parser.UniformDictionary, expected):
            method = self.subject.guess(parser.Attribute)
            if method is not None:
                if method.name == 'split_by_roles':
                    assert len(self.positional_arguments) == 1, self.positional_arguments
                    assert len(self.named_arguments) <= 1, self.named_arguments
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
                if function.name == 'sorted':
                    assert len(self.positional_arguments) >= 1
                    argument = self.positional_arguments[0]
                    uniform_iterator = argument.guess(expected)
                    if uniform_iterator is not None:
                        return uniform_iterator
                    uniform_dictionary = argument.guess(parser.UniformDictionary)
                    if uniform_dictionary is not None:
                        return uniform_dictionary.guess(expected)
            else:
                method = self.subject.guess(parser.Attribute)
                if method is not None:
                    if method.name == 'iterkeys':
                        uniform_dictionary = method.subject.guess(parser.UniformDictionary)
                        if uniform_dictionary is not None:
                            return parser.UniformIterator(
                                items = [uniform_dictionary.key],
                                parser = parser,
                                )
                    elif method.name == 'iteritems':
                        uniform_dictionary = method.subject.guess(parser.UniformDictionary)
                        if uniform_dictionary is not None:
                            return parser.UniformIterator(
                                items = [
                                    uniform_dictionary.key,
                                    uniform_dictionary.value,
                                    ],
                                parser = parser,
                                )
                    elif method.name == 'itervalues':
                        uniform_dictionary = method.subject.guess(parser.UniformDictionary)
                        if uniform_dictionary is not None:
                            return parser.UniformIterator(
                                items = [uniform_dictionary.value],
                                parser = parser,
                                )

        return None

    @classmethod
    def parse(cls, subject, node, container = None, parser = None):
        if node is None:
            children = []
        elif node.type == symbols.arglist:
            children = node.children
        else:
            children = [node]
        keyword_argument = None
        named_arguments = collections.OrderedDict()
        positional_arguments = []
        star_argument = None
        child_index = 0
        while child_index < len(children):
            argument = children[child_index]
            if argument.type == symbols.argument:
                # Named argument
                argument_children = argument.children
                assert len(argument_children) == 3, "Unexpected length {} of children in argument:\n{}\n\n{}".format(
                    len(argument_children), repr(argument), unicode(argument).encode('utf-8'))
                argument_name, equal, argument_value = argument_children
                assert argument_name.type == tokens.NAME, "Unexpected name type:\n{}\n\n{}".format(repr(argument_name),
                    unicode(argument_name).encode('utf-8'))
                assert equal.type == tokens.EQUAL, "Unexpected equal type:\n{}\n\n{}".format(repr(equal),
                    unicode(equal).encode('utf-8'))
                named_arguments[argument_name.value] = parser.parse_value(argument_value, container = container)
            else:
                # Positional argument
                if argument.type == tokens.STAR:
                    child_index += 1
                    argument = children[child_index]
                    if argument.type == tokens.STAR:
                        child_index += 1
                        argument = children[child_index]
                        keyword_argument = parser.parse_value(argument, container = container)
                    else:
                        star_argument = parser.parse_value(argument, container = container)
                else:
                    positional_arguments.append(parser.parse_value(argument, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            child = children[child_index]
            assert child.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(child),
                unicode(child).encode('utf-8'))
            child_index += 1
        return cls(container = container, keyword_argument = keyword_argument, named_arguments = named_arguments,
            node = node, parser = parser, positional_arguments = positional_arguments, star_argument = star_argument,
            subject = subject)


class Class(AbstractWrapper):
    base_class_name = None
    name = None
    variable_by_name = None

    def __init__(self, base_class_name = None, container = None, name = None, node = None, parser = None,
            variable_by_name = None):
        super(Class, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(base_class_name, basestring)
        self.base_class_name = base_class_name
        assert isinstance(name, basestring)
        self.name = name
        if variable_by_name is None:
            variable_by_name = collections.OrderedDict()
        else:
            assert isinstance(variable_by_name, collections.OrderedDict)
        self.variable_by_name = variable_by_name

    @property
    def containing_class(self):
        return self

    @classmethod
    def get_function_class(cls, parser = None):
        return parser.Function

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            container = self.container
            if container is not None:
                return container.get_variable(name, default = default, parser = parser)
            # TODO: Handle class inheritance.
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            variable = default
        return variable

    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 7, len(children)
            assert children[0].type == tokens.NAME and children[0].value == 'class'
            assert children[1].type == tokens.NAME
            name = children[1].value
            assert children[2].type == tokens.LPAR and children[2].value == '('
            assert children[3].type == tokens.NAME
            base_class_name = children[3].value
            assert children[4].type == tokens.RPAR and children[4].value == ')'
            assert children[5].type == tokens.COLON and children[5].value == ':'

            variable_by_name = collections.OrderedDict()
            self = cls(base_class_name = base_class_name, container = container, name = name, node = node,
                parser = parser, variable_by_name = variable_by_name)

            suite = children[6]
            assert suite.type == symbols.suite
            suite_children = suite.children
            assert len(suite_children) > 2, len(suite_children)
            assert suite_children[0].type == tokens.NEWLINE and suite_children[0].value == '\n'
            assert suite_children[1].type == tokens.INDENT and suite_children[1].value == '    '
            for suite_child in itertools.islice(suite_children, 2, None):
                if suite_child.type == symbols.decorated:
                    decorator = parser.Decorator.parse(suite_child, container = self, parser = parser)
                    variable_by_name[decorator.decorated.name] = parser.Variable(container = self,
                        name = decorator.name, parser = parser, value = decorator)
                elif suite_child.type == symbols.funcdef:
                    function = cls.get_function_class(parser = parser).parse(suite_child, container = self,
                        parser = parser)
                    variable_by_name[function.name] = parser.Variable(container = self, name = function.name,
                        parser = parser, value = function)
                elif suite_child.type == symbols.simple_stmt:
                    assert len(suite_child.children) == 2, len(suite_child.children)
                    expression = suite_child.children[0]
                    assert expression.type in (symbols.expr_stmt, tokens.STRING), expression.type
                    assert suite_child.children[1].type == tokens.NEWLINE and suite_child.children[1].value == '\n'
                elif suite_child.type == tokens.DEDENT:
                    continue
                else:
                    assert False, "Unexpected statement in class definition:\n{}\n\n{}".format(repr(suite_child),
                        unicode(suite_child).encode('utf-8'))
            return self
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class ClassFileInput(AbstractWrapper):
    @classmethod
    def get_class_class(cls, parser = None):
        return parser.Class

    @classmethod
    def parse(cls, class_definition, parser = None):
        source_lines, line_number = inspect.getsourcelines(class_definition)
        source = textwrap.dedent(''.join(source_lines))
        node = parser.driver.parse_string(source)
        assert node.type == symbols.file_input, "Unexpected file input type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2 and children[0].type == symbols.classdef and children[1].type == tokens.ENDMARKER, \
            "Unexpected node children in:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        python_module = inspect.getmodule(class_definition)
        if parser.country_package is not None:
            assert python_module.__file__.startswith(os.path.dirname(parser.country_package.__file__)), \
                "Requested class is defined outside country_package:\n{}".format(source)
        module = parser.python_module_by_name.get(python_module.__name__)
        if module is None:
            parser.python_module_by_name[python_module.__name__] = module = parser.Module(node, python = python_module,
                parser = parser)
        self = cls(parser = parser)
        class_definition_class = self.get_class_class(parser = parser)
        try:
            return class_definition_class.parse(children[0], container = module, parser = parser)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class CompactNode(AbstractWrapper):
    is_reference = True
    name = None
    parent = None  # Parent Compact Node wrapper
    value = None  # Law node JSON

    def __init__(self, is_reference = False, name = None, parent = None, parser = None, value = None):
        super(CompactNode, self).__init__(parser = parser)
        if not is_reference:
            self.is_reference = False
        assert (parent is None) == (name is None), str((name, parent))
        if name is not None:
            self.name = name
        if parent is not None:
            assert isinstance(parent, CompactNode)
            self.parent = parent
        if value is not None:
            assert isinstance(value, dict)
            self.value = value

    def iter_names(self):
        parent = self.parent
        if parent is not None:
            for ancestor_name in parent.iter_names():
                yield ancestor_name
        name = self.name
        if name is not None:
            yield name

    @property
    def path(self):
        return '.'.join(self.iter_names())


class Comparison(AbstractWrapper):
    left = None
    operator = None
    right = None

    def __init__(self, container = None, hint = None, left = None, node = None, operator = None, parser = None,
            right = None):
        super(Comparison, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(left, AbstractWrapper)
        self.left = left
        assert isinstance(operator, basestring)
        self.operator = operator
        assert isinstance(right, AbstractWrapper)
        self.right = right

    def guess(self, expected):
        guessed = super(Comparison, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            left_array = self.left.guess(parser.Array)
            if left_array is not None:
                return parser.Array(
                    cell = parser.get_cell_wrapper(container = self.container, type = bool),
                    entity_class = left_array.entity_class,
                    parser = parser,
                    )
            left_dated_holder = self.left.guess(parser.DatedHolder)
            if left_dated_holder is not None:
                return parser.Array(
                    cell = parser.get_cell_wrapper(container = self.container, type = bool),
                    entity_class = left_dated_holder.entity_class,
                    parser = parser,
                    )
            right_array = self.right.guess(parser.Array)
            if right_array is not None:
                return parser.Array(
                    cell = parser.get_cell_wrapper(container = self.container, type = bool),
                    entity_class = right_array.entity_class,
                    parser = parser,
                    )
            right_dated_holder = self.right.guess(parser.DatedHolder)
            if right_dated_holder is not None:
                return parser.Array(
                    cell = parser.get_cell_wrapper(container = self.container, type = bool),
                    entity_class = right_dated_holder.entity_class,
                    parser = parser,
                    )
        elif issubclass(parser.Boolean, expected):
            return parser.Boolean(
                parser = parser,
                )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.comparison, "Unexpected comparison type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in comparison:\n{}\n\n{}".format(len(children),
            repr(node), unicode(node).encode('utf-8'))
        left, operator, right = children
        left = parser.parse_value(left, container = container)
        if operator.type == tokens.NAME:
            assert operator.value in ('in', 'is'), "Unexpected operator type:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            operator_symbol = operator.value
        elif operator.type == symbols.comp_op:
            operator_children = operator.children
            assert len(operator_children) == 2, "Unexpected length {} of children in comp_op:\n{}\n\n{}".format(
                len(operator_children), repr(node), unicode(node).encode('utf-8'))
            first_word, second_word = operator_children
            if first_word.type == tokens.NAME and first_word.value == 'is' and second_word.type == tokens.NAME \
                    and second_word.value == 'not':
                operator_symbol = 'is not'
            elif first_word.type == tokens.NAME and first_word.value == 'not' and second_word.type == tokens.NAME \
                    and second_word.value == 'in':
                operator_symbol = 'not in'
            else:
                assert False, "Unexpected comp_op children:\n{}\n\n{}".format(repr(node),
                    unicode(node).encode('utf-8'))
        else:
            assert operator.type in (
                tokens.EQEQUAL,
                tokens.GREATER,
                tokens.GREATEREQUAL,
                tokens.LESS,
                tokens.LESSEQUAL,
                tokens.NOTEQUAL,
                ), "Unexpected operator type:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            operator_symbol = operator.value
        right = parser.parse_value(right, container = container)

        return cls(container = container, left = left, node = node, parser = parser, operator = operator_symbol,
            right = right)


class Continue(AbstractWrapper):
    pass


class Date(AbstractWrapper):
    pass


class DatedHolder(AbstractWrapper):
    column = None
    value = None  # array value, as a numpy array

    def __init__(self, column = None, container = None, hint = None, node = None, parser = None, value = None):
        super(DatedHolder, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if column is not None:
            assert column in parser.tax_benefit_system.column_by_name.itervalues(), \
                "Unexpected value for column: {} of type {}".format(column, type(column))
            self.column = column
        if value is not None:
            assert isinstance(value, np.ndarray), "Unexpected value for array: {} of type {}".format(value,
                type(value))
            self.value = value

    @property
    def cell(self):
        if self.column is None:
            return None
        return self.parser.get_cell_wrapper(container = self.container, type = self.column.dtype)

    @property
    def entity_class(self):
        if self.column is None:
            return None
        return self.parser.tax_benefit_system.entity_class_by_key_plural[self.column.entity_key_plural]


class DateTime64(AbstractWrapper):
    pass


class Decorator(AbstractWrapper):
    decorated = None
    name = None
    subject = None  # The decorator

    def __init__(self, container = None, decorated = None, name = None, node = None, parser = None, subject = None):
        super(Decorator, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(decorated, AbstractWrapper)
        self.decorated = decorated
        assert isinstance(name, basestring)
        self.name = name
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 2, len(children)

            decorator = children[0]
            assert decorator.type == symbols.decorator
            decorator_children = decorator.children
            assert len(decorator_children) == 6, len(decorator_children)
            assert decorator_children[0].type == tokens.AT and decorator_children[0].value == '@'
            subject = parser.Variable.parse(decorator_children[1], container = container, parser = parser)
            name = decorator_children[1].value
            assert decorator_children[2].type == tokens.LPAR and decorator_children[2].value == '('
            subject = parser.Call.parse(subject, decorator_children[3], container = container, parser = parser)
            assert decorator_children[4].type == tokens.RPAR and decorator_children[4].value == ')'
            assert decorator_children[5].type == tokens.NEWLINE and decorator_children[5].value == '\n'
            subject = subject

            decorated = children[1]
            assert decorated.type == symbols.funcdef
            decorated = container.get_function_class(parser = parser).parse(decorated, container = container,
                parser = parser)

            return cls(container = container, decorated = decorated, name = name, node = node, parser = parser,
                subject = subject)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class Dictionary(AbstractWrapper):
    value = None  # Dictionary value, as a dict

    def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
        super(Dictionary, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(value, dict), "Unexpected value for dictionary: {} of type {}".format(value,
            type(value))
        self.value = value


class Enum(AbstractWrapper):
    value = None

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(Enum, self).__init__(container = container, node = node, parser = parser)
        if value is not None:
            self.value = value

    def guess(self, expected):
        guessed = super(Enum, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.UniformIterator, expected):
            return parser.UniformIterator(
                items = [
                    # Item label
                    parser.String(
                        parser = parser,
                        ),
                    # Item index
                    parser.Number(
                        parser = parser,
                        ),
                    ],
                parser = parser,
                )

        return None


class Entity(AbstractWrapper):
    entity_class = None

    def __init__(self, container = None, entity_class = None, hint = None, node = None, parser = None):
        super(Entity, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert entity_class is not None
        self.entity_class = entity_class


class Expression(AbstractWrapper):
    operands = None
    operator = None

    def __init__(self, container = None, hint = None, node = None, operands = None, operator = None, parser = None):
        super(Expression, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(operands, list)
        self.operands = operands
        assert isinstance(operator, basestring)
        self.operator = operator

    def guess(self, expected):
        guessed = super(Expression, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            for operand in self.operands:
                array = operand.guess(parser.Array)
                if array is not None:
                    return parser.Array(
                        cell = parser.Boolean(
                            parser = parser,
                            ),
                        entity_class = array.entity_class,
                        parser = parser,
                        )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.expr, "Unexpected expression type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 3 and (len(children) & 1), \
            "Unexpected length {} of children in expression:\n{}\n\n{}".format(len(children), repr(node),
            unicode(node).encode('utf-8'))

        child_index = 0
        operands = []
        operator_symbol = None
        while child_index < len(children):
            child = children[child_index]
            operands.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            operator = children[child_index]
            assert operator.type == tokens.VBAR, "Unexpected operator type:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            if operator_symbol is None:
                operator_symbol = operator.value
            else:
                assert operator_symbol == operator.value, "Unexpected operator:\n{}\n\n{}".format(repr(node),
                    unicode(node).encode('utf-8'))
            child_index += 1

        return cls(container = container, node = node, parser = parser, operands = operands, operator = operator_symbol)


class Factor(AbstractWrapper):
    operand = None
    operator = None

    def __init__(self, container = None, hint = None, node = None, operand = None, operator = None, parser = None):
        super(Factor, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(operand, AbstractWrapper)
        self.operand = operand
        assert isinstance(operator, basestring)
        self.operator = operator

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.factor, "Unexpected factor type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, "Unexpected length {} of children in factor:\n{}\n\n{}".format(len(children),
            repr(node), unicode(node).encode('utf-8'))
        operator, operand = children
        assert operator.type in (tokens.MINUS, tokens.TILDE), "Unexpected operator type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        operand = parser.parse_value(operand, container = container)
        return cls(container = container, node = node, operand = operand, operator = operator.value, parser = parser)


class For(AbstractWrapper):
    body = None
    iterator = None
    variable_by_name = None

    def __init__(self, container = None, hint = None, iterator = None, node = None, body = None, parser = None,
            variable_by_name = None):
        super(For, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if body is not None:
            assert isinstance(body, list)
            self.body = body
        assert isinstance(iterator, AbstractWrapper)
        self.iterator = iterator
        guessed_iterator = iterator.guess(parser.UniformIterator)
        if guessed_iterator is None:
            if len(variable_by_name) == 1 and 'bar' in variable_by_name:
                guessed_iterator = parser.UniformIterator(
                    container = container,
                    items = [
                        parser.TaxScale(
                            container = container,
                            parser = parser,
                            ),
                        ],
                    parser = parser,
                    )
            else:
                assert False, "{} has no iterator".format(iterator)

        assert isinstance(variable_by_name, collections.OrderedDict)
        for variable, value in itertools.izip(variable_by_name.itervalues(), guessed_iterator.items):
            variable.value = value
        self.variable_by_name = variable_by_name
        container.variable_by_name.update(variable_by_name)

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.for_stmt, "Unexpected for statement type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 6, "Unexpected length {} of children in for statement:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        for_word, variables, in_word, iterator, colon, body = children
        assert for_word.type == tokens.NAME and for_word.value == 'for'
        variable_by_name = collections.OrderedDict()
        if variables.type == symbols.exprlist:
            variables = variables.children
            variable_index = 0
            while variable_index < len(variables):
                variable = variables[variable_index]
                assert variable.type == tokens.NAME
                variable_name = variable.value
                variable_by_name[variable_name] = parser.Variable(container = container, name = variable_name,
                    parser = parser)
                variable_index += 1
                if variable_index >= len(variables):
                    break
                comma = variables[variable_index]
                assert comma.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(comma),
                    unicode(comma).encode('utf-8'))
                variable_index += 1
        elif variables.type == tokens.NAME:
            variable_name = variables.value
            variable_by_name[variable_name] = parser.Variable(container = container, name = variable_name,
                parser = parser)
        else:
            assert False, "Unexpected variables in for statement:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
        assert in_word.type == tokens.NAME and in_word.value == 'in'
        iterator = parser.parse_value(iterator, container = container)
        assert colon.type == tokens.COLON and colon.value == ':'

        self = cls(container = container, iterator = iterator, parser = parser, variable_by_name = variable_by_name)
        self.body = parser.parse_suite(body, container = container)

        return self


class Function(AbstractWrapper):
    body = None
    body_parsed = False
    keyword_name = None  # Name of "kwargs" in "**kwargs"
    name = None
    named_parameters = None  # Dictionary of parameter name => default value
    positional_parameters = None  # List of parameters names
    returns = None  # List of Return wrappers present in function
    star_name = None  # Name of "args" in "*args"
    variable_by_name = None

    def __init__(self, body = None, container = None, hint = None, name = None, keyword_name = None,
            named_parameters = None, node = None, parser = None, positional_parameters = None, returns = None,
            star_name = None, variable_by_name = None):
        super(Function, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if body is None:
            body = []
        else:
            assert isinstance(body, list)
            if body:
                self.body_parsed = True
        self.body = body
        if keyword_name is not None:
            assert isinstance(keyword_name, basestring)
            self.keyword_name = keyword_name
        assert isinstance(name, basestring)
        self.name = name
        if named_parameters is None:
            named_parameters = collections.OrderedDict()
        else:
            assert isinstance(named_parameters, collections.OrderedDict)
        self.named_parameters = named_parameters
        if positional_parameters is None:
            positional_parameters = []
        else:
            assert isinstance(positional_parameters, list)
        self.positional_parameters = positional_parameters
        if returns is None:
            returns = []
        else:
            assert isinstance(returns, list)
        self.returns = returns
        if star_name is not None:
            assert isinstance(star_name, basestring)
            self.star_name = star_name
        if variable_by_name is None:
            variable_by_name = collections.OrderedDict()
        else:
            assert isinstance(variable_by_name, collections.OrderedDict)
        self.variable_by_name = variable_by_name

    @property
    def containing_function(self):
        return self

    @classmethod
    def get_function_class(cls, parser = None):
        return parser.Function

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            container = self.container
            if container is not None:
                return container.get_variable(name, default = default, parser = parser)
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            variable = default
        return variable

    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 5
            assert children[0].type == tokens.NAME and children[0].value == 'def'
            assert children[1].type == tokens.NAME  # Function name
            name = children[1].value

            self = cls(container = container, name = name, node = node, parser = parser)
            self.parse_parameters()
            # Don't parse body now. Wait for first call (to know the values of the parameters).
            # self.parse_body()
            return self
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise

    def parse_body(self):
        parser = self.parser
        children = self.node.children
        assert len(children) == 5

        self.body_parsed = True
        body = parser.parse_suite(children[4], container = self)
        self.body[:] = body

    def parse_call(self, call):
        if not self.body_parsed:
            parser = self.parser

            positional_arguments = call.positional_arguments
            if call.star_argument is not None:
                positional_arguments = positional_arguments + list(call.star_argument.value.value)
            for argument_name, argument_value in itertools.izip(self.positional_parameters, positional_arguments):
                self.variable_by_name[argument_name].value = argument_value
            if self.star_name is not None:
                self.variable_by_name[self.star_name].value = parser.Tuple(
                    container = self,
                    parser = parser,
                    value = tuple(positional_arguments[len(self.positional_parameters):]),
                    )

            named_arguments = call.named_arguments
            if call.keyword_argument is not None:
                named_arguments = named_arguments.copy()
                named_arguments.update(call.keyword_argument.value.value)
            keyword_argument = {}
            for argument_name, argument_value in named_arguments.iteritems():
                if argument_name in self.named_parameters:
                    self.variable_by_name[argument_name].value = argument_value
                else:
                    keyword_argument[argument_name] = argument_value
            if self.keyword_name is not None:
                self.variable_by_name[self.keyword_name].value = parser.Dictionary(
                    container = self,
                    parser = parser,
                    value = keyword_argument,
                    )

            self.parse_body()

    def parse_parameters(self):
        parser = self.parser
        children = self.node.children
        assert len(children) == 5

        parameters = children[2]
        assert parameters.type == symbols.parameters
        parameters_children = parameters.children
        assert 2 <= len(parameters_children) <= 3, \
            "Unexpected length {} of children in parameters statement:\n{}\n\n{}".format(len(parameters_children),
                repr(parameters), unicode(parameters).encode('utf-8'))

        assert parameters_children[0].type == tokens.LPAR and parameters_children[0].value == '('

        if len(parameters_children) == 3:
            if parameters_children[1].type == tokens.NAME:
                # Single positional parameter
                typedargslist = None
                typedargslist_children = [parameters_children[1]]
            else:
                typedargslist = parameters_children[1]
                assert typedargslist.type == symbols.typedargslist
                typedargslist_children = typedargslist.children

            typedargslist_child_index = 0
            while typedargslist_child_index < len(typedargslist_children):
                typedargslist_child = typedargslist_children[typedargslist_child_index]
                if typedargslist_child.type == tokens.DOUBLESTAR:
                    typedargslist_child_index += 1
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    assert typedargslist_child.type == tokens.NAME, "Unexpected typedargslist child:\n{}\n\n{}".format(
                        repr(typedargslist_child), unicode(typedargslist_child).encode('utf-8'))
                    self.keyword_name = typedargslist_child.value
                    self.variable_by_name[self.keyword_name] = parser.Variable(container = self,
                        name = self.keyword_name, parser = parser)
                    typedargslist_child_index += 1
                    if typedargslist_child_index >= len(typedargslist_children):
                        break
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    assert typedargslist_child.type == tokens.COMMA
                    typedargslist_child_index += 1
                elif typedargslist_child.type == tokens.STAR:
                    typedargslist_child_index += 1
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    assert typedargslist_child.type == tokens.NAME, "Unexpected typedargslist child:\n{}\n\n{}".format(
                        repr(typedargslist_child), unicode(typedargslist_child).encode('utf-8'))
                    self.star_name = typedargslist_child.value
                    self.variable_by_name[self.star_name] = parser.Variable(container = self, name = self.star_name,
                        parser = parser)
                    typedargslist_child_index += 1
                    if typedargslist_child_index >= len(typedargslist_children):
                        break
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    assert typedargslist_child.type == tokens.COMMA
                    typedargslist_child_index += 1
                else:
                    assert typedargslist_child.type == tokens.NAME, "Unexpected typedargslist child:\n{}\n\n{}".format(
                        repr(typedargslist_child), unicode(typedargslist_child).encode('utf-8'))
                    parameter_name = typedargslist_child.value
                    typedargslist_child_index += 1
                    if typedargslist_child_index >= len(typedargslist_children):
                        # Last positional parameter
                        self.positional_parameters.append(parameter_name)
                        self.variable_by_name[parameter_name] = parser.Variable(container = self, name = parameter_name,
                            parser = parser)
                        break
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    if typedargslist_child.type == tokens.COMMA:
                        # Positional parameter
                        self.positional_parameters.append(parameter_name)
                        self.variable_by_name[parameter_name] = parser.Variable(container = self, name = parameter_name,
                            parser = parser)
                        typedargslist_child_index += 1
                    elif typedargslist_child.type == tokens.EQUAL:
                        # Named parameter
                        typedargslist_child_index += 1
                        typedargslist_child = typedargslist_children[typedargslist_child_index]
                        self.named_parameters[parameter_name] = parser.parse_value(typedargslist_child,
                            container = self)
                        self.variable_by_name[parameter_name] = parser.Variable(container = self, name = parameter_name,
                            parser = parser)
                        typedargslist_child_index += 1
                        if typedargslist_child_index >= len(typedargslist_children):
                            break
                        typedargslist_child = typedargslist_children[typedargslist_child_index]
                        assert typedargslist_child.type == tokens.COMMA
                        typedargslist_child_index += 1

        assert parameters_children[-1].type == tokens.RPAR and parameters_children[-1].value == ')'

        assert children[3].type == tokens.COLON and children[3].value == ':'


# class FunctionCall(AbstractWrapper):
#     definition = None
#     variable_by_name = None

#     def __init__(self, node, definition = None, parser = None):
#         super(FunctionCall, self).__init__(node, parser = parser)
#         assert isinstance(definition, Function)
#         self.definition = definition
#         self.variable_by_name = collections.OrderedDict()

#     def get_variable(self, name, default = UnboundLocalError, parser = None):
#         variable = self.variable_by_name.get(name, None)
#         if variable is None:
#             container = self.definition.container
#             if container is not None:
#                 return container.get_variable(name, default = default, parser = parser)
#             if default is UnboundLocalError:
#                 raise KeyError("Undefined value for {}".format(name))
#             variable = default
#         return variable


class FunctionFileInput(AbstractWrapper):
    @classmethod
    def get_function_class(cls, parser = None):
        return parser.Function

    @classmethod
    def parse(cls, function, parser = None):
        source_lines, line_number = inspect.getsourcelines(function)
        source = textwrap.dedent(''.join(source_lines))
        # print source
        node = parser.driver.parse_string(source)
        assert node.type == symbols.file_input, "Unexpected file input type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2 and children[0].type == symbols.funcdef and children[1].type == tokens.ENDMARKER, \
            "Unexpected node children in:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        python_module = inspect.getmodule(function)
        if parser.country_package is not None:
            assert python_module.__file__.startswith(os.path.dirname(parser.country_package.__file__)), \
                "Requested class is defined outside country_package:\n{}".format(source)
        module = parser.python_module_by_name.get(python_module.__name__)
        if module is None:
            parser.python_module_by_name[python_module.__name__] = module = parser.Module(node, python = python_module,
                parser = parser)
        self = cls(parser = parser)
        function_class = self.get_function_class(parser = parser)
        try:
            return function_class.parse(children[0], container = module, parser = parser)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class Holder(AbstractWrapper):
    column = None

    def __init__(self, column = None, container = None, hint = None, node = None, parser = None):
        super(Holder, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert column is not None
        self.column = column


class If(AbstractWrapper):
    items = None  # List of (test, body) couples

    def __init__(self, container = None, hint = None, node = None, items = None, parser = None):
        super(If, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(items, list)
        self.items = items

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.if_stmt, "Unexpected if statement type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 4, "Unexpected length {} of children in if statement:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))

        items = []
        child_index = 0
        while child_index < len(children):
            reserved_word = children[child_index]
            assert reserved_word.type == tokens.NAME and reserved_word.value in ('if', 'elif', 'else'), \
                "Unexpected reserved word {}:\n{}\n\n{}".format(reserved_word.value, repr(node),
                    unicode(node).encode('utf-8'))
            child_index += 1

            if reserved_word.value == 'else':
                test = None
            else:
                test = parser.parse_value(children[child_index], container = container)
                child_index += 1

            colon = children[child_index]
            assert colon.type == tokens.COLON and colon.value == ':', "Unexpected colon {}:\n{}\n\n{}".format(
                colon.value, repr(node), unicode(node).encode('utf-8'))
            child_index += 1

            body = parser.parse_suite(children[child_index], container = container)
            child_index += 1

            items.append((test, body))

        return cls(container = container, items = items, node = node, parser = parser)


class Instant(AbstractWrapper):
    pass


class Key(AbstractWrapper):
    subject = None
    value = None  # Value of the key

    def __init__(self, container = None, hint = None, node = None, parser = None, subject = None, value = None):
        super(Key, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(subject, AbstractWrapper)
        self.subject = subject
        assert isinstance(value, AbstractWrapper)
        self.value = value

    def guess(self, expected):
        guessed = super(Key, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        uniform_dictionary = self.subject.guess(parser.UniformDictionary)
        if uniform_dictionary is not None:
            return uniform_dictionary.value.guess(expected)

        return None

    @classmethod
    def parse(cls, subject, node, container = None, parser = None):
        assert node.type == symbols.trailer, "Unexpected key type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in power key:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        left_bracket, key, right_bracket = children
        assert left_bracket.type == tokens.LSQB, "Unexpected left bracket type:\n{}\n\n{}".format(repr(left_bracket),
            unicode(left_bracket).encode('utf-8'))
        value = parser.parse_value(key, container = container)
        assert right_bracket.type == tokens.RSQB, "Unexpected right bracket type:\n{}\n\n{}".format(repr(right_bracket),
            unicode(right_bracket).encode('utf-8'))
        return cls(container = container, node = node, parser = parser, subject = subject, value = value)


class Lambda(AbstractWrapper):
    expression = None
    positional_parameters = None  # List of parameters names
    variable_by_name = None

    def __init__(self, container = None, expression = None, hint = None, node = None, parser = None,
            positional_parameters = None, variable_by_name = None):
        super(Lambda, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if expression is not None:
            assert isinstance(expression, AbstractWrapper)
            self.expression = expression
        if positional_parameters is None:
            positional_parameters = []
        else:
            assert isinstance(positional_parameters, list)
        self.positional_parameters = positional_parameters
        if variable_by_name is None:
            variable_by_name = collections.OrderedDict()
        else:
            assert isinstance(variable_by_name, collections.OrderedDict)
        self.variable_by_name = variable_by_name

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.lambdef, "Unexpected lambda definition type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 4, "Unexpected length {} of children in lambda definition:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        lambda_word, parameters, colon, expression = children

        self = cls(container = container, node = node, parser = parser)

        assert lambda_word.type == tokens.NAME and lambda_word.value == 'lambda'
        if parameters.type == tokens.NAME:
            parameter_name = parameters.value
            self.positional_parameters.append(parameter_name)
            self.variable_by_name[parameter_name] = parser.Variable(container = self, name = parameter_name,
                parser = parser)
        else:
            assert False, "Unexpected parameters in lambda definition:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
        assert colon.type == tokens.COLON and colon.value == ':'
        self.expression = parser.parse_value(expression, container = self)

        return self

    @property
    def containing_function(self):
        return self

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            container = self.container
            if container is not None:
                return container.get_variable(name, default = default, parser = parser)
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            variable = default
        return variable


class List(AbstractWrapper):
    value = None  # list value, as a list

    def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
        super(List, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(value, list), "Unexpected value for list: {} of type {}".format(value,
            type(value))
        self.value = value

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.listmaker, "Unexpected list type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        children = node.children
        child_index = 0
        items = []
        while child_index < len(children):
            child = children[child_index]
            items.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            comma = children[child_index]
            assert comma.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(comma),
                unicode(comma).encode('utf-8'))
            child_index += 1

        return cls(container = container, node = node, parser = parser, value = items)


class ListGenerator(AbstractWrapper):
    iterators = None
    value = None
    variable_by_name = None

    def __init__(self, container = None, hint = None, iterators = None, node = None, parser = None,
            value = None, variable_by_name = None):
        super(ListGenerator, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(iterators, list)
        self.iterators = iterators
        variables_value = []
        for iterator in iterators:
            guessed_iterator = iterator.guess(parser.UniformIterator)
            if guessed_iterator is None:
                if len(variable_by_name) == 1 and 'bar' in variable_by_name:
                    guessed_iterator = parser.UniformIterator(
                        container = container,
                        items = [
                            parser.TaxScale(
                                container = container,
                                parser = parser,
                                ),
                            ],
                        parser = parser,
                        )
                else:
                    assert False, "{} has no iterator".format(iterator)
            variables_value.extend(guessed_iterator.items)
        if value is not None:
            assert isinstance(value, AbstractWrapper)
            self.value = value

        assert isinstance(variable_by_name, collections.OrderedDict)
        for variable, value in itertools.izip(variable_by_name.itervalues(), variables_value):
            variable.value = value
        self.variable_by_name = variable_by_name
        container.variable_by_name.update(variable_by_name)

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.listmaker, "Unexpected list type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        children = node.children
        assert len(children) >= 2, "Unexpected length {} of children in for statement:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        iterators = []
        variable_by_name = collections.OrderedDict()
        for child_index, child in enumerate(children[1:], 1):
            if child.type == symbols.comp_for:
                for_node = child
                assert len(for_node.children) == 4, \
                    "Unexpected length {} of for children in list generator statement:\n{}\n\n{}".format(
                        len(for_node.children), repr(for_node), unicode(for_node).encode('utf-8'))
                for_word, variables, in_word, iterator = for_node.children
                assert for_word.type == tokens.NAME and for_word.value == 'for'
                if variables.type == symbols.exprlist:
                    variables = variables.children
                    variable_index = 0
                    while variable_index < len(variables):
                        variable = variables[variable_index]
                        assert variable.type == tokens.NAME
                        variable_name = variable.value
                        variable_by_name[variable_name] = parser.Variable(container = container, name = variable_name,
                            parser = parser)
                        variable_index += 1
                        if variable_index >= len(variables):
                            break
                        comma = variables[variable_index]
                        assert comma.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(comma),
                            unicode(comma).encode('utf-8'))
                        variable_index += 1
                elif variables.type == tokens.NAME:
                    variable_name = variables.value
                    variable_by_name[variable_name] = parser.Variable(container = container, name = variable_name,
                        parser = parser)
                else:
                    assert False, "Unexpected variables in for statement:\n{}\n\n{}".format(repr(node),
                        unicode(node).encode('utf-8'))
                assert in_word.type == tokens.NAME and in_word.value == 'in'
                iterator = parser.parse_value(iterator, container = container)
                iterators.append(iterator)
            else:
                assert False, "Unexpected item in list generator type:\n{}\n\n{}".format(repr(child),
                    unicode(child).encode('utf-8'))

        self = cls(container = container, iterators = iterators, parser = parser, variable_by_name = variable_by_name)
        self.value = parser.parse_value(children[0], container = container)

        return self


class Logger(AbstractWrapper):
    pass


# class Math(AbstractWrapper):
#     pass


class Module(AbstractWrapper):
    python = None
    variable_by_name = None

    def __init__(self, node, python = None, parser = None):
        super(Module, self).__init__(node = node, parser = parser)
        if python is not None:
            # Python module
            self.python = python
        self.variable_by_name = collections.OrderedDict(sorted(dict(
            and_ = parser.Variable(container = self, name = u'and_', parser = parser),
            around = parser.Variable(container = self, name = u'around', parser = parser),
            apply_along_axis = parser.Variable(container = self, name = u'apply_along_axis', parser = parser),
            array = parser.Variable(container = self, name = u'array', parser = parser),
            CAT = parser.Variable(container = self, name = u'CAT', parser = parser,
                value = parser.Enum(parser = parser)),
            ceil = parser.Variable(container = self, name = u'ceil', parser = parser),
            CHEF = parser.Variable(container = self, name = u'CHEF', parser = parser,
                value = parser.Number(parser = parser, value = 0)),
            # combine_tax_scales = parser.Variable(container = self, name = u'combine_tax_scales', parser = parser),
            CONJ = parser.Variable(container = self, name = u'CONJ', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            CREF = parser.Variable(container = self, name = u'CREF', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            date = parser.Variable(container = self, name = u'date', parser = parser),
            datetime64 = parser.Variable(container = self, name = u'datetime64', parser = parser),
            dict = parser.Variable(container = self, name = u'dict', parser = parser),
            # ENFS = parser.Variable(container = self, name = u'ENFS', parser = parser,
            #     value = parser.UniformList(parser = parser, value = parser.Number(parser = parser, value = x))),
            ENFS = parser.Variable(container = self, name = u'ENFS', parser = parser),
            floor = parser.Variable(container = self, name = u'floor', parser = parser),
            fromiter = parser.Variable(container = self, name = u'fromiter', parser = parser),
            fsolve = parser.Variable(container = self, name = u'fsolve', parser = parser),
            hasattr = parser.Variable(container = self, name = u'hasattr', parser = parser),
            holidays = parser.Variable(container = self, name = u'holidays', parser = parser),
            int16 = parser.Variable(container = self, name = u'int16', parser = parser,
                value = parser.Type(parser = parser, value = np.int16)),
            int32 = parser.Variable(container = self, name = u'int32', parser = parser,
                value = parser.Type(parser = parser, value = np.int32)),
            izip = parser.Variable(container = self, name = u'izip', parser = parser),
            law = parser.Variable(container = self, name = u'law', parser = parser,
                value = parser.CompactNode(parser = parser, value = parser.tax_benefit_system.get_legislation())),
            len = parser.Variable(container = self, name = u'len', parser = parser),
            log = parser.Variable(container = self, name = u'log', parser = parser,
                value = parser.Logger(parser = parser)),
            MarginalRateTaxScale = parser.Variable(container = self, name = u'MarginalRateTaxScale', parser = parser),
            max = parser.Variable(container = self, name = u'max', parser = parser),
            max_ = parser.Variable(container = self, name = u'max_', parser = parser),
            math = parser.Variable(container = self, name = u'math', parser = parser),
            min_ = parser.Variable(container = self, name = u'min_', parser = parser),
            not_ = parser.Variable(container = self, name = u'not_', parser = parser),
            ones = parser.Variable(container = self, name = u'ones', parser = parser),
            or_ = parser.Variable(container = self, name = u'or_', parser = parser),
            original_busday_count = parser.Variable(container = self, name = u'original_busday_count', parser = parser),
            PAC1 = parser.Variable(container = self, name = u'PAC1', parser = parser,
                value = parser.Number(parser = parser, value = 2)),
            PAC2 = parser.Variable(container = self, name = u'PAC2', parser = parser,
                value = parser.Number(parser = parser, value = 3)),
            PAC3 = parser.Variable(container = self, name = u'PAC3', parser = parser,
                value = parser.Number(parser = parser, value = 4)),
            PART = parser.Variable(container = self, name = u'PART', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            partial = parser.Variable(container = self, name = u'partial', parser = parser),
            PREF = parser.Variable(container = self, name = u'PREF', parser = parser,
                value = parser.Number(parser = parser, value = 0)),
            round = parser.Variable(container = self, name = u'round', parser = parser),
            round_ = parser.Variable(container = self, name = u'round_', parser = parser),
            # scale_tax_scales = parser.Variable(container = self, name = u'scale_tax_scales', parser = parser),
            SCOLARITE_COLLEGE = parser.Variable(container = self, name = u'SCOLARITE_COLLEGE', parser = parser,
                value = parser.Number(parser = parser, value = 1)),
            sorted = parser.Variable(container = self, name = u'sorted', parser = parser),
            startswith = parser.Variable(container = self, name = u'startswith', parser = parser),
            TAUX_DE_PRIME = parser.Variable(container = self, name = u'TAUX_DE_PRIME', parser = parser,
                value = parser.Number(parser = parser, value = 1 / 4)),
            # TaxScalesTree = parser.Variable(container = self, name = u'TaxScalesTree', parser = parser),
            timedelta64 = parser.Variable(container = self, name = u'timedelta64', parser = parser),
            ValueError = parser.Variable(container = self, name = u'ValueError', parser = parser),
            VOUS = parser.Variable(container = self, name = u'VOUS', parser = parser,
                value = parser.Number(parser = parser, value = 0)),
            where = parser.Variable(container = self, name = u'where', parser = parser),
            xor_ = parser.Variable(container = self, name = u'xor_', parser = parser),
            zeros = parser.Variable(container = self, name = u'zeros', parser = parser),
            zone_apl_by_depcom = parser.Variable(container = self, name = u'zone_apl_by_depcom', parser = parser),
            ).iteritems()))

    @property
    def containing_module(self):
        return self

    def get_variable(self, name, default = UnboundLocalError, parser = None):
        variable = self.variable_by_name.get(name, None)
        if variable is None:
            value = getattr(self.python, name, UnboundLocalError)
            if value is UnboundLocalError:
                if default is UnboundLocalError:
                    raise KeyError("Undefined value for {}".format(name))
                return default
            if not inspect.isfunction(value):
                # TODO?
                if default is UnboundLocalError:
                    raise KeyError("Undefined value for {}".format(name))
                return default
            # Declare function before parsing if to avoid infinite parsing when it is recursive.
            self.variable_by_name[name] = variable = parser.Variable(container = self, name = name,
                parser = parser)
            function = parser.FunctionFileInput.parse(value, parser = parser)
            assert isinstance(function, parser.Function), function
            variable.value = function
        return variable


class NoneWrapper(AbstractWrapper):
    pass


class NotTest(AbstractWrapper):
    value = None

    def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
        super(NotTest, self).__init__(container = container, hint = hint, node = node,
            parser = parser)
        assert isinstance(value, AbstractWrapper)
        self.value = value

    def guess(self, expected):
        guessed = super(NotTest, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            array = self.value.guess(parser.Array)
            if array is not None:
                return parser.Array(
                    cell = parser.Boolean(
                        parser = parser,
                        ),
                    entity_class = array.entity_class,
                    parser = parser,
                    )
        elif issubclass(parser.Boolean, expected):
            return parser.Boolean(
                parser = parser,
                )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.not_test, "Unexpected not test type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        children = node.children
        assert len(children) == 2, len(children)
        assert children[0].type == tokens.NAME and children[0].value == 'not'
        value = parser.parse_value(children[1], container = container)

        return cls(container = container, node = node, parser = parser, value = value)


class Number(AbstractWrapper):
    type = None
    value = None

    def __init__(self, container = None, node = None, parser = None, type = None, value = None):
        super(Number, self).__init__(container = container, node = node, parser = parser)
        if type is not None:
            self.type = type
        if value is not None:
            assert isinstance(value, (bool, int, float)), "Unexpected value for number: {} of type {}".format(value,
                type(value))
            self.value = value

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == tokens.NUMBER, "Unexpected number type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        try:
            value = int(node.value)
        except ValueError:
            value = float(node.value)
        return cls(container = container, node = node, parser = parser, value = value)


class ParentheticalExpression(AbstractWrapper):
    value = None

    def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
        super(ParentheticalExpression, self).__init__(container = container, hint = hint, node = node,
            parser = parser)
        assert isinstance(value, AbstractWrapper)
        self.value = value

    def guess(self, expected):
        guessed = super(ParentheticalExpression, self).guess(expected)
        if guessed is not None:
            return guessed

        if self.value is not None:
            guessed = self.value.guess(expected)
            if guessed is not None:
                return guessed

        return None


class Period(AbstractWrapper):
    unit = None

    def __init__(self, container = None, hint = None, node = None, parser = None, unit = None):
        super(Period, self).__init__(container = container, hint = hint, node = node, parser = parser)
        if unit is not None:
            assert unit in (u'day', u'month', u'year'), unit
            self.unit = unit


class Raise(AbstractWrapper):
    exception = None

    def __init__(self, container = None, exception = None, hint = None, node = None, parser = None):
        super(Raise, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(exception, AbstractWrapper)
        self.exception = exception

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.raise_stmt, "Unexpected raise type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, "Unexpected length {} of children in raise:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        raise_word = children[0]
        assert raise_word.type == tokens.NAME and raise_word.value == 'raise'
        exception = parser.parse_value(children[1], container = container)

        return cls(container = container, exception = exception, node = node, parser = parser)


class Return(AbstractWrapper):
    value = None

    def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
        super(Return, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(value, AbstractWrapper)
        self.value = value

    def guess(self, expected):
        guessed = super(Return, self).guess(expected)
        if guessed is not None:
            return guessed

        if self.value is not None:
            guessed = self.value.guess(expected)
            if guessed is not None:
                return guessed

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.return_stmt, "Unexpected return type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, len(children)
        assert children[0].type == tokens.NAME and children[0].value == 'return'
        value = parser.parse_value(children[1], container = container)

        self = cls(container = container, node = node, parser = parser, value = value)

        containing_function = self.containing_function
        containing_function.returns.append(self)

        return self


class Role(Number):
    pass


class Simulation(AbstractWrapper):
    pass


class StemNode(AbstractWrapper):
    """An indifferentiated CompactNode or Parameter or TaxScale"""
    is_reference = True
    parent = None  # Parent CompactNode wrapper

    def __init__(self, is_reference = False, parent = None, parser = None):
        super(StemNode, self).__init__(parser = parser)
        if not is_reference:
            self.is_reference = False
        if parent is not None:
            assert isinstance(parent, (CompactNode, StemNode))
            self.parent = parent

    # def iter_names(self):
    #     parent = self.parent
    #     if parent is not None:
    #         for ancestor_name in parent.iter_names():
    #             yield ancestor_name
    #     name = self.name
    #     if name is not None:
    #         yield name

    # @property
    # def path(self):
    #     return '.'.join(self.iter_names())


class String(AbstractWrapper):
    value = None  # String value, as a string

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(String, self).__init__(container = container, node = node, parser = parser)
        if value is not None:
            assert isinstance(value, unicode), "Unexpected value for string: {} of type {}".format(value,
                type(value))
            self.value = value

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == tokens.STRING, "Unexpected string type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        value = node.value
        if isinstance(value, str):
            value = value.decode('utf-8')
        if value.startswith(u'u'):
            value = value[1:]
        for delimiter in (u'"""', u"'''", u'"', u"'"):
            if value.startswith(delimiter) and value.endswith(delimiter):
                value = value[len(delimiter):-len(delimiter)]
                break
        else:
            assert False, "Unknow delimiters for: {}".format(value)
        return cls(container = container, node = node, parser = parser, value = value)


# class Structure(AbstractWrapper):
#     value = None  # A list or a dictionary
#
#     def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
#         super(Structure, self).__init__(container = container, hint = hint, node = node, parser = parser)
#         assert isinstance(value, (dict, list, tuple)), "Unexpected value for structure: {} of type {}".format(value,
#             type(value))
#         self.value = value


class TaxScale(AbstractWrapper):
    pass


# class TaxScalesTree(AbstractWrapper):
#     pass


class Term(AbstractWrapper):
    items = None

    def __init__(self, container = None, hint = None, items = None, node = None, parser = None):
        super(Term, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(items, list)
        assert len(items) >= 3 and (len(items) & 1)
        self.items = items

    def guess(self, expected):
        guessed = super(Term, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            for index, item in enumerate(self.items):
                if index & 1:
                    continue
                array = item.guess(parser.Array)
                if array is not None:
                    return parser.Array(
                        cell = parser.Number(
                            parser = parser,
                            ),
                        entity_class = array.entity_class,
                        parser = parser,
                        )

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.term, "Unexpected term type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 3 and (len(children) & 1), \
            "Unexpected length {} of children in term:\n{}\n\n{}".format(len(children), repr(node),
            unicode(node).encode('utf-8'))

        child_index = 0
        items = []
        while child_index < len(children):
            child = children[child_index]
            items.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            operator = children[child_index]
            assert operator.type in (
                tokens.DOUBLESLASH,
                tokens.PERCENT,
                tokens.SLASH,
                tokens.STAR,
                ), "Unexpected operator type:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            items.append(operator.value)
            child_index += 1

        return cls(container = container, items = items, node = node, parser = parser)


class Test(AbstractWrapper):
    false_value = None
    test = None
    true_value = None

    def __init__(self, container = None, false_value = None, hint = None, node = None, parser = None, test = None,
            true_value = None):
        super(Test, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(false_value, AbstractWrapper)
        self.false_value = false_value
        assert isinstance(test, AbstractWrapper)
        self.test = test
        assert isinstance(true_value, AbstractWrapper)
        self.true_value = true_value

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.test, "Unexpected test statement type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 5, "Unexpected length {} of children in test statement:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        true_value, if_word, test, else_word, false_value = children
        true_value = parser.parse_value(true_value, container = container)
        assert if_word.type == tokens.NAME and if_word.value == 'if'
        test = parser.parse_value(test, container = container)
        assert else_word.type == tokens.NAME and else_word.value == 'else'
        false_value = parser.parse_value(false_value, container = container)

        return cls(container = container, false_value = false_value, node = node, parser = parser, test= test,
            true_value = true_value)


class Tuple(AbstractWrapper):
    value = None  # Tuple value, as a tuple

    def __init__(self, container = None, hint = None, node = None, parser = None, value = None):
        super(Tuple, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(value, tuple), "Unexpected value for tuple: {} of type {}".format(value,
            type(value))
        self.value = value

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.testlist, "Unexpected tuple type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        children = node.children
        child_index = 0
        items = []
        while child_index < len(children):
            child = children[child_index]
            items.append(parser.parse_value(child, container = container))
            child_index += 1
            if child_index >= len(children):
                break
            comma = children[child_index]
            assert comma.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(comma),
                unicode(comma).encode('utf-8'))
            child_index += 1

        return cls(container = container, node = node, parser = parser, value = tuple(items))


class TupleGenerator(AbstractWrapper):
    # TODO: Used only by zone_apl

    @classmethod
    def parse(cls, node, container = None, parser = None):
        assert node.type == symbols.testlist_gexp, "Unexpected tuple type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        # TODO: Used only by zone_apl

        return cls(container = container, node = node, parser = parser)


class Type(AbstractWrapper):
    value = None

    def __init__(self, container = None, node = None, parser = None, value = None):
        super(Type, self).__init__(container = container, node = node, parser = parser)
        if value is not None:
            self.value = value


class UniformDictionary(AbstractWrapper):
    key = None
    value = None

    def __init__(self, container = None, key = None, node = None, parser = None, value = None):
        super(UniformDictionary, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(key, AbstractWrapper)
        self.key = key
        assert isinstance(value, AbstractWrapper)
        self.value = value

    def guess(self, expected):
        guessed = super(UniformDictionary, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.UniformIterator, expected):
            return parser.UniformIterator(
                items = [self.key],
                parser = parser,
                )

        return None


class UniformIterator(AbstractWrapper):
    items = None  # A list of values (one for iterkeys & itervalues, 2 for iteritems) that iterate.

    def __init__(self, container = None, items = None, node = None, parser = None):
        super(UniformIterator, self).__init__(container = container, node = node, parser = parser)
        assert isinstance(items, list)
        self.items = items


# class UniformList(AbstractWrapper):
#     item = None

#     def __init__(self, node, item = None, parser = None):
#         super(UniformList, self).__init__(node, parser = parser)
#         if item is not None:
#             self.item = item


class Variable(AbstractWrapper):
    name = None
    value = None  # A value wrapper

    def __init__(self, container = None, hint = None, name = None, node = None, parser = None, value = None):
        super(Variable, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(name, basestring)
        self.name = name
        if value is not None:
            assert isinstance(value, AbstractWrapper)
            self.value = value

    def __repr__(self):
        return u'<Variable {}>'.format(self.name)

    def guess(self, expected):
        guessed = super(Variable, self).guess(expected)
        if guessed is not None:
            return guessed

        if self.value is not None:
            guessed = self.value.guess(expected)
            if guessed is not None:
                return guessed

        return None

    @classmethod
    def parse(cls, node, container = None, parser = None, value = None):
        assert node.type == tokens.NAME, "Unexpected variable type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        return cls(container = container, name = node.value, node = node, parser = parser, value = value)


class XorExpression(AbstractWrapper):
    operands = None
    operator = None

    def __init__(self, container = None, hint = None, node = None, operands = None, operator = None, parser = None):
        super(XorExpression, self).__init__(container = container, hint = hint, node = node, parser = parser)
        assert isinstance(operands, list)
        self.operands = operands
        assert isinstance(operator, basestring)
        self.operator = operator

    def guess(self, expected):
        guessed = super(XorExpression, self).guess(expected)
        if guessed is not None:
            return guessed

        parser = self.parser
        if issubclass(parser.Array, expected):
            for operand in self.operands:
                array = operand.guess(parser.Array)
                if array is not None:
                    return parser.Array(
                        cell = parser.Boolean(
                            parser = parser,
                            ),
                        entity_class = array.entity_class,
                        parser = parser,
                        )

        return None


# Level-2 Wrappers


class Boolean(Number):
    pass


# Formula-specific classes


class Formula(AbstractWrapper):
    column = None
    formula_class = None

    def __init__(self, container = None, formula_class = None, hint = None, node = None, parser = None):
        super(Formula, self).__init__(container = container, hint = hint, node = node, parser = parser)
        self.column = parser.column
        assert self.column is not None
        assert isinstance(formula_class, parser.FormulaClass)
        self.formula_class = formula_class


class FormulaClass(Class):
    @classmethod
    def get_function_class(cls, parser = None):
        return parser.FormulaFunction


class FormulaClassFileInput(ClassFileInput):
    # Caution: This is not the whole module, but only a dummy "module" containing only the formula.
    @classmethod
    def get_class_class(cls, parser = None):
        return parser.FormulaClass


class FormulaFunction(Function):
    @classmethod
    def parse(cls, node, container = None, parser = None):
        try:
            children = node.children
            assert len(children) == 5
            assert children[0].type == tokens.NAME and children[0].value == 'def'
            assert children[1].type == tokens.NAME  # Function name
            name = children[1].value

            self = cls(container = container, name = name, node = node, parser = parser)
            self.parse_parameters()
            self.parse_body()
            return self
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise

    def parse_parameters(self):
        super(FormulaFunction, self).parse_parameters()
        parser = self.parser
        assert self.positional_parameters == ['self', 'simulation', 'period'], self.positional_parameters
        assert not self.named_parameters, self.named_arguments
        formula_variable = self.variable_by_name['self']
        assert formula_variable.value is None, formula_variable.value
        formula_variable.value = parser.Formula(container = self.container.container, formula_class = self.container,
            parser = self.parser)
        simulation_variable = self.variable_by_name['simulation']
        assert simulation_variable.value is None, simulation_variable.value
        simulation_variable.value = parser.Simulation(parser = self.parser)
        period_variable = self.variable_by_name['period']
        assert period_variable.value is None, period_variable.value
        period_variable.value = parser.Period(parser = self.parser, unit = u'day')


# class FormulaFunctionFileInput(FunctionFileInput):
#     # Caution: This is not the whole module, but only a dummy "module" containing only the formula.
#     @classmethod
#     def get_function_class(cls, parser = None):
#         return parser.FormulaFunction


# Default Parser


class Parser(conv.State):
    AndExpression = AndExpression
    AndTest = AndTest
    Array = Array
    # ArrayLength = ArrayLength
    ArithmeticExpression = ArithmeticExpression
    Assert = Assert
    Assignment = Assignment
    Attribute = Attribute
    Boolean = Boolean
    Call = Call
    Class = Class
    ClassFileInput = ClassFileInput
    column = None  # Formula column
    CompactNode = CompactNode
    Comparison = Comparison
    Continue = Continue
    country_package = None
    Date = Date
    DateTime64 = DateTime64
    DatedHolder = DatedHolder
    Decorator = Decorator
    Dictionary = Dictionary
    driver = None
    Entity = Entity
    # EntityToEntity = EntityToEntity
    Enum = Enum
    Expression = Expression
    Factor = Factor
    For = For
    Formula = Formula
    FormulaClass = FormulaClass
    FormulaClassFileInput = FormulaClassFileInput
    FormulaFunction = FormulaFunction
    # FormulaFunctionFileInput = FormulaFunctionFileInput
    Function = Function
    # FunctionCall = FunctionCall
    FunctionFileInput = FunctionFileInput
    Holder = Holder
    If = If
    Instant = Instant
    Key = Key
    Lambda = Lambda
    List = List
    ListGenerator = ListGenerator
    Logger = Logger
    # Math = Math
    Module = Module
    NoneWrapper = NoneWrapper
    NotTest = NotTest
    Number = Number
    ParentheticalExpression = ParentheticalExpression
    Period = Period
    python_module_by_name = None
    Raise = Raise
    Return = Return
    Role = Role
    Simulation = Simulation
    StemNode = StemNode
    String = String
    # Structure = Structure
    tax_benefit_system = None
    TaxScale = TaxScale
    # TaxScalesTree = TaxScalesTree
    Term = Term
    Test = Test
    Tuple = Tuple
    TupleGenerator = TupleGenerator
    Type = Type
    UniformDictionary = UniformDictionary
    UniformIterator = UniformIterator
    # UniformList = UniformList
    Variable = Variable
    XorExpression = XorExpression

    def __init__(self, country_package = None, driver = None, tax_benefit_system = None):
        if country_package is not None:
            self.country_package = country_package
        self.driver = driver
        self.python_module_by_name = {}
        self.tax_benefit_system = tax_benefit_system

    @property
    def entity_class(self):
        if self.column is None:
            return None
        return self.tax_benefit_system.entity_class_by_key_plural[self.column.entity_key_plural]

    def get_cell_wrapper(self, container = None, type = None):
        wrapper_class = {
            None: self.Number,
            np.bool: self.Boolean,
            np.float32: self.Number,
            np.int16: self.Number,
            np.int32: self.Number,
            'datetime64[D]': self.DateTime64,
            }[type]
        if wrapper_class is self.Number:
            return wrapper_class(container = container, parser = self, type = type)
        return wrapper_class(container = container, parser = self)

    def parse_power(self, node, container = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))

        assert node.type == symbols.power, "Unexpected power type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 2, "Unexpected length {} of children in power:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        subject = self.parse_value(children[0], container = container)
        for trailer in itertools.islice(children, 1, None):
            assert trailer.type == symbols.trailer, "Unexpected trailer type:\n{}\n\n{}".format(repr(trailer),
                unicode(trailer).encode('utf-8'))
            trailer_children = trailer.children
            trailer_first_child = trailer_children[0]
            if trailer_first_child.type == tokens.DOT:
                subject = self.Attribute.parse(subject, trailer, container = container, parser = self)
            elif trailer_first_child.type == tokens.LPAR:
                if len(trailer_children) == 2:
                    left_parenthesis, right_parenthesis = trailer_children
                    arguments = None
                else:
                    assert len(trailer_children) == 3, \
                        "Unexpected length {} of children in power call:\n{}\n\n{}".format(len(trailer_children),
                        repr(trailer), unicode(trailer).encode('utf-8'))
                    left_parenthesis, arguments, right_parenthesis = trailer_children
                assert left_parenthesis.type == tokens.LPAR, "Unexpected left parenthesis type:\n{}\n\n{}".format(
                    repr(left_parenthesis), unicode(left_parenthesis).encode('utf-8'))
                assert right_parenthesis.type == tokens.RPAR, "Unexpected right parenthesis type:\n{}\n\n{}".format(
                    repr(right_parenthesis), unicode(right_parenthesis).encode('utf-8'))
                subject = self.Call.parse(subject, arguments, container = container, parser = self)
            else:
                subject = self.Key.parse(subject, trailer, container = container, parser = self)
        return subject

    def parse_suite(self, node, container = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))

        if node.type == symbols.suite:
            children = node.children
        else:
            children = [node]  # Suite is only a single statement.
        body = []
        for child in children:
            if child.type == symbols.for_stmt:
                for_wrapper = self.For.parse(child, container = container, parser = self)
                body.append(for_wrapper)
            elif child.type == symbols.funcdef:
                function = container.get_function_class(parser = self).parse(child, container = container,
                    parser = self)
                body.append(function)
                container.variable_by_name[function.name] = self.Variable(container = container, name = function.name,
                    parser = self, value = function)
            elif child.type == symbols.if_stmt:
                if_wrapper = self.If.parse(child, container = container, parser = self)
                body.append(if_wrapper)
            elif child.type == symbols.simple_stmt:
                assert len(child.children) == 2, \
                    "Unexpected length {} for simple statement in function definition:\n{}\n\n{}".format(
                        len(child.children), repr(child), unicode(child).encode('utf-8'))
                statement = child.children[0]
                if statement.type == symbols.assert_stmt:
                    assert_statement = self.Assert.parse(statement, container = container, parser = self)
                    body.append(assert_statement)
                elif statement.type == symbols.expr_stmt:
                    assignment = self.Assignment.parse(statement, container = container, parser = self)
                    body.append(assignment)
                elif statement.type == symbols.global_stmt:
                    # TODO: Used only by zone_apl.
                    pass
                elif statement.type == symbols.power:
                    power = self.parse_power(statement, container = container)
                    body.append(power)
                elif statement.type == symbols.raise_stmt:
                    raise_statement = self.Raise.parse(statement, container = container, parser = self)
                    body.append(raise_statement)
                elif statement.type == symbols.return_stmt:
                    return_wrapper = self.Return.parse(statement, container = container, parser = self)
                    body.append(return_wrapper)
                elif statement.type == tokens.NAME and statement.value == 'continue':
                    continue_statement = self.Continue(container = container, node = statement, parser = self)
                    body.append(continue_statement)
                elif statement.type == tokens.STRING:
                    # Docstring
                    string = self.String.parse(statement, container = container, parser = self)
                    body.append(string)
                else:
                    assert False, "Unexpected simple statement in suite:\n{}\n\n{}".format(repr(child),
                        unicode(child).encode('utf-8'))
                assert child.children[1].type == tokens.NEWLINE and child.children[1].value == '\n'
            elif child.type == symbols.with_stmt:
                # TODO: Used only by zone_apl.
                pass
            elif child.type in (tokens.DEDENT, tokens.INDENT, tokens.NEWLINE):
                pass
            else:
                assert False, "Unexpected statement in suite:\n{}\n\n{}".format(repr(child),
                    unicode(child).encode('utf-8'))
        return body

    def parse_value(self, node, container = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))

        if node.type == symbols.and_expr:
            return self.AndExpression.parse(node, container = container, parser = self)

        if node.type == symbols.and_test:
            return self.AndTest.parse(node, container = container, parser = self)

        if node.type == symbols.arith_expr:
            return self.ArithmeticExpression.parse(node, container = container, parser = self)

        if node.type == symbols.atom:
            assert node.type == symbols.atom, "Unexpected atom type:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            children = node.children
            assert len(children) == 3, "Unexpected length {} of children in atom:\n{}\n\n{}".format(len(children),
                repr(node), unicode(node).encode('utf-8'))
            left_parenthesis, value, right_parenthesis = children
            assert left_parenthesis.type in (tokens.LBRACE, tokens.LPAR, tokens.LSQB), \
                "Unexpected left parenthesis {} in atom:\n{}\n\n{}".format(left_parenthesis.value, repr(node),
                    unicode(node).encode('utf-8'))
            assert right_parenthesis.type in (tokens.RBRACE, tokens.RPAR, tokens.RSQB), \
                "Unexpected right parenthesis {} in atom:\n{}\n\n{}".format(right_parenthesis.value, repr(node),
                    unicode(node).encode('utf-8'))
            if left_parenthesis.type == tokens.LPAR:
                value = self.parse_value(value, container = container)
                return self.ParentheticalExpression(container = container, node = node, parser = self, value = value)
            if value.type == symbols.dictsetmaker:
                dict_children = value.children
                child_index = 0
                while child_index < len(dict_children):
                    item_key = self.parse_value(dict_children[child_index], container = container)
                    assert dict_children[child_index + 1].type == tokens.COLON, \
                        "Unexpected colon {} in atom:\n{}\n\n{}".format(dict_children[child_index + 1], repr(value),
                            unicode(value).encode('utf-8'))
                    item_value = self.parse_value(dict_children[child_index + 2], container = container)
                    child_index += 3
                    if (child_index < len(dict_children)) and dict_children[child_index].type == tokens.COMMA:
                        child_index += 1
                    else:
                        assert child_index == len(dict_children), \
                            "Missing comma after dictionary item {} in atom:\n{}\n\n{}".format(child_index, repr(value),
                                unicode(value).encode('utf-8'))
                # TODO: Currently it is assumed that dictionary is uniform.
                return self.UniformDictionary(
                    container = container,
                    key = item_key,
                    parser = self,
                    value = item_value,
                    )
            if value.type == symbols.listmaker:
                if any(child.type == symbols.comp_for for child in value.children):
                    return self.ListGenerator.parse(value, container = container, parser = self)
                return self.List.parse(value, container = container, parser = self)
            singleton = self.parse_value(value, container = container)
            return self.List(container = container, node = value, parser = self, value = [singleton])

        if node.type == symbols.comparison:
            return self.Comparison.parse(node, container = container, parser = self)

        if node.type == symbols.expr:
            return self.Expression.parse(node, container = container, parser = self)

        if node.type == symbols.factor:
            return self.Factor.parse(node, container = container, parser = self)

        if node.type == symbols.lambdef:
            return self.Lambda.parse(node, container = container, parser = self)

        if node.type == symbols.not_test:
            return self.NotTest.parse(node, container = container, parser = self)

        if node.type == symbols.power:
            return self.parse_power(node, container = container)

        if node.type == symbols.term:
            return self.Term.parse(node, container = container, parser = self)

        if node.type == symbols.test:
            return self.Test.parse(node, container = container, parser = self)

        if node.type == symbols.testlist:
            return self.Tuple.parse(node, container = container, parser = self)

        if node.type == symbols.testlist_gexp:
            return self.TupleGenerator.parse(node, container = container, parser = self)

        if node.type == tokens.NAME:
            name = node.value
            if name == u'False':
                return self.Boolean(container = container, parser = self, value = False)
            elif name == u'None':
                return self.NoneWrapper(container = container, parser = self)
            elif name == u'True':
                return self.Boolean(container = container, parser = self, value = True)
            variable = container.get_variable(name, default = None, parser = self)
            assert variable is not None, "Undefined variable: {}".format(name)
            return variable

        if node.type == tokens.NUMBER:
            return self.Number.parse(node, container = container, parser = self)

        if node.type == tokens.STRING:
            return self.String.parse(node, container = container, parser = self)

        assert False, "Unexpected value:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))

    @property
    def person_class(self):
        for entity_class in self.tax_benefit_system.entity_class_by_key_plural.itervalues():
            if entity_class.is_persons_entity:
                return entity_class
        return None
