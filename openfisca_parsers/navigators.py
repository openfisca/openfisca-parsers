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


"""Functions to navigate in RedBaron nodes."""


from toolz.curried import map
from toolz.curried.operator import attrgetter


def find_all_variable_classes(rbnode):
    return rbnode('class', inherit_from=lambda rbnodes: 'Variable' in map(attrgetter('value'), rbnodes))


def find_class_attribute(class_rbnode, name):
    class_attribute_rbnodes = class_rbnode.value('assignment', recursive=False)
    assignment_rbnode = class_attribute_rbnodes.find('assignment', target=lambda rbnode: rbnode.value == name)
    return assignment_rbnode.value if assignment_rbnode is not None else None


def find_column_default_value(column_rbnode):
    default_rbnode = column_rbnode.find('call_argument', target=lambda rbnode: rbnode.value == 'default')
    return default_rbnode.value.to_python() if default_rbnode is not None else None


def find_dependencies(rbnodes):
    calculate_rbnodes = rbnodes('atomtrailers', value=is_simulation_calculate_rbnodes)
    return list(map(
        lambda rbnode: rbnode.call[0].value.to_python(),
        calculate_rbnodes,
        ))


def find_formula_function_rbnode(class_rbnode):
    # TODO Match function parameters to be (self, simulation, period)
    return class_rbnode.find('def', name='function')


def find_parameters(rbnodes):
    legislation_at_rbnodes = rbnodes('atomtrailers', value=is_legislation_at_rbnodes)
    # TODO Handle periods and parameters spanned over multiple lines, like when using "P".
    return list(map(
        lambda rbnode: '.'.join(map(lambda node1: node1.value, rbnode[3:])),
        legislation_at_rbnodes,
        ))


def is_legislation_at_rbnodes(rbnodes):
    return len(rbnodes) >= 2 and rbnodes[0].value == 'simulation' and rbnodes[1].value == 'legislation_at'


def is_simulation_calculate_rbnodes(rbnodes):
    return len(rbnodes) >= 2 and rbnodes[0].value == 'simulation' and rbnodes[1].value == 'calculate'
