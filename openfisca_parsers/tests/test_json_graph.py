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


from nose.tools import assert_in, assert_not_equal, assert_equal

from openfisca_parsers.json_graph import asg_to_json_graph
from openfisca_parsers import show_json


#'''
#a(y) = b(y) + 1
#b(y) = 9
#'''

period_of_a = {
    'type': 'Period',
    }
b = {
    'type': 'Variable',
    'name': 'b',
    'formula': {
        'type': 'Constant',
        'value': 9,
        },
    'period': {
        'type': 'Period',
        },
    }
a = {
    'type': 'Variable',
    'name': 'a',
    'formula': {
        'type': 'ArithmeticOperation',
        'operator': 'sum',
        'operands': [
            {
                'type': 'ValueForPeriod',
                'period': period_of_a,
                'variable': b,
                },
            {
                'type': 'Constant',
                'value': 1,
                },
            ],
        },
    'period': period_of_a,
    }


#'''
#c(y) = d(y) + d(y+1)
#d(y) = e(y) + 1
#e(y) = 9
#'''

period_of_c = {
    'type': 'Period',
    }
period_of_d = {
    'type': 'Period',
    }
e = {
    'type': 'Variable',
    'name': 'e',
    'formula': {
        'type': 'Constant',
        'value': 9,
        },
    'period': {
        'type': 'Period',
        },
    }
d = {
    'type': 'Variable',
    'name': 'd',
    'formula': {
        'type': 'ArithmeticOperation',
        'operator': 'sum',
        'operands': [
            {
                'type': 'ValueForPeriod',
                'period': period_of_d,
                'variable': e,
                },
            {
                'type': 'Constant',
                'value': 1,
                },
            ],
        },
    'period': period_of_d,
    }
c = {
    'type': 'Variable',
    'name': 'c',
    'formula': {
        'type': 'ArithmeticOperation',
        'operator': 'sum',
        'operands': [
            {
                'type': 'ValueForPeriod',
                'period': period_of_c,
                'variable': d,
                },
            {
                'type': 'ValueForPeriod',
                'period': {
                    'type': 'PeriodOperation',
                    'period': period_of_c,
                    'operator': 'next_year',
                    },
                'variable': d,
                },
            ],
        },
    'period': period_of_c,
    }

def test_same_period():
    module_ofnode = {
        'type': 'Module',
        'variables': [a, b],
        }
    json_graph = asg_to_json_graph(module_ofnode)
    show_json(json_graph)
    assert_in('graph', json_graph)
    assert_in('nodes', json_graph['graph'])
    assert_in('edges', json_graph['graph'])


def test_different_periods():
    module_ofnode = {
        'type': 'Module',
        'variables': [c, d]
        }
    json_graph = asg_to_json_graph(module_ofnode)
    show_json(json_graph)
    assert_in('graph', json_graph)
    assert_in('nodes', json_graph['graph'])
    assert_in('edges', json_graph['graph'])


def test_merge():
    '''
        Test a version of merge with a custom visit rule
    '''
    # MERGE RULES
    replace_rules = {'d': a, 'e': b}

    module_ofnode = {
        'type': 'Module',
        'variables': [a, b, c, d]
        }

    def rec_merge(node, replace_rules):
        if node['type'] == 'Module':
            node['variables'] = [
                rec_merge(child, replace_rules)
                for child in node['variables']
                ]

        if node['type'] == 'ArithmeticOperation':
            node['operands'] = [
                rec_merge(child, replace_rules)
                for child in node['operands']
                ]

        if node['type'] == 'Variable':
            if node['name'] in replace_rules:
                node = replace_rules[node['name']]
            if 'formula' in node:
                node['formula'] = rec_merge(node['formula'], replace_rules)

        if node['type'] == 'ValueForPeriod':
            if 'name' in node['variable']:
                node['variable'] = rec_merge(node['variable'], replace_rules)
        return node

    def recursive_assert(node):
        if node['type'] == 'Module':
            for child in node['variables']:
                recursive_assert(child)
        if node['type'] == 'ArithmeticOperation':
            for child in node['operands']:
                recursive_assert(child)
        if node['type'] == 'Variable' and 'formula' in node:
                recursive_assert(node['formula'])
        if node['type'] == 'ValueForPeriod':
                recursive_assert(node['variable'])

        if 'name' in node:
            assert_not_equal(node['name'],'d')
            assert_not_equal(node['name'],'e')

    initial_length = len(repr(module_ofnode))

    # MERGING
    module_ofnode = rec_merge(module_ofnode, replace_rules)
    final_length = len(repr(module_ofnode))

    # CHECKING MERGE
    recursive_assert(module_ofnode)
    assert_equal(initial_length, final_length)

    # CHECKING RESULTING GRAPH
    json_graph = asg_to_json_graph(module_ofnode)
    show_json(json_graph)
    assert_in('graph', json_graph)
    assert_in('nodes', json_graph['graph'])
    assert_in('edges', json_graph['graph'])
    assert_in('edges', json_graph['graph'])
