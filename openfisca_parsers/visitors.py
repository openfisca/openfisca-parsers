# -*- coding: utf-8 -*-


# OpenFisca -- A versatile microsimulation software
# By: OpenFisca Team <contact@openfisca.fr>
#
# Copyright (C) 2011, 2012, 2013, 2014, 2015, 2016 OpenFisca Team
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


"""
Functions converting RedBaron nodes to OpenFisca ASG nodes.

Vocabulary:
- rbnode: redbaron nodes
- ofnode: openfisca node
- pyvariable: python variable

ofnodes are JSON-like data structures describing OpenFisca elements,
but replace some OpenFisca-Core specific vocabulary by more generic (no more columns for example).

ofnodes have this shape: {'type': 'CamelCase'}. The other fields depend on the 'type' field.
"""


from toolz.curried import assoc, concatv, keyfilter, map, merge
from toolz.curried.operator import attrgetter
import redbaron.nodes

from . import ofnodes as ofn, openfisca_data, rbnodes as rbn


# RedBaron nodes helpers


def is_significant_rbnode(rbnode):
    return not isinstance(rbnode, (redbaron.nodes.EndlNode, redbaron.nodes.CommaNode, redbaron.nodes.DotNode))


def to_unicode(string_or_unicode):
    """
    Fixes wrong unicode strings containing utf-8 bytes.
    Cf http://stackoverflow.com/questions/3182716/python-unicode-string-with-utf-8#comment43141617_14306718
    """
    if isinstance(string_or_unicode, str):
        string_or_unicode = string_or_unicode.decode('utf-8')
    else:
        assert isinstance(string_or_unicode, unicode), string_or_unicode
        string_or_unicode = string_or_unicode.encode('raw_unicode_escape').decode('utf-8')
    return string_or_unicode


# Generic visitor: rbnode, context -> ofnode | dict
# All specific visitors must call it to concentrate flow (ie log calls).


def visit_rbnode(rbnode, context):
    visitors = keyfilter(lambda key: key.startswith('visit_'), globals())
    visitor = visitors.get('visit_' + rbnode.type)
    if visitor is None:
        raise NotImplementedError(u'Visitor not declared for type="{type}", source="{source}"'.format(
            source=rbnode,
            type=rbnode.type,
            ))
    ofnode = visitor(rbnode, context)
    return ofnode


# Specific visitors: (rbnode, context) -> ofnode | dict | None
# Visitors can:
# - return an ofnode, a dict (which is not an ofnode of the graph, but is useful for the calling visitor), or None
# - write to context: the caller of the visitor who wrote to context should erase it after usage
# Returning a dict is simpler than writing to context because there is no cleanup management.


def visit_binary_operator(rbnode, context):
    operator = rbnode.value
    assert operator in ('+', '-', '*', '/', '&'), operator
    operand1_ofnode = visit_rbnode(rbnode.first, context)
    operand2_ofnode = visit_rbnode(rbnode.second, context)
    if operator == '-':
        # Transform a binary "-" operator in a binary "sum" whose second operand is wrapped in a unary "negate".
        operator = 'sum'
        operand2_ofnode = ofn.make_ofnode({
            'type': 'ArithmeticOperation',
            'operator': 'negate',
            'operand': operand2_ofnode,
            }, rbnode, context)
    operands_ofnodes = ofn.reduce_nested_binary_operators(operator, operand1_ofnode, operand2_ofnode)
    return ofn.make_ofnode({
        'type': 'ArithmeticOperation',
        'operator': operator,
        'operands': operands_ofnodes,
        }, rbnode, context)


def visit_assignment(rbnode, context):
    """Just forward to right hand side node. Handle special cases like "split_by_roles"."""
    pyvariable_name = rbnode.target.value
    if rbn.is_split_by_roles(rbnode.value):
        split_by_roles_dict = visit_rbnode(rbnode.value, context)
        context['split_by_role_infos_by_pyvariable_name'][pyvariable_name] = split_by_roles_dict
    else:
        ofnode = visit_rbnode(rbnode.value, context)
        context['pyvariable_by_name'][pyvariable_name] = ofnode
    return None


def visit_associative_parenthesis(rbnode, context):
    """Just forward to inner node."""
    return visit_rbnode(rbnode.value, context)


def visit_atomtrailers(rbnode, context):
    # Atomtrailers is a generic Python expression (a.b.c, a[0].b(1 + 2), etc.).

    def apply_rbnode_to_ofnode(ofnode, rbnode):
        """Return a new ofnode resulting from applying a rbnode to an ofnode."""
        if ofnode['type'] in ('Period', 'PeriodOperation'):
            if rbnode.value in ('start', 'this_year'):
                return ofn.make_ofnode({
                    'type': 'PeriodOperation',
                    'operator': rbnode.value,
                    'operand': ofnode,
                    }, rbnode, context)
            else:
                raise NotImplementedError(rbnode)
        elif ofnode['type'] == 'Parameter':
            parameter_path_fragment = rbnode.value
            parameter_path_fragments = list(concatv(ofnode['path'], [parameter_path_fragment]))
            parameter_path = '.'.join(parameter_path_fragments)
            # TODO Delegate finding to visit_name?
            parameter_ofnode = context['parameter_by_path'].get(parameter_path)
            if parameter_ofnode is None:
                parameter_ofnode = ofn.make_ofnode(assoc(ofnode, 'path', parameter_path_fragments), rbnode, context)
                context['parameter_by_path'][parameter_path] = parameter_ofnode
            return parameter_ofnode
        elif ofnode['type'] == 'ParameterAtInstant':
            new_parameter_ofnode = apply_rbnode_to_ofnode(ofnode['parameter'], rbnode)
            return ofn.make_ofnode(assoc(ofnode, 'parameter', new_parameter_ofnode), rbnode, context)
        else:
            raise NotImplementedError(ofnode)

    if rbn.is_simulation_calculate(rbnode.value):
        # simulation.compute return holders, which are represented by "ValueForPeriod" in the OpenFisca graph.
        variable_name = to_unicode(rbnode.call[0].value.to_python())
        period_pyvariable_name = rbnode.call[1].value.value
        # Ensure there is no more atom in trailer like ".x.y"" in "simulation.calculate('variable_name', period).x.y".
        assert len(rbnode.value) == 3, rbn.debug(rbnode, context)
        variable_ofnode = context['variable_by_name'].get(variable_name)
        if variable_ofnode is None:
            # Create a stub which will be completed when the real Variable class will be parsed.
            variable_ofnode = ofn.make_ofnode({
                '_stub': True,
                'type': 'Variable',
                'name': variable_name,
                }, rbnode, context)
        is_holder = rbnode.value[1].value == 'compute'
        return ofn.make_ofnode({
            'type': 'ValueForPeriod',
            '_is_holder': is_holder or None,
            'period': context['pyvariable_by_name'][period_pyvariable_name],
            'variable': variable_ofnode,
            }, rbnode, context)
    elif rbn.is_legislation_at(rbnode.value):
        period_operation_ofnode = visit_rbnode(rbnode.call[0].value, context)
        assert period_operation_ofnode['type'] == 'PeriodOperation', period_operation_ofnode
        parameter_path_rbnodes = rbnode[rbnode.call.index_on_parent + 1:]
        parameter_path_fragments = list(map(attrgetter('value'), parameter_path_rbnodes))
        parameter_path = '.'.join(parameter_path_fragments)
        # TODO Delegate finding to visit_name?
        parameter_ofnode = context['parameter_by_path'].get(parameter_path)
        if parameter_ofnode is None:
            parameter_ofnode = ofn.make_ofnode({
                'type': 'Parameter',
                'path': parameter_path_fragments,
                }, rbnode, context)
            context['parameter_by_path'][parameter_path] = parameter_ofnode
        return ofn.make_ofnode({
            'type': 'ParameterAtInstant',
            'parameter': parameter_ofnode,
            'instant': period_operation_ofnode,
            }, rbnode, context)
    elif rbn.is_split_by_roles(rbnode.value):
        holder_ofnode = visit_rbnode(rbnode.call[0].value, context)
        # TODO Check value type, not ofnode type.
        assert holder_ofnode['type'] == 'ValueForPeriod' and holder_ofnode['_is_holder'], holder_ofnode
        assert len(rbnode.call) <= 2 and rbnode.call[1].name.value == 'roles', rbn.debug(rbnode, context)
        roles = list(map(unicode, rbnode.call[1].value))
        # Just return extracted data (not an ofnode).
        return {'holder_ofnode': holder_ofnode, 'roles': roles}
    elif rbn.is_sum_by_entity(rbnode.value):
        holder_ofnode = visit_rbnode(rbnode.call[0].value, context)
        # TODO Check value type, not ofnode type.
        # assert holder_ofnode['type'] == 'ValueForPeriod' and holder_ofnode['_is_holder'], holder_ofnode
        assert len(rbnode.call) == 1, rbn.debug(rbnode, context)  # Later "roles" kwargs will be supported.
        return ofn.make_ofnode({
            'type': 'ValueForEntity',
            'operator': 'sum',
            'variable': holder_ofnode,
            }, rbnode, context)
    elif rbn.is_cast_from_entity_to_roles(rbnode.value):
        holder_ofnode = visit_rbnode(rbnode.call[0].value, context)
        # TODO Check value type, not ofnode type.
        assert holder_ofnode['type'] == 'ValueForPeriod' and holder_ofnode['_is_holder'], holder_ofnode
        assert len(rbnode.call) <= 2 and rbnode.call[1].name.value == 'role', rbn.debug(rbnode, context)
        role = rbnode.call[1].value.value
        return ofn.make_ofnode({
            'type': 'ValueForRole',
            'role': role,
            'variable': holder_ofnode,
            }, rbnode, context)
    else:
        first_rbnode = rbnode.value[0]
        assert first_rbnode.type == 'name', rbn.debug(first_rbnode, context)
        if first_rbnode.value in context['pyvariable_by_name']:
            # first_rbnode is a local variable of the function.
            other_rbnodes = rbnode.value[1:]
            name_ofnode = visit_rbnode(first_rbnode, context)
            ofnode = reduce(apply_rbnode_to_ofnode, other_rbnodes, name_ofnode)
            return ofnode
        elif first_rbnode.value in context['split_by_role_infos_by_pyvariable_name']:
            # Handle getitem nodes like "xxx[VOUS]".
            assert rbnode[1].type == 'getitem', rbn.debug(rbnode, context)
            role = rbnode.getitem.value.value
            variable_name = first_rbnode.value
            split_by_roles_dict = context['split_by_role_infos_by_pyvariable_name'][variable_name]
            holder_ofnode = split_by_roles_dict['holder_ofnode']
            # In OpenFisca-Core Python code, a "ValueForRole" must always be applied to a "ValueForPeriod",
            # which must be under its openfisca_core.holders.Holder form.
            assert holder_ofnode['type'] == 'ValueForPeriod' and holder_ofnode['_is_holder'], holder_ofnode
            # Keep general "variable" key as a "ValueForRole" and "ValueForPeriod" should be swappable
            # in the OpenFisca graph.
            return ofn.make_ofnode({
                'type': 'ValueForRole',
                'role': role,
                'variable': holder_ofnode,
                }, rbnode, context)
        else:
            # first_rbnode is a function, imported or builtin.
            # TODO Could be other things like a Python module.
            assert rbnode[1].type == 'call', rbn.debug(rbnode, context)
            call_arguments_rbnodes = rbnode.call.value
            # function_call_ofnode is a stub which was created by visit_name.
            function_call_ofnode = visit_rbnode(first_rbnode, context)
            assert function_call_ofnode['type'] == 'ArithmeticOperation', function_call_ofnode
            operands_ofnodes = [
                visit_rbnode(call_argument_rbnode.value, context)
                for call_argument_rbnode in call_arguments_rbnodes
                ]
            ofn.update_ofnode_stub(function_call_ofnode, merge={'operands': operands_ofnodes})
            # TODO Handle ".x" in f().x.
            rbnodes_after_call = rbnode[rbnode.call.index_on_parent + 1:]
            assert len(rbnodes_after_call) == 0, rbnodes_after_call
            return function_call_ofnode


def visit_class(rbnode, context):
    variable_name = rbnode.name

    column_rbnode = rbn.find_class_attribute(rbnode, name='column')
    column_name = column_rbnode.name.value
    column_kwargs = {
        kwarg_rbnode.target.value: kwarg_rbnode.value.to_python()
        for kwarg_rbnode in column_rbnode.call.value
        } \
        if column_rbnode.call is not None \
        else {}
    value_type = openfisca_data.value_type_by_column_name.get(column_name)
    assert value_type is not None, column_name
    if 'val_type' in column_kwargs:
        value_type = column_kwargs['val_type']
        if column_name == 'AgeCol' and value_type == 'months':
            value_type = 'age_in_months'
    default_value = column_kwargs.get('default')

    is_period_size_independent = column_name in ('AgeCol', 'PeriodSizeIndependentIntCol')

    label_rbnode = rbn.find_class_attribute(rbnode, name='label')
    label = to_unicode(label_rbnode.to_python()) if label_rbnode is not None else None

    entity_rbnode = rbn.find_class_attribute(rbnode, name='entity_class')
    entity_name = openfisca_data.get_entity_name(entity_rbnode.value)

    start_date_rbnode = rbn.find_class_attribute(rbnode, name='start_date')
    start_date = '-'.join(map(lambda rbnode: rbnode.value.value, start_date_rbnode.call.filtered())) \
        if start_date_rbnode is not None \
        else None

    stop_date_rbnode = rbn.find_class_attribute(rbnode, name='stop_date')
    stop_date = '-'.join(map(lambda rbnode: rbnode.value.value, stop_date_rbnode.call.filtered())) \
        if stop_date_rbnode is not None \
        else None

    ofnode_dict = {
        'type': 'Variable',
        'default_value': default_value,
        'entity': entity_name,
        'is_period_size_independent': is_period_size_independent,
        'label': label,
        'name': variable_name,
        'start_date': start_date,
        'stop_date': stop_date,
        'value_type': value_type,
        }

    def_rbnode = rbn.find_formula_function(rbnode)
    if def_rbnode is not None:
        input_period_ofnode = ofn.make_ofnode({'type': 'Period'}, rbnode, context)
        input_period_pyvariable_name = 'period'
        ofn.make_ofnode({
            'type': 'PythonVariableDeclaration',
            'name': input_period_pyvariable_name,
            'value': input_period_ofnode,
            }, rbnode, context)
        context['pyvariable_by_name'] = {input_period_pyvariable_name: input_period_ofnode}
        context['split_by_role_infos_by_pyvariable_name'] = {}
        formula_dict = visit_rbnode(def_rbnode, context)
        del context['pyvariable_by_name']
        del context['split_by_role_infos_by_pyvariable_name']
        ofnode_dict = merge(ofnode_dict, {
            'docstring': formula_dict['docstring'],
            'formula': formula_dict['formula_ofnode'],
            'input_period': input_period_ofnode,
            'output_period': formula_dict['output_period_ofnode'],
            })

    variable_ofnode = context['variable_by_name'].get(variable_name)
    if variable_ofnode is None:
        variable_ofnode = ofn.make_ofnode(ofnode_dict, rbnode, context)
        context['variable_by_name'][variable_name] = variable_ofnode
    else:
        # variable_ofnode is a stub which was created by `visit_atomtrailers`.
        ofn.update_ofnode_stub(variable_ofnode, merge=ofnode_dict)

    return variable_ofnode


def visit_comparison(rbnode, context):
    return ofn.make_ofnode({
        'type': 'ArithmeticOperation',
        'operator': rbnode.value.first,
        'operands': [
            visit_rbnode(rbnode.first, context),
            visit_rbnode(rbnode.second, context),
            ],
        }, rbnode, context)


def visit_def(rbnode, context):
    body_rbnodes = rbnode.value.filter(is_significant_rbnode)
    docstring_rbnode = body_rbnodes.find(('string', 'unicode_string'), recursive=False)
    docstring = to_unicode(docstring_rbnode.to_python().strip()) if docstring_rbnode is not None else None
    output_period_ofnode = formula_ofnode = None
    for index, rbnode in enumerate(body_rbnodes):
        if rbnode.type in ('comment', 'string'):
            continue
        elif rbnode.type == 'assignment':
            visit_rbnode(rbnode, context)
        elif rbnode.type == 'return':
            # TODO Ensure there is no forgotten nodes after return.
            # assert index == len(body_rbnodes) - 1, u'return is not the last function statement'
            output_period_ofnode, formula_ofnode = visit_rbnode(rbnode.value, context)
        else:
            raise NotImplementedError((rbnode.type, rbn.debug(rbnode, context)))
    # Just return extracted data (not an ofnode).
    formula_dict = {
        'docstring': docstring,
        'formula_ofnode': formula_ofnode,
        'output_period_ofnode': output_period_ofnode,
        }
    return formula_dict


def visit_float(rbnode, context):
    return ofn.make_ofnode({
        'type': 'Constant',
        'value': rbnode.to_python(),
        }, rbnode, context)


def visit_int(rbnode, context):
    return ofn.make_ofnode({
        'type': 'Constant',
        'value': rbnode.to_python(),
        }, rbnode, context)


def visit_name(rbnode, context):
    name = rbnode.value
    if name in context['pyvariable_by_name']:
        # name is a local variable of the function.
        return context['pyvariable_by_name'][name]
    else:
        # name is a function name, imported or builtin.
        # TODO name could be another thing, like a Python module name.
        # Create a stub which will be completed by visit_atomtrailers when parsing function call arguments.
        return ofn.make_ofnode({
            '_stub': True,
            'type': 'ArithmeticOperation',
            'operator': name,
            'operands': None,
            }, rbnode, context)


def visit_tuple(rbnode, context):
    ofnodes = [
        visit_rbnode(rbnode1, context)
        for rbnode1 in rbnode.value
        ]
    return ofnodes


def visit_unitary_operator(rbnode, context):
    operator = rbnode.value
    assert operator == '-', operator
    operand = visit_rbnode(rbnode.target, context)
    return ofn.make_ofnode({
        'type': 'ArithmeticOperation',
        'operator': operator,
        'operands': [operand],
        }, rbnode, context)
