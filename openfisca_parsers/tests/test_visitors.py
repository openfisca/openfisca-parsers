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


from nose.tools import assert_equal, assert_not_in
from redbaron import RedBaron

from openfisca_parsers import visitors
from openfisca_parsers.scripts.variables_to_ast_json import show_ofnodes  # noqa


def test_legislation_at():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start)
    return period, P
'''
    rbnode = RedBaron(source_code)[0]
    context = visitors.make_initial_context()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula_ofnode']['type'], 'ParameterAtInstant')
    assert_not_in('path', ofnode['formula_ofnode']['parameter'])


def test_legislation_at_with_path():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start).a.b
    return period, P
'''
    rbnode = RedBaron(source_code)[0]
    context = visitors.make_initial_context()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula_ofnode']['type'], 'ParameterAtInstant')
    assert_equal(ofnode['formula_ofnode']['parameter']['path'], ['a', 'b'])


def test_legislation_at_with_paths_fork():
    source_code = '''\
def function(self, simulation, period):
    P = simulation.legislation_at(period.start).a.b
    x = P.x
    y = P.y
    return period, x + y
'''
    rbnode = RedBaron(source_code)[0]
    context = visitors.make_initial_context()
    ofnode = visitors.visit_rbnode(rbnode, context)
    assert_equal(ofnode['formula_ofnode']['type'], 'ArithmeticOperator')
