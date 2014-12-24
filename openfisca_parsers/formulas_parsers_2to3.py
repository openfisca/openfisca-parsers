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


"""Parsers for formula-specific Abstract Syntax Trees"""


from __future__ import division

import collections
import inspect
import itertools
import lib2to3.pgen2.token
import lib2to3.pygram
import lib2to3.pytree
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


class AbstractWrapper(object):
    container = None  # The wrapper directly containing this wrapper
    node = None  # The lib2to3 node

    def __init__(self, node, container = None, state = None):
        if node is not None:
            assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            self.node = node
        if container is not None:
            assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
                repr(node), unicode(node).encode('utf-8'))
            self.container = container
        assert isinstance(state, State), "Invalid state {} for node:\n{}\n\n{}".format(state, repr(node),
            unicode(node).encode('utf-8'))

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


class Array(AbstractWrapper):
    column = None
    data_type = None
    entity_key_plural = None
    is_argument = False
    operation = None

    def __init__(self, node, column = None, data_type = None, entity_key_plural = None, is_argument = False,
            operation = None, state = None):
        super(Array, self).__init__(node, state = state)
        if column is not None:
            self.column = column
            assert column.dtype == data_type, str((column.dtype, data_type))
            assert column.entity_key_plural == entity_key_plural
        if data_type is not None:
            self.data_type = data_type
        if entity_key_plural is not None:
            self.entity_key_plural = entity_key_plural
        if is_argument:
            self.is_argument = True
        if operation is not None:
            self.operation = operation


class ArrayLength(AbstractWrapper):
    array = None

    def __init__(self, node, array = None, state = None):
        super(ArrayLength, self).__init__(node, state = state)
        if array is not None:
            self.array = array


class Assignment(AbstractWrapper):
    left = None  # Variable name
    operator = None
    right = None

    def __init__(self, node, container = None, state = None):
        super(Assignment, self).__init__(node, container = container, state = state)

        assert node.type == symbols.expr_stmt, "Expected a node of type {}. Got:\n{}\n\n{}".format(
            type_symbol(symbols.expr_stmt), repr(node), unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in assignment:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        left, operator, right = children
        assert operator.type in (tokens.EQUAL, tokens.MINEQUAL, tokens.PLUSEQUAL, tokens.STAREQUAL), \
            "Unexpected assignment operator:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        self.operator = operator.value
        if left.type == symbols.testlist_star_expr:
            assert right.type == symbols.testlist_star_expr
            left_children = left.children
            right_children = right.children
            assert len(left_children) == len(right_children), \
                "Unexpected length difference for left & right in assignment:\n{}\n\n{}".format(repr(node),
                    unicode(node).encode('utf-8'))
            child_index = 0
            self.left = left_wrappers = []
            self.right = right_wrappers = []
            while child_index < len(left_children):
                left_child = left_children[child_index]
                assert left_child.type == tokens.NAME
                left_wrapper = state.Variable(left_child, container = container, state = state)
                left_wrappers.append(left_wrapper)
                right_child = right_children[child_index]
                right_wrapper = state.parse_value(right_child, container = container, state = state)
                right_wrappers.append(right_wrapper)
                container.variable_value_by_name[left_wrapper.name] = right_wrapper

                child_index += 1
                if child_index >= len(left_children):
                    break
                assert left_children[child_index].type == tokens.COMMA
                child_index += 1
        elif left.type == symbols.power:
            self.left = state.parse_power(left, container = container, state = state)
            self.right = state.parse_value(right, container = container, state = state)
        else:
            assert left.type == tokens.NAME, \
                "Unexpected assignment left operand:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            self.left = state.Variable(left, container = container, state = state)
            self.right = state.parse_value(right, container = container, state = state)
            container.variable_value_by_name[self.left.name] = self.right


class Attribute(AbstractWrapper):
    name = None
    subject = None

    def __init__(self, subject, node, container = None, state = None):
        super(Attribute, self).__init__(node, container = container, state = state)

        assert isinstance(subject, AbstractWrapper)
        self.subject = subject
        assert node.type == symbols.trailer, "Unexpected attribute type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2, "Unexpected length {} of children in power attribute:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        dot, attribute = children
        assert dot.type == tokens.DOT, "Unexpected dot type:\n{}\n\n{}".format(repr(dot), unicode(dot).encode('utf-8'))
        assert attribute.type == tokens.NAME, "Unexpected attribute type:\n{}\n\n{}".format(repr(attribute),
            unicode(attribute).encode('utf-8'))
        self.name = attribute.value


class BinaryOperation(AbstractWrapper):
    left = None
    operator = None  # AST operator
    right = None

    def __init__(self, node, left = None, operator = None, right = None, state = None):
        super(BinaryOperation, self).__init__(node, state = state)
        if left is not None:
            self.left = left
        if operator is not None:
            self.operator = operator
        if right is not None:
            self.right = right


class Call(AbstractWrapper):
    named_arguments = None
    positional_arguments = None
    subject = None

    def __init__(self, subject, node, container = None, state = None):
        super(Call, self).__init__(node, container = container, state = state)

        assert isinstance(subject, AbstractWrapper)
        self.subject = subject

        if node is None:
            children = []
        elif node.type == symbols.arglist:
            children = node.children
        else:
            children = [node]
        self.named_arguments = named_arguments = collections.OrderedDict()
        self.positional_arguments = positional_arguments = []
        child_index = 0
        while child_index < len(children):
            argument = children[child_index]
            if argument.type == symbols.argument:
                argument_children = argument.children
                assert len(argument_children) == 3, "Unexpected length {} of children in argument:\n{}\n\n{}".format(
                    len(argument_children), repr(argument), unicode(argument).encode('utf-8'))
                argument_name, equal, argument_value = argument_children
                assert argument_name.type == tokens.NAME, "Unexpected name type:\n{}\n\n{}".format(repr(argument_name),
                    unicode(argument_name).encode('utf-8'))
                assert equal.type == tokens.EQUAL, "Unexpected equal type:\n{}\n\n{}".format(repr(equal),
                    unicode(equal).encode('utf-8'))
                named_arguments[argument_name.value] = state.parse_value(argument_value, container = container,
                    state = state)
            else:
                positional_arguments.append(state.parse_value(argument, container = container, state = state))
            child_index += 1
            if child_index >= len(children):
                break
            child = children[child_index]
            assert child.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(child),
                unicode(child).encode('utf-8'))
            child_index += 1


class Class(AbstractWrapper):
    base_class_name = None
    name = None
    variable_value_by_name = None

    def __init__(self, node, container = None, state = None):
        super(Class, self).__init__(node, container = container, state = state)
        self.variable_value_by_name = collections.OrderedDict()

        try:
            children = node.children
            assert len(children) == 7, len(children)
            assert children[0].type == tokens.NAME and children[0].value == 'class'
            assert children[1].type == tokens.NAME
            self.name = children[1].value
            assert children[2].type == tokens.LPAR and children[2].value == '('
            assert children[3].type == tokens.NAME
            self.base_class_name = children[3].value
            assert children[4].type == tokens.RPAR and children[4].value == ')'
            assert children[5].type == tokens.COLON and children[5].value == ':'
            suite = children[6]
            assert suite.type == symbols.suite
            suite_children = suite.children
            assert len(suite_children) > 2, len(suite_children)
            assert suite_children[0].type == tokens.NEWLINE and suite_children[0].value == '\n'
            assert suite_children[1].type == tokens.INDENT and suite_children[1].value == '    '
            for suite_child in itertools.islice(suite_children, 2, None):
                if suite_child.type == symbols.decorated:
                    decorator = state.Decorator(suite_child, container = self, state = state)
                    self.variable_value_by_name[decorator.decorated.name] = decorator
                elif suite_child.type == symbols.funcdef:
                    function = state.Function(suite_child, container = self, state = state)
                    self.variable_value_by_name[function.name] = function
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
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise

    @property
    def containing_class(self):
        return self

    def get_variable_value(self, name, default = UnboundLocalError, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is UnboundLocalError:
            container = self.container
            if container is not None:
                return container.get_variable_value(name, default = default, state = state)
        if value is UnboundLocalError:
            # TODO: Handle class inheritance.
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            value = default
        return value

    def has_variable(self, name, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is not UnboundLocalError:
            return True
        container = self.container
        if container is not None:
            return container.has_variable(name, state = state)
        return False


class ClassFileInput(AbstractWrapper):
    def get_class_definition_class(self, state):
        return state.Class

    @classmethod
    def parse(cls, class_definition, state = None):
        source_lines, line_number = inspect.getsourcelines(class_definition)
        source = textwrap.dedent(''.join(source_lines))
        node = state.driver.parse_string(source)
        assert node.type == symbols.file_input, "Expected a node of type {}. Got:\n{}\n\n{}".format(
            type_symbol(symbols.file_input), repr(node), unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2 and children[0].type == symbols.classdef and children[1].type == tokens.ENDMARKER, \
            "Unexpected node children in:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        module = state.Module(node, python = inspect.getmodule(class_definition), state = state)
        self = cls(None, state = state)
        class_definition_class = self.get_class_definition_class(state)
        try:
            return class_definition_class(children[0], container = module, state = state)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class Continue(AbstractWrapper):
    pass


class Date(AbstractWrapper):
    pass


class DatedHolder(AbstractWrapper):
    column = None
    data_type = None
    entity_key_plural = None
    is_argument = False

    def __init__(self, node, column = None, data_type = None, entity_key_plural = None, is_argument = False,
            state = None):
        super(DatedHolder, self).__init__(node, state = state)
        if column is not None:
            self.column = column
            assert column.dtype == data_type, str((column.dtype, data_type))
            assert column.entity_key_plural == entity_key_plural
        if data_type is not None:
            self.data_type = data_type
        if entity_key_plural is not None:
            self.entity_key_plural = entity_key_plural
        if is_argument:
            self.is_argument = True


class DateTime64(AbstractWrapper):
    pass


class Decorator(AbstractWrapper):
    decorated = None
    subject = None  # The decorator

    def __init__(self, node, container = None, state = None):
        super(Decorator, self).__init__(node, container = container, state = state)

        try:
            children = node.children
            assert len(children) == 2, len(children)

            decorator = children[0]
            assert decorator.type == symbols.decorator
            decorator_children = decorator.children
            assert len(decorator_children) == 6, len(decorator_children)
            assert decorator_children[0].type == tokens.AT and decorator_children[0].value == '@'
            subject = state.Variable(decorator_children[1], container = container, state = state)
            self.name = decorator_children[1].value
            assert decorator_children[2].type == tokens.LPAR and decorator_children[2].value == '('
            subject = state.Call(subject, decorator_children[3], container = container, state = state)
            assert decorator_children[4].type == tokens.RPAR and decorator_children[4].value == ')'
            assert decorator_children[5].type == tokens.NEWLINE and decorator_children[5].value == '\n'
            self.subject = subject

            decorated = children[1]
            assert decorated.type == symbols.funcdef
            self.decorated = state.Function(decorated, container = container, state = state)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class Enum(AbstractWrapper):
    pass


class Entity(AbstractWrapper):
    pass


class EntityToEntity(AbstractWrapper):
    keyword_arguments = None
    method_name = None
    named_arguments = None
    positional_arguments = None
    star_arguments = None

    def __init__(self, node, keyword_arguments = None, method_name = None, named_arguments = None,
            positional_arguments = None, star_arguments = None, state = None):
        super(EntityToEntity, self).__init__(node, state = state)
        if keyword_arguments is not None:
            self.keyword_arguments = keyword_arguments
        if method_name is not None:
            self.method_name = method_name
        if named_arguments is not None:
            self.named_arguments = named_arguments
        if positional_arguments is not None:
            self.positional_arguments = positional_arguments
        if star_arguments is not None:
            self.star_arguments = star_arguments


class For(AbstractWrapper):
    def __init__(self, node, container = None, state = None):
        super(For, self).__init__(node, container = container, state = state)

        # TODO: Parse and store attributes.


class Function(AbstractWrapper):
    body = None
    name = None
    named_parameters = None
    positional_parameters = None
    returns = None  # List of Return wrappers present in function
    variable_value_by_name = None

    def __init__(self, node, container = None, state = None):
        super(Function, self).__init__(node, container = container, state = state)
        self.returns = []
        self.variable_value_by_name = collections.OrderedDict()

        try:
            children = node.children
            assert len(children) == 5
            assert children[0].type == tokens.NAME and children[0].value == 'def'
            assert children[1].type == tokens.NAME  # Function name
            self.name = children[1].value

            parameters = children[2]
            assert parameters.type == symbols.parameters
            parameters_children = parameters.children
            assert len(parameters_children) == 3
            assert parameters_children[0].type == tokens.LPAR and parameters_children[0].value == '('

            if parameters_children[1].type == tokens.NAME:
                # Single positional parameter
                typedargslist = None
                typedargslist_children = [parameters_children[1]]
            else:
                typedargslist = parameters_children[1]
                assert typedargslist.type == symbols.typedargslist
                typedargslist_children = typedargslist.children

            self.named_parameters = named_parameters = collections.OrderedDict()
            self.positional_parameters = positional_parameters = []
            typedargslist_child_index = 0
            while typedargslist_child_index < len(typedargslist_children):
                typedargslist_child = typedargslist_children[typedargslist_child_index]
                assert typedargslist_child.type == tokens.NAME
                parameter_name = typedargslist_child.value
                typedargslist_child_index += 1
                if typedargslist_child_index >= len(typedargslist_children):
                    positional_parameters.append(parameter_name)
                    break
                typedargslist_child = typedargslist_children[typedargslist_child_index]
                if typedargslist_child.type == tokens.COMMA:
                    positional_parameters.append(parameter_name)
                    typedargslist_child_index += 1
                elif typedargslist_child.type == tokens.EQUAL:
                    typedargslist_child_index += 1
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    named_parameters[parameter_name] = typedargslist_child
                    typedargslist_child_index += 1
                    if typedargslist_child_index >= len(typedargslist_children):
                        break
                    typedargslist_child = typedargslist_children[typedargslist_child_index]
                    assert typedargslist_child.type == tokens.COMMA
                    typedargslist_child_index += 1

            assert parameters_children[2].type == tokens.RPAR and parameters_children[2].value == ')'

            assert children[3].type == tokens.COLON and children[3].value == ':'

            suite = children[4]
            assert suite.type == symbols.suite
            self.body = body = []
            suite_children = suite.children
            assert suite_children[0].type == tokens.NEWLINE and suite_children[0].value == '\n'
            assert suite_children[1].type == tokens.INDENT
            for suite_child in itertools.islice(suite_children, 2, None):
                if suite_child.type == symbols.for_stmt:
                    for_wrapper = state.For(suite_child, container = self, state = state)
                    body.append(for_wrapper)
                elif suite_child.type == symbols.funcdef:
                    function = state.Function(suite_child, container = self, state = state)
                    body.append(function)
                    self.variable_value_by_name[function.name] = function
                elif suite_child.type == symbols.if_stmt:
                    if_wrapper = state.If(suite_child, container = self, state = state)
                    body.append(if_wrapper)
                elif suite_child.type == symbols.simple_stmt:
                    assert len(suite_child.children) == 2, \
                        "Unexpected length {} for simple statement in function definition:\n{}\n\n{}".format(
                            len(suite_child.children), repr(suite_child), unicode(suite_child).encode('utf-8'))
                    statement = suite_child.children[0]
                    if statement.type == symbols.expr_stmt:
                        assignment = state.Assignment(statement, container = self, state = state)
                        body.append(assignment)
                    elif statement.type == symbols.return_stmt:
                        return_wrapper = state.Return(statement, container = self, state = state)
                        body.append(return_wrapper)
                    else:
                        assert statement.type in (symbols.power, tokens.STRING), type_symbol(statement.type)
                    assert suite_child.children[1].type == tokens.NEWLINE and suite_child.children[1].value == '\n'
                elif suite_child.type == tokens.DEDENT:
                    continue
                else:
                    assert False, "Unexpected statement in function definition:\n{}\n\n{}".format(repr(suite_child),
                        unicode(suite_child).encode('utf-8'))

            # parameters = node.args
            # positional_parameters = parameters.args[: len(parameters.args) - len(parameters.defaults)]
            # for parameter in positional_parameters:
            #     parameter_name = parameter.id
            #     if parameter_name in ('_defaultP', '_P'):
            #         function_call.variable_value_by_name[parameter_name] = state.LawNode(
            #             is_reference = parameter_name == '_defaultP')
            #     elif parameter_name == 'period':
            #         function_call.variable_value_by_name[parameter_name] = state.Period()
            #     elif parameter_name == 'self':
            #         function_call.variable_value_by_name[parameter_name] = state.Formula()
            #     else:
            #         # Input variable
            #         if parameter_name.endswith('_holder'):
            #             column_name = parameter_name[:-len('_holder')]
            #             variable_value_class = state.DatedHolder
            #         else:
            #             column_name = parameter_name
            #             variable_value_class = state.Array
            #         column = state.tax_benefit_system.column_by_name.get(column_name)
            #         assert column is not None, u'{}@{}: Undefined input variable: {}'.format(
            #             state.column.entity_key_plural, state.column.name, parameter_name)
            #         function_call.variable_value_by_name[parameter_name] = variable_value_class(
            #             column = column,
            #             data_type = column.dtype,
            #             entity_key_plural = column.entity_key_plural,
            #             is_argument = True,
            #             )
            #
            # if parameters.defaults:
            #     # Named parameters
            #     for parameter, value in itertools.izip(
            #             parameters.args[len(parameters.args) - len(parameters.defaults):],
            #             parameters.defaults,
            #             ):
            #         assert isinstance(parameter, ast.Name), ast.dump(parameter)
            #         function_call.variable_value_by_name[parameter.id] = conv.check(function_call.parse_value)(value,
            #             state)
            #
            # for statement in node.body:
            #     statement = conv.check(function_call.parse_statement)(statement, state)
            #     if isinstance(statement, state.Return):
            #         value = statement.operation
            #         assert isinstance(value, state.Array), "Unexpected return value {} in node {}".format(value,
            #             ast.dump(node))
            #         data_type = value.data_type
            #         expected_data_type = state.column.dtype
            #         assert (
            #             data_type == expected_data_type
            #             or data_type == np.int32 and expected_data_type == np.float32
            #             or data_type == np.int32 and expected_data_type == np.int16
            #             ), "Formula returns an array of {} instead of {}".format(value.data_type, state.column.dtype)
            #         assert value.entity_key_plural == state.column.entity_key_plural, ast.dump(node)
            #         return value, None
            # assert False, 'Missing return statement in formula: {}'.format(ast.dump(node))
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise

    def call(self, named_arguments = None, positional_arguments = None, state = None):
        node = self.node
        function_call = state.FunctionCall(definition = self)
        assert not node.decorator_list, ast.dump(node)
        parameters = node.args
        for parameter, argument in itertools.izip(
                parameters.args[:len(parameters.args) - len(parameters.defaults)],
                positional_arguments,
                ):
            function_call.variable_value_by_name[parameter.id] = argument
        if parameters.defaults:
            for parameter, default_argument in itertools.izip(
                    parameters.args[len(parameters.args) - len(parameters.defaults):],
                    parameters.defaults,
                    ):
                argument = named_arguments.get(parameter.id, UnboundLocalError)
                if argument is UnboundLocalError:
                    named_arguments[parameter.id] = conv.check(function_call.parse_value)(default_argument, state)
        if parameters.vararg is None:
            assert len(parameters.args) - len(parameters.defaults) == len(positional_arguments), ast.dump(node)  # TODO
        else:
            assert len(parameters.args) - len(parameters.defaults) <= len(positional_arguments), \
                str((ast.dump(node), positional_arguments))  # TODO # noqa
            function_call.variable_value_by_name[parameters.vararg] = positional_arguments[len(parameters.args):]
        assert parameters.kwarg is None, ast.dump(node)  # TODO
        function_call.variable_value_by_name.update(named_arguments)

        for statement in node.body:
            statement = conv.check(function_call.parse_statement)(statement, state)
            if isinstance(statement, state.Return):
                return statement.operation, None
        return None, None

    @property
    def containing_function(self):
        return self

    def get_variable_value(self, name, default = UnboundLocalError, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is UnboundLocalError:
            container = self.container
            if container is not None:
                return container.get_variable_value(name, default = default, state = state)
        if value is UnboundLocalError:
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            value = default
        return value

    def has_variable(self, name, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is not UnboundLocalError:
            return True
        if value in self.named_parameters or value in self.positional_parameters:
            return True
        container = self.container
        if container is not None:
            return container.has_variable(name, state = state)
        return False


class FunctionCall(AbstractWrapper):
    definition = None
    variable_value_by_name = None

    def __init__(self, node, definition = None, state = None):
        super(FunctionCall, self).__init__(node, state = state)
        assert isinstance(definition, Function)
        self.definition = definition
        self.variable_value_by_name = collections.OrderedDict()

    def get_variable_value(self, name, default = UnboundLocalError, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is UnboundLocalError:
            container = self.definition.container
            if container is not None:
                return container.get_variable_value(name, default = default, state = state)
        if value is UnboundLocalError:
            if default is UnboundLocalError:
                raise KeyError("Undefined value for {}".format(name))
            value = default
        return value

    def has_variable(self, name, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is not UnboundLocalError:
            return True
        container = self.definition.container
        if container is not None:
            return container.has_variable(name, state = state)
        return False

    def parse_binary_operation(self, node, left, operator, right, state):
        operation = state.BinaryOperation(
            left = left,
            operator = operator,
            right = right,
            )
        if isinstance(operator, (ast.Add, ast.Div, ast.FloorDiv, ast.Mult, ast.Sub)):
            if isinstance(left, state.Array) and isinstance(right, state.Array):
                if left.data_type == np.bool and right.data_type == np.bool:
                    data_type = np.bool
                elif left.data_type in (np.bool, np.int16, np.int32) \
                        and right.data_type in (np.bool, np.int16, np.int32):
                    data_type = np.int32
                elif left.data_type in (np.bool, np.float32, np.int16, np.int32) \
                        and right.data_type in (np.bool, np.float32, np.int16, np.int32):
                    data_type = np.float32
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                assert left.entity_key_plural == right.entity_key_plural
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = left.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, state.Array) and isinstance(right, state.DateTime64):
                value = state.Array(
                    data_type = np.datetime64,
                    entity_key_plural = left.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, state.Array) and isinstance(right, (state.LawNode, state.Number)):
                if left.data_type == np.bool and right.data_type == bool:
                    data_type = np.bool
                elif left.data_type in (np.bool, np.int16, np.int32) and right.data_type in (bool, int):
                    data_type = np.int32
                elif left.data_type in (np.bool, np.float32, np.int16, np.int32) \
                        and right.data_type in (bool, float, int):
                    data_type = np.float32
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = left.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, state.DateTime64) and isinstance(right, state.Array):
                value = state.Array(
                    data_type = np.datetime64,
                    entity_key_plural = right.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, (state.LawNode, state.Number)) and isinstance(right, state.Array):
                if left.data_type == bool and right.data_type == np.bool:
                    data_type = np.bool
                elif left.data_type in (bool, int) and right.data_type in (np.bool, np.int16, np.int32):
                    data_type = np.int32
                elif left.data_type in (bool, float, int) \
                        and right.data_type in (np.bool, np.float32, np.int16, np.int32):
                    data_type = np.float32
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = right.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, (state.LawNode, state.Number)) and isinstance(right, (state.LawNode, state.Number)):
                if left.data_type == bool and right.data_type == bool:
                    data_type = bool
                elif left.data_type in (bool, int) and right.data_type in (bool, int):
                    data_type = int
                elif left.data_type in (bool, float, int) and right.data_type in (bool, float, int):
                    data_type = float
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                value = state.Number(
                    data_type = data_type,
                    operation = operation,
                    )
                return value, None
            assert False, 'left: {}\n    operator: {}\n    right: {}\n    node: {}'.format(left, operator, right,
                ast.dump(node))
        if isinstance(operator, (ast.BitAnd, ast.BitOr)):
            if isinstance(left, state.Array) and isinstance(right, state.Array):
                if left.data_type == np.bool and right.data_type in (np.bool, np.int16, np.int32):
                    data_type = np.bool
                elif left.data_type in (np.bool, np.int16, np.int32) and right.data_type == np.bool:
                    data_type = np.bool
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                assert left.entity_key_plural == right.entity_key_plural
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = left.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, state.Number) and isinstance(right, state.Number):
                if left.data_type == bool and right.data_type == bool:
                    data_type = bool
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                value = state.Number(
                    data_type = data_type,
                    operation = operation,
                    )
                return value, None
            assert False, 'left: {}\n    operator: {}\n    right: {}\n    node: {}'.format(left, operator, right,
                ast.dump(node))
        if isinstance(operator, ast.Mult):
            if isinstance(left, state.Array) and isinstance(right, state.Array):
                if left.data_type == np.float32 and right.data_type == np.float32:
                    data_type = np.float32
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                assert left.entity_key_plural == right.entity_key_plural
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = left.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, state.Array) and isinstance(right, (state.LawNode, state.Number)):
                if left.data_type in (np.float32, np.int16, np.int32) and right.data_type == float:
                    data_type = np.float32
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = left.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            if isinstance(left, (state.LawNode, state.Number)) and isinstance(right, state.Array):
                if left.data_type == float and right.data_type in (np.float32, np.int16, np.int32):
                    data_type = np.float32
                else:
                    assert False, '{} {} {}'.format(left.data_type, operator, right.data_type)
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = right.entity_key_plural,
                    operation = operation,
                    )
                return value, None
            assert False, 'left: {}\n    operator: {}\n    right: {}\n    node: {}'.format(left, operator, right,
                ast.dump(node))
        assert False, 'left: {}\n    operator: {}\n    right: {}\n    node: {}'.format(left, operator, right,
            ast.dump(node))

    def parse_call(self, node, state):
        assert isinstance(node, ast.Call), ast.dump(node)
        function = node.func
        positional_arguments = conv.check(conv.uniform_sequence(self.parse_value))(node.args, state)
        named_arguments = collections.OrderedDict(
            (keyword.arg, conv.check(self.parse_value)(keyword.value, state))
            for keyword in node.keywords
            )
        star_arguments = conv.check(self.parse_value)(node.starargs, state) if node.starargs is not None else None
        if star_arguments is not None:
            assert isinstance(star_arguments, (list, tuple)), star_arguments
            # print 'positional_arguments =', positional_arguments
            # print 'star_arguments =', star_arguments
            positional_arguments.extend(star_arguments)
            # print 'positional_arguments =', positional_arguments
            # print ast.dump(node)
        keyword_arguments = conv.check(self.parse_value)(node.kwargs, state) if node.kwargs is not None else None
        assert keyword_arguments is None, ast.dump(node)
        if isinstance(function, ast.Attribute):
            assert isinstance(function.ctx, ast.Load), ast.dump(node)
            value = conv.check(self.parse_value)(function.value, state)
            if isinstance(value, state.Array):
                method_name = function.attr
                if method_name in ('all', 'any'):
                    assert value.data_type == np.bool, ast.dump(node)
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    test = state.Number(
                        data_type = bool,
                        operation = value,
                        )
                    return test, None
                if method_name == 'astype':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    new_type = positional_arguments[0]
                    if isinstance(new_type, state.String):
                        if new_type.value in ('timedelta64[Y]', 'timedelta64[M]'):
                            assert value.data_type == np.datetime64
                            test = state.Array(
                                data_type = np.int32,
                                entity_key_plural = value.entity_key_plural,
                                operation = value,
                                )
                            return test, None
                        assert False, 'Unhandled data type {} for array method {}({}) in node {}'.format(
                            value.data_type, method_name, new_type, ast.dump(node))
                    if isinstance(new_type, state.Type):
                        if new_type.value is np.int16:
                            assert value.data_type == np.bool
                            test = state.Array(
                                data_type = np.int16,
                                entity_key_plural = value.entity_key_plural,
                                operation = value,
                                )
                            return test, None
                        assert False, 'Unhandled data type {} for array method {}({}) in node {}'.format(
                            value.data_type, method_name, new_type, ast.dump(node))
                    assert False, 'Unhandled data type {} for array method {}({}) in node {}'.format(value.data_type,
                        method_name, new_type, ast.dump(node))
                assert False, 'Unknown array method {} in node {}'.format(method_name, ast.dump(node))
            if isinstance(value, state.Formula):
                method_name = function.attr
                if method_name == 'any_by_roles':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    array_or_dated_holder = positional_arguments[0]
                    assert isinstance(array_or_dated_holder, (state.Array, state.DatedHolder))
                    default = named_arguments.get('default')
                    assert default is None, ast.dump(node)
                    entity = named_arguments.get('entity')
                    assert entity is None, ast.dump(node)
                    roles = named_arguments.get('roles')
                    if roles is not None:
                        assert isinstance(roles, list), ast.dump(node)
                        assert all(
                            isinstance(role, state.Number) and isinstance(role.value, int)
                            for role in roles
                            ), ast.dump(node)
                    # operation = state.EntityToEntity(method_name = method_name,
                    #     named_arguments = named_arguments, positional_arguments = positional_arguments)
                    array = state.Array(
                        data_type = np.bool,
                        entity_key_plural = state.column.entity_key_plural,
                        # operation = operation,
                        )
                    return array, None
                if method_name == 'cast_from_entity_to_role':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    array_or_dated_holder = positional_arguments[0]
                    assert isinstance(array_or_dated_holder, (state.Array, state.DatedHolder))
                    default = named_arguments.get('default')
                    assert default is None, ast.dump(node)
                    entity = named_arguments.get('entity')
                    assert entity is None, ast.dump(node)
                    role = named_arguments['role']
                    assert isinstance(role, state.Number), ast.dump(node)
                    assert isinstance(role.value, int), ast.dump(node)
                    # operation = state.EntityToEntity(method_name = method_name,
                    #     named_arguments = named_arguments, positional_arguments = positional_arguments)
                    array = state.Array(
                        data_type = array_or_dated_holder.data_type,
                        entity_key_plural = u'individus',  # TODO
                        # operation = operation,
                        )
                    return array, None
                if method_name == 'cast_from_entity_to_roles':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    array_or_dated_holder = positional_arguments[0]
                    assert isinstance(array_or_dated_holder, (state.Array, state.DatedHolder))
                    default = named_arguments.get('default')
                    assert default is None, ast.dump(node)
                    entity = named_arguments.get('entity')
                    assert entity is None, ast.dump(node)
                    roles = named_arguments.get('roles')
                    if roles is not None:
                        assert isinstance(roles, list), ast.dump(node)
                        assert all(
                            isinstance(role, state.Number) and isinstance(role.value, int)
                            for role in roles
                            ), ast.dump(node)
                    # operation = state.EntityToEntity(method_name = method_name,
                    #     named_arguments = named_arguments, positional_arguments = positional_arguments)
                    array = state.Array(
                        data_type = array_or_dated_holder.data_type,
                        entity_key_plural = u'individus',  # TODO
                        # operation = operation,
                        )
                    return array, None
                if method_name == 'filter_role':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    array_or_dated_holder = positional_arguments[0]
                    assert isinstance(array_or_dated_holder, (state.Array, state.DatedHolder))
                    default = named_arguments.get('default')
                    assert default is None, ast.dump(node)
                    entity = named_arguments.get('entity')
                    assert entity is None, ast.dump(node)
                    role = named_arguments['role']
                    assert isinstance(role, state.Number), ast.dump(node)
                    assert isinstance(role.value, int), ast.dump(node)
                    # operation = state.EntityToEntity(method_name = method_name,
                    #     named_arguments = named_arguments, positional_arguments = positional_arguments)
                    array = state.Array(
                        data_type = array_or_dated_holder.data_type,
                        entity_key_plural = state.column.entity_key_plural,
                        # operation = operation,
                        )
                    return array, None
                if method_name == 'split_by_roles':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    array_or_dated_holder = positional_arguments[0]
                    assert isinstance(array_or_dated_holder, (state.Array, state.DatedHolder))
                    default = named_arguments.get('default')
                    assert default is None, ast.dump(node)
                    entity = named_arguments.get('entity')
                    assert entity is None, ast.dump(node)
                    roles = named_arguments.get('roles')
                    if roles is not None:
                        if isinstance(roles, list):
                            assert all(
                                isinstance(role, state.Number) and isinstance(role.value, int)
                                for role in roles
                                ), ast.dump(node)
                        elif isinstance(roles, state.UniformList) and isinstance(roles.item, state.Number) \
                                and roles.item.data_type == int:
                            pass
                        else:
                            assert False, ast.dump(node)
                    # operation = state.EntityToEntity(method_name = method_name,
                    #     named_arguments = named_arguments, positional_arguments = positional_arguments)
                    array_by_role = state.UniformDictionary(
                        key = state.Number(),
                        value = state.Array(
                            data_type = array_or_dated_holder.data_type,
                            entity_key_plural = state.column.entity_key_plural,
                            # operation = operation,
                            ),
                        )
                    return array_by_role, None
                if method_name == 'sum_by_entity':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    array_or_dated_holder = positional_arguments[0]
                    assert isinstance(array_or_dated_holder, (state.Array, state.DatedHolder))
                    default = named_arguments.get('default')
                    assert default is None, ast.dump(node)
                    entity = named_arguments.get('entity')
                    assert entity is None, ast.dump(node)
                    roles = named_arguments.get('roles')
                    if roles is not None:
                        assert isinstance(roles, list), ast.dump(node)
                        assert all(
                            isinstance(role, state.Number) and isinstance(role.value, int)
                            for role in roles
                            ), ast.dump(node)
                    # operation = state.EntityToEntity(method_name = method_name,
                    #     named_arguments = named_arguments, positional_arguments = positional_arguments)
                    array = state.Array(
                        data_type = (array_or_dated_holder.data_type
                            if array_or_dated_holder.data_type != np.bool
                            else np.int32),
                        entity_key_plural = state.column.entity_key_plural,
                        # operation = operation,
                        )
                    return array, None
                assert False, ast.dump(node)
            if isinstance(value, state.LawNode):
                method_name = function.attr
                if method_name == 'add_bracket':
                    # assert len(positional_arguments) == 1, ast.dump(node)
                    # assert len(named_arguments) == 0, ast.dump(node)
                    # tax_scale = positional_arguments[0]
                    # assert isinstance(tax_scale, (state.LawNode, state.TaxScalesTree)), ast.dump(node)
                    return state.LawNode(), None
                if method_name == 'add_tax_scale':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    tax_scale = positional_arguments[0]
                    assert isinstance(tax_scale, (state.LawNode, state.TaxScalesTree)), ast.dump(node)
                    return state.LawNode(), None
                if method_name == 'calc':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    input_array = positional_arguments[0]
                    assert isinstance(input_array, state.Array), ast.dump(node)
                    array = state.Array(
                        data_type = input_array.data_type,
                        entity_key_plural = input_array.entity_key_plural,
                        # operation = operation,
                        )
                    return array, None
                if method_name == 'inverse':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.LawNode(), None
                assert False, 'Unknown LawNode method {} in node {}'.format(method_name, ast.dump(node))
            if isinstance(value, state.Logger):
                # Ignore logging methods.
                return None, None
            if isinstance(value, state.Math):
                method_name = function.attr
                if method_name == 'floor':
                    return state.Number(data_type = float), None
                assert False, 'Unknown math method {} in node {}'.format(method_name, ast.dump(node))
            if isinstance(value, state.TaxScalesTree):
                method_name = function.attr
                if method_name == 'add_bracket':
                    # assert len(positional_arguments) == 1, ast.dump(node)
                    # assert len(named_arguments) == 0, ast.dump(node)
                    # tax_scale = positional_arguments[0]
                    # assert isinstance(tax_scale, (state.LawNode, state.TaxScalesTree)), ast.dump(node)
                    return state.LawNode(), None
                if method_name == 'add_tax_scale':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    tax_scale = positional_arguments[0]
                    assert isinstance(tax_scale, (state.LawNode, state.TaxScalesTree)), ast.dump(node)
                    return state.LawNode(), None
                if method_name == 'calc':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    input_array = positional_arguments[0]
                    assert isinstance(input_array, state.Array), ast.dump(node)
                    array = state.Array(
                        data_type = input_array.data_type,
                        entity_key_plural = input_array.entity_key_plural,
                        # operation = operation,
                        )
                    return array, None
                if method_name == 'get':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    name = positional_arguments[0]
                    assert isinstance(name, state.String), ast.dump(node)
                    return state.TaxScalesTree(), None
                if method_name == 'inverse':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.LawNode(), None
                if method_name == 'itervalues':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.UniformIterator(item = state.TaxScalesTree()), None
                if method_name == 'keys':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.UniformList(item = state.String()), None
                if method_name == 'multiply_rates':
                    # assert len(positional_arguments) == 1, ast.dump(node)
                    # assert len(named_arguments) == 0, ast.dump(node)
                    # tree = positional_arguments[0]
                    # assert isinstance(tree, state.TaxScalesTree), ast.dump(node)
                    return state.LawNode(), None
                if method_name == 'update':
                    assert len(positional_arguments) == 1, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    tree = positional_arguments[0]
                    assert isinstance(tree, state.TaxScalesTree), ast.dump(node)
                    return state.TaxScalesTree(), None
                assert False, 'Unknown TaxScalesTree method {} in node {}'.format(method_name, ast.dump(node))
            if isinstance(value, state.UniformDictionary):
                method_name = function.attr
                if method_name == 'iterkeys':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.UniformIterator(item = value.key), None
                if method_name == 'iteritems':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.UniformIterator(item = state.Structure([value.key, value.value])), None
                if method_name == 'itervalues':
                    assert len(positional_arguments) == 0, ast.dump(node)
                    assert len(named_arguments) == 0, ast.dump(node)
                    return state.UniformIterator(item = value.value), None
                assert False, 'Unknown UniformDictionary method {} in node {}'.format(method_name, ast.dump(node))
            assert False, 'Unhandled container {} in node {}'.format(value, ast.dump(node))
        assert isinstance(function, ast.Name), ast.dump(node)
        assert isinstance(function.ctx, ast.Load), ast.dump(node)
        function_name = function.id
        if function_name in ('around', 'round'):
            assert 1 <= len(positional_arguments) <= 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            array = positional_arguments[0]
            assert isinstance(array, (state.Array, state.LawNode, state.Number)), ast.dump(node)
            if len(positional_arguments) >= 2:
                decimals = positional_arguments[1]
                assert isinstance(decimals, state.Number), ast.dump(node)
            return array, None
        if function_name == 'combine_tax_scales':
            assert 1 <= len(positional_arguments) <= 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            tax_scales_tree = positional_arguments[0]
            assert isinstance(tax_scales_tree, state.TaxScalesTree), ast.dump(node)
            return state.LawNode(), None
        if function_name == 'datetime64':
            assert len(positional_arguments) == 1, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            date = positional_arguments[0]
            assert isinstance(date, state.Date), ast.dump(node)
            return state.DateTime64(), None
        if function_name in ('ceil', 'floor', 'not_'):
            assert len(positional_arguments) == 1, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            array = positional_arguments[0]
            assert isinstance(array, (state.Array, state.LawNode, state.Number)), ast.dump(node)
            return array, None
        if function_name == 'fsolve':
            assert len(positional_arguments) == 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            function = positional_arguments[0]
            assert isinstance(function, state.Function), ast.dump(node)
            array = positional_arguments[1]
            assert isinstance(array, state.Array), ast.dump(node)
            result = state.Array(
                column = state.column,
                data_type = state.column.dtype,
                entity_key_plural = state.column.entity_key_plural,
                # operation = operation,
                )
            return result, None
        if function_name == 'hasattr':
            assert 2 <= len(positional_arguments) <= 3, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            return state.Number(data_type = bool), None
        if function_name == 'izip':
            assert len(positional_arguments) >= 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            items = []
            for iterable in positional_arguments:
                if isinstance(iterable, (state.UniformIterator, state.UniformList)):
                    items.append(iterable.item)
                else:
                    assert False, 'Unhandled iterable {} in izip for node {}'.format(iterable, ast.dump(node))
            return state.UniformIterator(item = state.Structure(items)), None
        if function_name == 'len':
            assert len(positional_arguments) == 1, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            value = positional_arguments[0]
            assert isinstance(value, state.Array), ast.dump(node)
            return state.ArrayLength(array = value), None
        if function_name == 'MarginalRateTaxScale':
            # assert len(positional_arguments) == 2, ast.dump(node)
            # assert len(named_arguments) == 0, ast.dump(node)
            # name_argument = positional_arguments[0]
            # assert isinstance(name_argument, state.String), ast.dump(node)
            # law_node = positional_arguments[1]
            # assert isinstance(law_node, state.LawNode), ast.dump(node)
            return state.LawNode(), None
        if function_name in ('max_', 'min_'):
            assert len(positional_arguments) == 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            result = positional_arguments[0]
            assert isinstance(result, (state.Array, state.LawNode, state.Number)), ast.dump(node)
            for argument in positional_arguments[1:]:
                if isinstance(result, state.Array) and isinstance(argument, state.Array):
                    if result.data_type == np.bool and argument.data_type == np.bool:
                        data_type = np.bool
                    elif result.data_type in (np.bool, np.int16, np.int32) \
                            and argument.data_type in (np.bool, np.int16, np.int32):
                        data_type = np.int32
                    elif result.data_type in (np.bool, np.float32, np.int16, np.int32) \
                            and argument.data_type in (np.bool, np.float32, np.int16, np.int32):
                        data_type = np.float32
                    else:
                        assert False, '{}({}, {})'.format(function_name, result.data_type, argument.data_type)
                    assert result.entity_key_plural == argument.entity_key_plural
                    result = state.Array(
                        data_type = data_type,
                        entity_key_plural = result.entity_key_plural,
                        # operation = operation,
                        )
                elif isinstance(result, state.Array) and isinstance(argument, (state.LawNode, state.Number)):
                    if result.data_type == np.bool and argument.data_type == bool:
                        data_type = np.bool
                    elif result.data_type in (np.bool, np.int16, np.int32) and argument.data_type in (bool, int):
                        data_type = np.int32
                    elif result.data_type in (np.bool, np.float32, np.int16, np.int32) \
                            and argument.data_type in (bool, float, int):
                        data_type = np.float32
                    else:
                        assert False, '{}({}, {})'.format(function_name, result.data_type, argument.data_type)
                    result = state.Array(
                        data_type = data_type,
                        entity_key_plural = result.entity_key_plural,
                        # operation = operation,
                        )
                elif isinstance(result, (state.LawNode, state.Number)) and isinstance(argument, state.Array):
                    if result.data_type == bool and argument.data_type == np.bool:
                        data_type = np.bool
                    elif result.data_type in (bool, int) and argument.data_type in (np.bool, np.int16, np.int32):
                        data_type = np.int32
                    elif result.data_type in (bool, float, int) \
                            and argument.data_type in (np.bool, np.float32, np.int16, np.int32):
                        data_type = np.float32
                    else:
                        assert False, '{}({}, {})'.format(function_name, result.data_type, argument.data_type)
                    result = state.Array(
                        data_type = data_type,
                        entity_key_plural = argument.entity_key_plural,
                        # operation = operation,
                        )
                else:
                    assert False, '{}({}, {})\n    node: {}'.format(function_name, result, argument, ast.dump(node))
            return result, None
        if function_name in ('and_', 'or_', 'xor_'):
            assert len(positional_arguments) == 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            result = positional_arguments[0]
            assert isinstance(result, (state.Array, state.LawNode, state.Number)), ast.dump(node)
            for argument in positional_arguments[1:]:
                if isinstance(result, state.Array) and isinstance(argument, state.Array):
                    assert result.entity_key_plural == argument.entity_key_plural
                    result = state.Array(
                        data_type = np.bool,
                        entity_key_plural = result.entity_key_plural,
                        # operation = operation,
                        )
                elif isinstance(result, state.Array) and isinstance(argument, (state.LawNode, state.Number)):
                    result = state.Array(
                        data_type = np.bool,
                        entity_key_plural = result.entity_key_plural,
                        # operation = operation,
                        )
                elif isinstance(result, (state.LawNode, state.Number)) and isinstance(argument, state.Array):
                    result = state.Array(
                        data_type = np.bool,
                        entity_key_plural = argument.entity_key_plural,
                        # operation = operation,
                        )
                else:
                    assert False, '{}({}, {})\n    node: {}'.format(function_name, result, argument, ast.dump(node))
            return result, None
        if function_name in ('ones', 'zeros'):
            assert len(positional_arguments) == 1, ast.dump(node)
            assert 0 <= len(named_arguments) <= 1, ast.dump(node)
            length = positional_arguments[0]
            assert isinstance(length, state.ArrayLength), ast.dump(node)
            cast_type = named_arguments.get('dtype')
            if cast_type is None:
                data_type = np.float32  # Should be np.float64
            else:
                assert isinstance(cast_type, state.Type), ast.dump(node)
                data_type = cast_type.value
            result = state.Array(
                data_type = data_type,
                entity_key_plural = length.array.entity_key_plural,
                # operation = operation,
                )
            return result, None
        if function_name == 'scale_tax_scales':
            assert len(positional_arguments) == 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            tax_scales_tree = positional_arguments[0]
            assert isinstance(tax_scales_tree, (state.LawNode, state.TaxScalesTree)), ast.dump(node)
            factor_argument = positional_arguments[1]
            assert isinstance(factor_argument, (state.LawNode, state.Number)), ast.dump(node)
            return tax_scales_tree.__class__(), None
        if function_name == 'startswith':
            assert len(positional_arguments) == 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            left = positional_arguments[0]
            right = positional_arguments[1]
            if isinstance(left, state.Array):
                value = state.Array(
                    data_type = np.bool,
                    entity_key_plural = left.entity_key_plural,
                    # operation = operation,
                    )
                return value, None
            assert False, '{}({}, {})\n    node: {}'.format(function_name, left, right, ast.dump(node))
        if function_name == 'TaxScalesTree':
            assert len(positional_arguments) == 2, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            name_argument = positional_arguments[0]
            assert isinstance(name_argument, state.String), ast.dump(node)
            law_node = positional_arguments[1]
            assert isinstance(law_node, state.LawNode), ast.dump(node)
            return state.TaxScalesTree(), None
        if function_name == 'where':
            assert 1 <= len(positional_arguments) <= 3, ast.dump(node)
            assert len(named_arguments) == 0, ast.dump(node)
            condition = positional_arguments[0]
            x = positional_arguments[1] if len(positional_arguments) >= 2 else None
            y = positional_arguments[2] if len(positional_arguments) >= 3 else None
            if isinstance(condition, state.Array):
                data_type = np.bool if x is None and y is None else x.data_type if x is not None else y.data_type
                if data_type is int:
                    data_type = np.int32
                value = state.Array(
                    data_type = data_type,
                    entity_key_plural = condition.entity_key_plural,
                    # operation = operation,
                    )
                return value, None
            assert False, '{}({}...)\n    node: {}'.format(function_name, condition, ast.dump(node))
        local_function = self.get_variable_value(function_name, default = None, state = state)
        if local_function is not None and isinstance(local_function, state.Function):
            return local_function.call(named_arguments = named_arguments, positional_arguments = positional_arguments,
                state = state)
        assert False, ast.dump(node)

    def parse_statement(self, node, state):
        if isinstance(node, ast.Assert):
            # TODO
            return None, None
        if isinstance(node, ast.Assign):
            targets = node.targets
            assert len(targets) == 1, targets
            target = targets[0]
            assert isinstance(target.ctx, ast.Store), ast.dump(node)
            if isinstance(target, ast.Name):
                self.variable_value_by_name[target.id] = conv.check(self.parse_value)(node.value, state)
                return None, None
            if isinstance(target, ast.Subscript):
                # For example: salarie['fonc']['etat']['excep_solidarite'] = salarie['fonc']['commun']['solidarite']
                return None, None
            if isinstance(target, ast.Tuple):
                assert isinstance(node.value, ast.Tuple), ast.dump(node)
                assert len(target.elts) == len(node.value.elts), ast.dump(node)
                for name_element, value in itertools.izip(target.elts, node.value.elts):
                    self.variable_value_by_name[name_element.id] = conv.check(self.parse_value)(value, state)
                return None, None
            assert False, ast.dump(node)
        if isinstance(node, ast.AugAssign):
            target = node.target
            assert isinstance(target.ctx, ast.Store), ast.dump(node)
            if isinstance(target, ast.Name):
                left = self.get_variable_value(target.id, state = state)
                right = conv.check(self.parse_value)(node.value, state)
                value, error = self.parse_binary_operation(node, left, node.op, right, state)
                if error is not None:
                    return value, error
                self.variable_value_by_name[target.id] = value
                return None, None
            assert False, ast.dump(node)
        if isinstance(node, ast.Continue):
            return state.Continue(), None
        if isinstance(node, ast.Expr):
            conv.check(self.parse_value)(node.value, state)
            return None, None
        if isinstance(node, ast.For):
            target = node.target
            assert isinstance(target.ctx, ast.Store), ast.dump(node)
            if isinstance(target, ast.Name):
                iter = conv.check(self.parse_value)(node.iter, state)
                if isinstance(iter, state.Enum):
                    loop_item = state.Structure([
                        state.String(),
                        state.Number(
                            data_type = int,
                            ),
                        ])
                elif isinstance(iter, (state.UniformIterator, state.UniformList)):
                    loop_item = iter.item
                else:
                    assert False, 'Unhandled loop item {} in {}'.format(iter, ast.dump(node))
                self.variable_value_by_name[target.id] = loop_item
            elif isinstance(target, ast.Tuple):
                targets = target
                iters = conv.check(self.parse_value)(node.iter, state)
                if isinstance(iters, state.UniformIterator):
                    iter = iters.item
                    if isinstance(iter, state.Structure):
                        for target, loop_item in itertools.izip(targets.elts, iter.items):
                            self.variable_value_by_name[target.id] = loop_item
                    else:
                        assert False, "Unhandled loop item {} in node {}".format(iter, ast.dump(node))
                else:
                    assert False, "Unhandled loop items {} in node {}".format(iters, ast.dump(node))
            else:
                assert False, "Unexpected target {} in node {}".format(target, ast.dump(node))
            execute_body = True
            execute_orelse = True
            if execute_body:
                for statement in node.body:
                    statement = conv.check(self.parse_statement)(statement, state)
                    if isinstance(statement, (state.Continue, state.Return)):
                        if execute_orelse:
                            # Value of test is unknown. Stop execution of body but don't return result.
                            break
                        return statement, None
            if execute_orelse:
                for statement in node.orelse:
                    statement = conv.check(self.parse_statement)(statement, state)
                    if isinstance(statement, (state.Continue, state.Return)):
                        if execute_body:
                            # Value of test is unknown. Stop execution of body but don't return result.
                            break
                        return statement, None
            return None, None
        if isinstance(node, ast.FunctionDef):
            function = state.Function(container = self, module = self.definition.module, node = node, state = state)
            self.variable_value_by_name[node.name] = function
            return function, None
        if isinstance(node, ast.Global):
            for name in node.names:
                # TODO: Currently handle globals as local variables.
                self.variable_value_by_name[name] = None
            return None, None
        if isinstance(node, ast.If):
            test = conv.check(self.parse_value)(node.test, state)
            if isinstance(test, state.Number) and test.value is not UnboundLocalError:
                execute_body = bool(test.value)
                execute_orelse = not execute_body
            else:
                execute_body = True
                execute_orelse = True
            return_statement = None
            if execute_body:
                for statement in node.body:
                    statement = conv.check(self.parse_statement)(statement, state)
                    if isinstance(statement, state.Continue):
                        if execute_orelse:
                            # Value of test is unknown. Stop execution of body but don't return result.
                            break
                        return statement, None
                    if isinstance(statement, state.Return):
                        if execute_orelse:
                            # Value of test is unknown. Stop execution of body but don't return result.
                            return_statement = statement
                            break
                        return statement, None
            if execute_orelse:
                for statement in node.orelse:
                    statement = conv.check(self.parse_statement)(statement, state)
                    if isinstance(statement, state.Continue):
                        if execute_body:
                            # Value of test is unknown. Stop execution of body but don't return result.
                            break
                        return statement, None
                    if isinstance(statement, state.Return):
                        if execute_body:
                            # Value of test is unknown. Stop execution of body but don't return result.
                            return_statement = statement
                            break
                        return statement, None
            return return_statement, None
        if isinstance(node, ast.Pass):
            return None, None
        if isinstance(node, ast.Return):
            value = conv.check(self.parse_value)(node.value, state)
            result = state.Return(operation = value)
            return result, None
        return node, u'Unexpected AST node for statement'

    def parse_value(self, node, state):
        if isinstance(node, ast.Attribute):
            assert isinstance(node.ctx, ast.Load), ast.dump(node)
            container = conv.check(self.parse_value)(node.value, state)
            name = node.attr
            if isinstance(container, state.Entity):
                assert name == 'simulation', name
                simulation = state.Simulation()
                return simulation, None
            if isinstance(container, state.Formula):
                assert name == 'holder', name
                holder = state.Holder(formula = container)
                return holder, None
            if isinstance(container, state.Holder):
                assert name == 'entity', name
                entity = state.Entity()
                return entity, None
            if isinstance(container, state.Instant):
                if name == 'date':
                    return state.Date(), None
                assert name == 'year', name
                number = state.Number(data_type = int)  # TODO
                return number, None
            if isinstance(container, state.LawNode):
                if name == '__dict__':
                    return state.TaxScalesTree(), None
                law_node = state.LawNode(is_reference = container.is_reference, name = name, parent = container)
                return law_node, None
            if isinstance(container, state.Period):
                if name == 'date':
                    return state.Date(), None
                if name == 'start':
                    return state.Instant(), None
                assert False, 'Unhandled attribute {} for {} in {}'.format(name, container, ast.dump(node))
                instant = state.Instant()
                return instant, None
            if isinstance(container, state.TaxScalesTree):
                if name in ('name', 'option'):
                    return state.String(), None
                if name in 'rates':
                    return state.UniformList(item = state.Number(data_type = float)), None
                assert False, 'Unhandled attribute {} for {} in {}'.format(name, container, ast.dump(node))
            assert False, 'Unhandled attribute {} for {} in {}'.format(name, container, ast.dump(node))
        if isinstance(node, ast.BinOp):
            left = conv.check(self.parse_value)(node.left, state)
            right = conv.check(self.parse_value)(node.right, state)
            return self.parse_binary_operation(node, left, node.op, right, state)
        if isinstance(node, ast.Call):
            return self.parse_call(node, state)
        if isinstance(node, ast.Compare):
            left = conv.check(self.parse_value)(node.left, state)
            operators = node.ops
            comparators = conv.check(conv.uniform_sequence(self.parse_value))(node.comparators, state)
            test = left
            for operator, comparator in itertools.izip(operators, comparators):
                if isinstance(operator, (ast.Eq, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.NotEq)):
                    if isinstance(test, state.Array) and isinstance(comparator, state.Array):
                        assert test.entity_key_plural == comparator.entity_key_plural
                        value = state.Array(
                            data_type = np.bool,
                            entity_key_plural = test.entity_key_plural,
                            # operation = operation,
                            )
                        return value, None
                    if isinstance(test, state.Array) and isinstance(comparator, (state.LawNode, state.Number)):
                        value = state.Array(
                            data_type = np.bool,
                            entity_key_plural = test.entity_key_plural,
                            # operation = operation,
                            )
                        return value, None
                    if isinstance(test, (state.LawNode, state.Number)) and isinstance(comparator, state.Array):
                        value = state.Array(
                            data_type = np.bool,
                            entity_key_plural = comparator.entity_key_plural,
                            # operation = operation,
                            )
                        return value, None
                    if isinstance(test, (state.LawNode, state.Number, state.String)) and isinstance(comparator,
                            (state.LawNode, state.Number, state.String)):
                        value = state.Number(
                            data_type = bool,
                            # operation = operation,
                            )
                        return value, None
                    assert False, 'left: {}\n    operator: {}\n    comparator: {}\n    node: {}'.format(test, operator,
                        comparator, ast.dump(node))
                if isinstance(operator, (ast.In, ast.NotIn)):
                    if isinstance(comparator, list):
                        value = state.Number(
                            data_type = bool,
                            # operation = operation,
                            )
                        return value, None
                    if isinstance(test, state.String) and isinstance(comparator, state.TaxScalesTree):
                        value = state.Number(
                            data_type = bool,
                            # operation = operation,
                            )
                        return value, None
                    # if isinstance(comparator, state.UniformDictionary):
                    #     if type(test) == type(comparator.key):
                    #         value = state.Number(
                    #             data_type = bool,
                    #             # operation = operation,
                    #             )
                    #         return value, None
                    #     assert False, 'left: {}\n    operator: {}\n    comparator: {}\n    node: {}'.format(test,
                    #         operator, comparator, ast.dump(node))
                    if isinstance(comparator, state.UniformList):
                        if type(test) == type(comparator.item):
                            value = state.Number(
                                data_type = bool,
                                # operation = operation,
                                )
                            return value, None
                        assert False, 'left: {}\n    operator: {}\n    comparator: {}\n    node: {}'.format(test,
                            operator, comparator, ast.dump(node))
                    assert False, 'left: {}\n    operator: {}\n    comparator: {}\n    node: {}'.format(test, operator,
                        comparator, ast.dump(node))
                if isinstance(operator, ast.Is):
                    value = state.Number(
                        data_type = bool,
                        # operation = operation,
                        )
                    return value, None
                assert False, 'left: {}\n    operator: {}\n    comparator: {}\n    node: {}'.format(test, operator,
                    comparator, ast.dump(node))
            return test, None
        if isinstance(node, ast.Lambda):
            return state.Lambda(container = self, module = self.definition.module, node = node, state = state), None
        if isinstance(node, ast.List):
            return [
                conv.check(self.parse_value)(element, state)
                for element in node.elts
                ], None
            return state.Number(data_type = type(node.n), value = node.n), None
        if isinstance(node, ast.Name):
            assert isinstance(node.ctx, ast.Load), ast.dump(node)
            if node.id == 'False':
                return state.Number(data_type = bool, value = False), None
            if node.id == 'math':
                return state.Math(), None
            if node.id == 'None':
                return None, None
            if node.id == 'True':
                return state.Number(data_type = bool, value = True), None
            return self.get_variable_value(node.id, state = state), None
        if isinstance(node, ast.Num):
            return state.Number(data_type = type(node.n), value = node.n), None
        if isinstance(node, ast.Str):
            return state.String(value = node.s), None
        if isinstance(node, ast.Subscript):
            collection = conv.check(self.parse_value)(node.value, state)
            if isinstance(collection, state.Enum):
                assert isinstance(node.slice, ast.Index), ast.dump(node)
                index = conv.check(self.parse_value)(node.slice.value, state)
                assert isinstance(index, state.String), ast.dump(node)
                item = state.Number(
                    data_type = int,
                    )
                return item, None
            if isinstance(collection, state.LawNode):
                # For example: xxx.rate[i].
                assert isinstance(node.slice, ast.Index), ast.dump(node)
                index = conv.check(self.parse_value)(node.slice.value, state)
                if isinstance(index, (state.LawNode, state.Number)):
                    item = state.Number(
                        data_type = float,
                        # operation = TODO,
                        )
                    return item, None
                if isinstance(index, state.String):
                    return state.LawNode(), None
                assert False, ast.dump(node)
            if isinstance(collection, state.Structure):
                assert isinstance(node.slice, ast.Index), ast.dump(node)
                index = conv.check(self.parse_value)(node.slice.value, state)
                assert isinstance(index, (state.LawNode, state.Number, state.String)), ast.dump(node)
                assert index.value is not None, ast.dump(node)
                return collection.items[index.value], None
            if isinstance(collection, state.TaxScalesTree):
                assert isinstance(node.slice, ast.Index), ast.dump(node)
                index = conv.check(self.parse_value)(node.slice.value, state)
                assert isinstance(index, (state.LawNode, state.String)), ast.dump(node)
                return state.TaxScalesTree(), None
            if isinstance(collection, state.UniformDictionary):
                assert isinstance(node.slice, ast.Index), ast.dump(node)
                index = conv.check(self.parse_value)(node.slice.value, state)
                assert isinstance(index, collection.key.__class__), ast.dump(node)
                return collection.value, None
            if isinstance(collection, state.UniformList):
                assert isinstance(node.slice, ast.Index), ast.dump(node)
                index = conv.check(self.parse_value)(node.slice.value, state)
                assert isinstance(index, (state.LawNode, state.Number)), ast.dump(node)
                return collection.item, None
            assert False, 'Unhandled collection {} for subscript in {}'.format(collection, ast.dump(node))
        if isinstance(node, ast.Tuple):
            return tuple(
                conv.check(self.parse_value)(element, state)
                for element in node.elts
                ), None
        if isinstance(node, ast.UnaryOp):
            operand = conv.check(self.parse_value)(node.operand, state)
            operator = node.op
            operation = state.UnaryOperation(
                operand = operand,
                operator = operator,
                )
            if isinstance(operator, ast.Invert):
                if isinstance(operand, state.Array):
                    assert operand.data_type == np.bool, 'operator: {}\n    operand: {}\n    node: {}'.format(operator,
                        operand, ast.dump(node))
                    value = state.Array(
                        data_type = operand.data_type,
                        entity_key_plural = operand.entity_key_plural,
                        operation = operation,
                        )
                    return value, None
                assert False, 'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
            if isinstance(operator, ast.Not):
                if isinstance(operand, list):
                    value = state.Number(
                        data_type = bool,
                        # operation = operation,
                        value = bool(operand),
                        )
                    return value, None
                assert False, 'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
            if isinstance(operator, ast.USub):
                if isinstance(operand, state.Array):
                    assert operand.data_type in (np.float32, np.int16, np.int32), \
                        'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
                    value = state.Array(
                        data_type = operand.data_type,
                        entity_key_plural = operand.entity_key_plural,
                        operation = operation,
                        )
                    return value, None
                if isinstance(operand, state.LawNode):
                    assert operand.data_type in (float, int), \
                        'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
                    value = state.Number(
                        data_type = operand.data_type,
                        # operation = operation,
                        )
                    return value, None
                if isinstance(operand, state.Number):
                    assert operand.data_type in (float, int), \
                        'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
                    value = state.Number(
                        data_type = operand.data_type,
                        # operation = operation,
                        value = -operand.value if operand.value is not None else None,
                        )
                    return value, None
                assert False, 'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
            assert False, 'operator: {}\n    operand: {}\n    node: {}'.format(operator, operand, ast.dump(node))
        assert False, ast.dump(node)
        return None, None


class FunctionFileInput(AbstractWrapper):
    def get_function_class(self, state):
        return state.Function

    @classmethod
    def parse(cls, function, state = None):
        source_lines, line_number = inspect.getsourcelines(function)
        source = textwrap.dedent(''.join(source_lines))
        # print source
        node = state.driver.parse_string(source)
        assert node.type == symbols.file_input, "Expected a node of type {}. Got:\n{}\n\n{}".format(
            type_symbol(symbols.file_input), repr(node), unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 2 and children[0].type == symbols.funcdef and children[1].type == tokens.ENDMARKER, \
            "Unexpected node children in:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
        module = state.Module(node, python = inspect.getmodule(function), state = state)
        self = cls(None, state = state)
        function_class = self.get_function_class(state)
        try:
            return function_class(children[0], container = module, state = state)
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class Holder(AbstractWrapper):
    formula = None

    def __init__(self, node, formula = None, state = None):
        super(Holder, self).__init__(node, state = state)
        if formula is not None:
            self.formula = formula


class If(AbstractWrapper):
    def __init__(self, node, container = None, state = None):
        super(If, self).__init__(node, container = container, state = state)

        # TODO: Parse and store attributes.


class Instant(AbstractWrapper):
    pass


class Key(AbstractWrapper):
    value = None
    subject = None

    def __init__(self, subject, node, container = None, state = None):
        super(Key, self).__init__(node, container = container, state = state)

        assert isinstance(subject, AbstractWrapper)
        self.subject = subject
        assert node.type == symbols.trailer, "Unexpected attribute type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) == 3, "Unexpected length {} of children in power key:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        left_bracket, key, right_bracket = children
        assert left_bracket.type == tokens.LSQB, "Unexpected left bracket type:\n{}\n\n{}".format(repr(left_bracket),
            unicode(left_bracket).encode('utf-8'))
        self.value = state.parse_value(key, container = container, state = state)
        assert right_bracket.type == tokens.RSQB, "Unexpected right bracket type:\n{}\n\n{}".format(repr(right_bracket),
            unicode(right_bracket).encode('utf-8'))


class Lambda(Function):
    pass


class LawNode(AbstractWrapper):
    data_type = float  # TODO
    is_reference = True
    name = None
    parent = None

    def __init__(self, node, is_reference = False, name = None, parent = None, state = None):
        super(LawNode, self).__init__(node, state = state)
        if not is_reference:
            self.is_reference = False
        assert (parent is None) == (name is None), str((name, parent))
        if name is not None:
            self.name = name
        if parent is not None:
            assert isinstance(parent, LawNode)
            self.parent = parent

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


class Logger(AbstractWrapper):
    pass


class Math(AbstractWrapper):
    pass


class Module(AbstractWrapper):
    python = None
    variable_value_by_name = None

    def __init__(self, node, python = None, state = None):
        super(Module, self).__init__(node, state = state)
        if python is not None:
            # Python module
            self.python = python
        self.variable_value_by_name = collections.OrderedDict(sorted(dict(
            CAT = state.Enum(None, state = state),
            CHEF = state.Number(None, state = state, value = 0),
            CONJ = state.Number(None, state = state, value = 1),
            CREF = state.Number(None, state = state, value = 1),
            # ENFS = state.UniformList(None, state.Number(None, state = state, value = TODO), state = state),
            int16 = state.Type(None, value = np.int16, state = state),
            int32 = state.Type(None, value = np.int32, state = state),
            law = state.LawNode(None, state = state),
            log = state.Logger(None, state = state),
            PAC1 = state.Number(None, state = state, value = 2),
            PAC2 = state.Number(None, state = state, value = 3),
            PAC3 = state.Number(None, state = state, value = 4),
            PART = state.Number(None, state = state, value = 1),
            PREF = state.Number(None, state = state, value = 0),
            TAUX_DE_PRIME = state.Number(None, state = state, value = 1 / 4),
            VOUS = state.Number(None, state = state, value = 0),
            ).iteritems()))

    @property
    def containing_module(self):
        return self

    def get_variable_value(self, name, default = UnboundLocalError, state = None):
        value = self.variable_value_by_name.get(name, UnboundLocalError)
        if value is UnboundLocalError:
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
            function = conv.check(state.FunctionFileInput.parse)(value, state)
            self.variable_value_by_name[name] = value = function
        return value

    def has_variable(self, name, state = None):
        return self.get_variable_value(name, default = NameError, state = state) is not NameError


class Number(AbstractWrapper):
    value = None

    def __init__(self, node, container = None, state = None, value = None):
        super(Number, self).__init__(node, container = container, state = state)
        assert (node is None) != (value is None)
        if node is None:
            self.value = str(value)
        else:
            assert node.type == tokens.NUMBER, "Unexpected number type:\n{}\n\n{}".format(repr(node),
                unicode(node).encode('utf-8'))
            self.value = node.value


class Period(AbstractWrapper):
    pass


class Return(AbstractWrapper):
    value = None

    def __init__(self, node, container = None, state = None):
        super(Return, self).__init__(node, container = container, state = state)

        containing_function = self.containing_function
        containing_function.returns.append(self)

        children = node.children
        assert len(children) == 2, len(children)
        assert children[0].type == tokens.NAME and children[0].value == 'return'
        self.value = state.parse_value(children[1], container = container, state = state)


class Simulation(AbstractWrapper):
    pass


class String(AbstractWrapper):
    value = None

    def __init__(self, node, container = None, state = None):
        super(String, self).__init__(node, container = container, state = state)
        assert node.type == tokens.STRING, "Unexpected string type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        self.value = node.value


class Structure(AbstractWrapper):
    items = None

    def __init__(self, node, items = None, state = None):
        super(Structure, self).__init__(node, state = state)
        self.items = items


class TaxScalesTree(AbstractWrapper):
    pass


class Tuple(AbstractWrapper):
    value = None

    def __init__(self, node, container = None, state = None):
        super(Tuple, self).__init__(node, container = container, state = state)
        assert node.type == symbols.testlist, "Unexpected tuple type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))

        items = []
        item_index = 0
        while item_index < len(items):
            item = items[item_index]
            items.append(state.parse_value(item, container = container, state = state))
            item_index += 1
            if item_index >= len(items):
                break
            comma = items[item_index]
            assert comma.type == tokens.COMMA, "Unexpected comma type:\n{}\n\n{}".format(repr(comma),
                unicode(comma).encode('utf-8'))
            item_index += 1

        self.value = tuple(items)


class Type(AbstractWrapper):
    value = None

    def __init__(self, node, value = None, state = None):
        super(Type, self).__init__(node, state = state)
        self.value = value


class UnaryOperation(AbstractWrapper):
    operand = None
    operator = None  # AST operator

    def __init__(self, node, operand = None, operator = None, state = None):
        super(UnaryOperation, self).__init__(node, state = state)
        if operand is not None:
            self.operand = operand
        if operator is not None:
            self.operator = operator


class UniformDictionary(AbstractWrapper):
    key = None
    value = None

    def __init__(self, node, key = None, value = None, state = None):
        super(UniformDictionary, self).__init__(node, state = state)
        if key is not None:
            self.key = key
        if value is not None:
            self.value = value


class UniformIterator(AbstractWrapper):
    item = None

    def __init__(self, node, item = None, state = None):
        super(UniformIterator, self).__init__(node, state = state)
        if item is not None:
            self.item = item


class UniformList(AbstractWrapper):
    item = None

    def __init__(self, node, item = None, state = None):
        super(UniformList, self).__init__(node, state = state)
        if item is not None:
            self.item = item


class Variable(AbstractWrapper):
    name = None

    def __init__(self, node, container = None, state = None):
        super(Variable, self).__init__(node, container = container, state = state)
        assert node.type == tokens.NAME, "Unexpected variable type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        self.name = node.value


# Formula-specific classes


class Formula(AbstractWrapper):
    pass


class FormulaClass(Class):
    pass


class FormulaClassFileInput(ClassFileInput):
    # Caution: This is not the whole module, but only a dummy "module" containing only the formula.
    def get_class_definition_class(self, state):
        return state.FormulaClass


class FormulaFunction(Function):
    def call_formula(self, state = None):
        node = self.node
        try:
            function_call = state.FunctionCall(node, definition = self, state = state)

            for parameter_name in self.positional_parameters:
                if parameter_name in ('_defaultP', '_P'):
                    function_call.variable_value_by_name[parameter_name] = state.LawNode(None,
                        is_reference = parameter_name == '_defaultP', state = state)
                elif parameter_name == 'period':
                    function_call.variable_value_by_name[parameter_name] = state.Period(None, state = state)
                elif parameter_name == 'self':
                    function_call.variable_value_by_name[parameter_name] = state.Formula(None, state = state)
                else:
                    # Input variable
                    if parameter_name.endswith('_holder'):
                        column_name = parameter_name[:-len('_holder')]
                        variable_value_class = state.DatedHolder
                    else:
                        column_name = parameter_name
                        variable_value_class = state.Array
                    column = state.tax_benefit_system.column_by_name.get(column_name)
                    assert column is not None, u'{}@{}: Undefined input variable: {}'.format(
                        state.column.entity_key_plural, state.column.name, parameter_name)
                    function_call.variable_value_by_name[parameter_name] = variable_value_class(
                        None,  # No node for an OpenFisca variable.
                        column = column,
                        data_type = column.dtype,
                        entity_key_plural = column.entity_key_plural,
                        is_argument = True,
                        state = state,
                        )

            for parameter_name, parameter_value_node in self.named_parameters.iteritems():
                function_call.variable_value_by_name[parameter_name] = conv.check(function_call.parse_value)(
                    parameter_value_node, state = state)

            suite = children[4]
            assert suite.type == symbols.suite
            suite_children = suite.children
            assert suite_children[0].type == tokens.NEWLINE and suite_children[0].value == '\n'
            assert suite_children[1].type == tokens.INDENT and suite_children[1].value == '    '

            # for statement in node.body:
            #     statement = conv.check(function_call.parse_statement)(statement, state)
            #     if isinstance(statement, state.Return):
            #         value = statement.operation
            #         assert isinstance(value, state.Array), "Unexpected return value {} in node {}".format(value,
            #             ast.dump(node))
            #         data_type = value.data_type
            #         expected_data_type = state.column.dtype
            #         assert (
            #             data_type == expected_data_type
            #             or data_type == np.int32 and expected_data_type == np.float32
            #             or data_type == np.int32 and expected_data_type == np.int16
            #             ), "Formula returns an array of {} instead of {}".format(value.data_type, state.column.dtype)
            #         assert value.entity_key_plural == state.column.entity_key_plural, ast.dump(node)
            #         return value, None
            # assert False, 'Missing return statement in formula: {}'.format(ast.dump(node))
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise


class FormulaFunctionFileInput(FunctionFileInput):
    # Caution: This is not the whole module, but only a dummy "module" containing only the formula.
    def get_function_class(self, state):
        return state.FormulaFunction


# Default state


class State(conv.State):
    column = None  # Formula column
    Array = Array
    ArrayLength = ArrayLength
    Assignment = Assignment
    Attribute = Attribute
    BinaryOperation = BinaryOperation
    Call = Call
    Class = Class
    ClassFileInput = ClassFileInput
    Continue = Continue
    Date = Date
    DateTime64 = DateTime64
    DatedHolder = DatedHolder
    Decorator = Decorator
    driver = None
    Entity = Entity
    EntityToEntity = EntityToEntity
    Enum = Enum
    For = For
    Formula = Formula
    FormulaClass = FormulaClass
    FormulaClassFileInput = FormulaClassFileInput
    FormulaFunction = FormulaFunction
    FormulaFunctionFileInput = FormulaFunctionFileInput
    Function = Function
    FunctionCall = FunctionCall
    FunctionFileInput = FunctionFileInput
    Holder = Holder
    If = If
    Instant = Instant
    Key = Key
    Lambda = Lambda
    LawNode = LawNode
    Logger = Logger
    Math = Math
    Module = Module
    Number = Number
    Period = Period
    Return = Return
    Simulation = Simulation
    String = String
    Structure = Structure
    tax_benefit_system = None
    TaxScalesTree = TaxScalesTree
    Tuple = Tuple
    Type = Type
    UnaryOperation = UnaryOperation
    UniformDictionary = UniformDictionary
    UniformIterator = UniformIterator
    UniformList = UniformList
    Variable = Variable

    def __init__(self, driver = None, tax_benefit_system = None):
        self.driver = driver
        self.tax_benefit_system = tax_benefit_system

    def parse_power(self, node, container = None, state = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))
        assert isinstance(state, State), "Invalid state {} for node:\n{}\n\n{}".format(state, repr(node),
            unicode(node).encode('utf-8'))

        assert node.type == symbols.power, "Unexpected power type:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        children = node.children
        assert len(children) >= 2, "Unexpected length {} of children in power:\n{}\n\n{}".format(
            len(children), repr(node), unicode(node).encode('utf-8'))
        header = children[0]
        assert header.type == tokens.NAME, "Unexpected header type:\n{}\n\n{}".format(repr(header),
            unicode(header).encode('utf-8'))
        subject = state.Variable(header, container = container, state = state)
        for trailer in itertools.islice(children, 1, None):
            assert trailer.type == symbols.trailer, "Unexpected trailer type:\n{}\n\n{}".format(repr(trailer),
                unicode(trailer).encode('utf-8'))
            trailer_children = trailer.children
            trailer_first_child = trailer_children[0]
            if trailer_first_child.type == tokens.DOT:
                subject = state.Attribute(subject, trailer, container = container, state = state)
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
                subject = state.Call(subject, arguments, container = container, state = state)
            else:
                subject = state.Key(subject, trailer, container = container, state = state)
        return subject

    def parse_value(self, node, container = None, state = None):
        assert isinstance(node, lib2to3.pytree.Base), "Invalid node:\n{}\n\n{}".format(repr(node),
            unicode(node).encode('utf-8'))
        assert isinstance(container, AbstractWrapper), "Invalid container {} for node:\n{}\n\n{}".format(container,
            repr(node), unicode(node).encode('utf-8'))
        assert isinstance(state, State), "Invalid state {} for node:\n{}\n\n{}".format(state, repr(node),
            unicode(node).encode('utf-8'))

        children = node.children
        if node.type == symbols.and_expr:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in and_expr:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.arith_expr:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in arith_expr:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.atom:
            assert len(children) == 3, "Unexpected length {} of children in atom:\n{}\n\n{}".format(
                len(children), repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.comparison:
            assert len(children) == 3, "Unexpected length {} of children in comparison:\n{}\n\n{}".format(
                len(children), repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.expr:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in expr:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.factor:
            assert len(children) == 2, "Unexpected length {} of children in factor:\n{}\n\n{}".format(len(children),
                repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.power:
            return state.parse_power(node, container = container, state = state)
        if node.type == symbols.term:
            assert len(children) >= 3 and (len(children) & 1), \
                "Unexpected length {} of children in term:\n{}\n\n{}".format(len(children), repr(node),
                unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.test:
            assert len(children) == 5, "Unexpected length {} of children in test:\n{}\n\n{}".format(
                len(children), repr(node), unicode(node).encode('utf-8'))
            assert children[1].type == tokens.NAME and children[1].value == 'if', \
                "Unexpected non-if token in test:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            assert children[3].type == tokens.NAME and children[3].value == 'else', \
                "Unexpected non-else token in test:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            return None  # TODO
        if node.type == symbols.testlist:
            return state.Tuple(node, container = container, state = state)
        if node.type == tokens.NAME:
            variable = state.Variable(node, container = container, state = state)
            value = container.has_variable(variable.name, state = state)
            assert value is not NameError, "Undefined variable {}".format(variable.name)
            return variable
        if node.type == tokens.NUMBER:
            return state.Number(node, container = container, state = state)
        if node.type == tokens.STRING:
            return state.String(node, container = container, state = state)
        assert False, "Unexpected value:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
