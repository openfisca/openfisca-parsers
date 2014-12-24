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
        except:
            if node is not None:
                print "An exception occurred in node:\n{}\n\n{}".format(repr(node), unicode(node).encode('utf-8'))
            raise

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
    pass


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
