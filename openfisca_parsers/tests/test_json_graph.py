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


from nose.tools import assert_in

from openfisca_parsers.json_graph import asg_to_json_graph
from openfisca_parsers.ofnodes import show_json


def test_same_period():
    '''
    a(y) = b(y) + 1
    b(y) = 9
    '''
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
    '''
    a(y) = b(y) + b(y+1)
    b(y) = c(y) + 1
    c(y) = 9
    '''
    period_of_a = {
        'type': 'Period',
        }
    period_of_b = {
        'type': 'Period',
        }
    c = {
        'type': 'Variable',
        'name': 'c',
        'formula': {
            'type': 'Constant',
            'value': 9,
            },
        'period': {
            'type': 'Period',
            },
        }
    b = {
        'type': 'Variable',
        'name': 'b',
        'formula': {
            'type': 'ArithmeticOperation',
            'operator': 'sum',
            'operands': [
                {
                    'type': 'ValueForPeriod',
                    'period': period_of_b,
                    'variable': c,
                    },
                {
                    'type': 'Constant',
                    'value': 1,
                    },
                ],
            },
        'period': period_of_b,
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
                    'type': 'ValueForPeriod',
                    'period': {
                        'type': 'PeriodOperation',
                        'period': period_of_a,
                        'operator': 'next_year',
                        },
                    'variable': b,
                    },
                ],
            },
        'period': period_of_a,
        }
    module_ofnode = {
        'type': 'Module',
        'variables': [a, b],
        }
    json_graph = asg_to_json_graph(module_ofnode)
    show_json(json_graph)
    assert_in('graph', json_graph)
    assert_in('nodes', json_graph['graph'])
    assert_in('edges', json_graph['graph'])
