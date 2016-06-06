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


from nose.tools import assert_equal, assert_not_equal, assert_not_in
from redbaron import RedBaron

from openfisca_parsers import contexts, visitors
from openfisca_parsers.scripts.variables_to_ast_json import show_json


def test_legislation_at():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start)
    return period, P
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    formula_dict = visitors.visit_rbnode(rbnode, context)
    show_json(formula_dict)
    assert_equal(formula_dict['formula_ofnode']['type'], 'ParameterAtInstant')
    assert_equal(formula_dict['formula_ofnode']['parameter']['path'], [])


def test_legislation_at_with_path():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start).aaa.bbb
    return period, P
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    formula_dict = visitors.visit_rbnode(rbnode, context)
    show_json(formula_dict)
    assert_equal(formula_dict['formula_ofnode']['type'], 'ParameterAtInstant')
    assert_equal(formula_dict['formula_ofnode']['parameter']['path'], ['aaa', 'bbb'])


def test_legislation_at_with_path_later():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start)
    return period, P.aaa.bbb
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    formula_dict = visitors.visit_rbnode(rbnode, context)
    show_json(formula_dict)
    assert_equal(formula_dict['formula_ofnode']['type'], 'ParameterAtInstant')
    assert_equal(formula_dict['formula_ofnode']['parameter']['path'], ['aaa', 'bbb'])


def test_legislation_at_with_paths_forks():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start).aaa.bbb
    xxx = P.xxx
    yyy = P.yyy
    zzz = yyy.zzz
    return period, xxx + zzz
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    formula_dict = visitors.visit_rbnode(rbnode, context)
    show_json(formula_dict)
    assert_equal(formula_dict['formula_ofnode']['type'], 'ArithmeticOperator')
    left_ofnode, right_ofnode = formula_dict['formula_ofnode']['operands']
    assert_equal(left_ofnode['type'], 'ParameterAtInstant')
    assert_equal(right_ofnode['type'], 'ParameterAtInstant')
    assert_equal(left_ofnode['parameter']['type'], 'Parameter')
    assert_equal(right_ofnode['parameter']['type'], 'Parameter')
    assert_equal(left_ofnode['parameter']['path'], ['aaa', 'bbb', 'xxx'])
    assert_equal(right_ofnode['parameter']['path'], ['aaa', 'bbb', 'yyy', 'zzz'])
    assert_not_equal(left_ofnode['id'], right_ofnode['id'])
    assert_not_equal(left_ofnode['parameter']['id'], right_ofnode['parameter']['id'])


def test_period_this_year():
    source_code = '''\
def function(self, simulation, period):
    period = period.this_year
    return period, 0
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    formula_dict = visitors.visit_rbnode(rbnode, context)
    show_json(formula_dict)
    assert_equal(formula_dict['formula_ofnode']['type'], 'Number')
    assert_equal(formula_dict['formula_ofnode']['value'], 0)
    assert_equal(formula_dict['output_period_ofnode']['type'], 'PeriodOperator')
    assert_equal(formula_dict['output_period_ofnode']['operator'], 'this_year')


def test_variable_class():
    source_code = '''\
class A(Variable):
    column = FloatCol
    entity_class = Familles

    def function(self, simulation, period):
        return period, 0
'''
    rbnode = RedBaron(source_code)[0]
    context = contexts.create()
    ofnode = visitors.visit_rbnode(rbnode, context)
    show_json(ofnode)
    assert_equal(ofnode['formula']['type'], 'Number')
    assert_equal(ofnode['formula']['value'], 0)
    assert_equal(ofnode['output_period']['type'], 'Period')
