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


"""Functions to navigate in OpenFisca AST nodes."""


from toolz.curried import assoc, concatv, valfilter

from . import openfisca_data


def make_ofnode(items, rbnode, context, with_rbnode=False):
    """
    Create and return a new ofnode with a generated id.
    with_rbnode: if True, reference the rbnode from the '_rbnode' key in the ofnode.
    """
    id = context['generate_shortid']()
    ofnode = assoc(items, 'id', id)
    if with_rbnode:
        ofnode = assoc(ofnode, '_rbnode', rbnode)
    return valfilter(lambda value: value is not None, ofnode)


def make_sum_of_value_for_all_roles_ofnode(ofnode, rbnode, context):
    """This is the expanded version of sum_by_entity."""
    entity_name = context['current_class_visitor']['entity_name']
    all_roles = openfisca_data.get_all_roles(entity_name)
    value_for_role_ofnodes = list(map(
        lambda role: make_ofnode({
            'type': 'ValueForRole',
            'role': role,
            'variable': ofnode,
            }, rbnode, context),
        all_roles,
        ))
    sum_ofnode = make_ofnode({
        'type': 'ArithmeticOperator',
        'operator': '+',
        'operands': value_for_role_ofnodes,
        }, rbnode, context)
    return sum_ofnode


def update_ofnode_stub(ofnode, merge):
    assert '_stub' in ofnode, ofnode
    ofnode.update(valfilter(lambda value: value is not None, merge))
    del ofnode['_stub']
    return ofnode


# Graph optimization functions


def reduce_binary_operator(operator, operand1_ofnode, operand2_ofnode):
    """
    Reduce many binary ArithmeticOperator nodes into one equivalent n-ary ArithmeticOperator.

    Examples:
        +(a, b) => +(a, b)
        +(+(a, b), c) => +(a, b, c)
        +(a, +(b, c)) => +(a, b, c)
        +(+(a, b), +(c, d)) => +(a, b, c, d)
    """
    operands_ofnodes = [operand1_ofnode, operand2_ofnode]
    if operand1_ofnode['type'] == 'ArithmeticOperator' and operand1_ofnode['operator'] == operator:
        operands_ofnodes = list(concatv(operand1_ofnode['operands'], [operand2_ofnode]))
    if operand2_ofnode['type'] == 'ArithmeticOperator' and operand2_ofnode['operator'] == operator:
        operands_ofnodes = list(concatv(operands_ofnodes[:-1], operand2_ofnode['operands']))
    return operands_ofnodes
