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


"""Functions to navigate in OpenFisca ASG nodes."""


import json

from toolz.curried import assoc, concatv, valfilter


# Input / output functions


def show_json(ofnodes):
    print(json.dumps(ofnodes, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8'))


# OpenFisca nodes creation / manipulation functions

def is_ofnode(value):
    return isinstance(value, dict) and 'type' in value


def make_ofnode(ofnode, rbnode, context, with_rbnode=False):
    """
    Create and return a new ofnode with a generated id, removing items with None values.
    with_rbnode: if True, reference the rbnode from the '_rbnode' key in the ofnode.
    """
    if with_rbnode:
        ofnode = assoc(ofnode, '_rbnode', rbnode)
    ofnode = valfilter(lambda value: value is not None, ofnode)
    return ofnode


def reduce_nested_binary_operators(operator, operand1_ofnode, operand2_ofnode):
    """
    Reduce many binary ArithmeticOperation nodes into one equivalent n-ary ArithmeticOperation.

    Examples:
        +(a, b) => +(a, b)
        +(+(a, b), c) => +(a, b, c)
        +(a, +(b, c)) => +(a, b, c)
        +(+(a, b), +(c, d)) => +(a, b, c, d)
    """
    operands_ofnodes = [operand1_ofnode, operand2_ofnode]
    if operand1_ofnode['type'] == 'ArithmeticOperation' and operand1_ofnode['operator'] == operator:
        operands_ofnodes = list(concatv(operand1_ofnode['operands'], [operand2_ofnode]))
    if operand2_ofnode['type'] == 'ArithmeticOperation' and operand2_ofnode['operator'] == operator:
        operands_ofnodes = list(concatv(operands_ofnodes[:-1], operand2_ofnode['operands']))
    return operands_ofnodes


def update_ofnode_stub(ofnode, merge):
    assert '_stub' in ofnode, ofnode
    ofnode.update(valfilter(lambda value: value is not None, merge))
    del ofnode['_stub']
    return ofnode
