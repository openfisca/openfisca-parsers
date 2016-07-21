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


"""Functions to navigate in RedBaron nodes."""


from toolz.curried import map
from toolz.curried.operator import attrgetter


def debug(rbnode, context=None):
    return u'{} at line {}'.format(
        rbnode.dumps(),
        rbnode.absolute_bounding_box.top_left.line,
        )


def find_all_variable_classes(rbnode, names=None):
    return rbnode(
        'class',
        inherit_from=lambda rbnodes: 'Variable' in list(map(attrgetter('value'), rbnodes)),
        name=lambda value: value in names if names is not None else True,  # True disables the name filter
        )


def find_class_attribute(class_rbnode, name):
    class_attribute_rbnodes = class_rbnode.value('assignment', recursive=False)
    assignment_rbnode = class_attribute_rbnodes.find('assignment', target=lambda rbnode: rbnode.value == name)
    return assignment_rbnode.value if assignment_rbnode is not None else None


def find_dependencies(rbnodes):
    calculate_rbnodes = rbnodes('atomtrailers', value=is_simulation_calculate)
    return list(map(
        lambda rbnode: rbnode.call[0].value.to_python(),
        calculate_rbnodes,
        ))


def find_formula_function(class_rbnode):
    # TODO Match function parameters to be (self, simulation, period)
    return class_rbnode.find('def', name='function')


def find_parameters(rbnodes):
    legislation_at_rbnodes = rbnodes('atomtrailers', value=is_legislation_at)
    # TODO Handle periods and parameters spanned over multiple lines, like when using "P".
    return list(map(
        lambda rbnode: '.'.join(map(lambda node1: node1.value, rbnode[3:])),
        legislation_at_rbnodes,
        ))


def is_legislation_at(rbnodes):
    """Detects simulation.legislation_at(instant) calls."""
    return len(rbnodes) >= 3 and rbnodes[0].value == 'simulation' and rbnodes[1].value == 'legislation_at'


def is_simulation_calculate(rbnodes):
    """Detects simulation.calculate('variable_name', period) or simulation.compute('variable_name', period) calls."""
    return len(rbnodes) >= 3 and rbnodes[0].value == 'simulation' and rbnodes[1].value in ('calculate', 'compute')


def is_split_by_roles(rbnodes):
    """Detects self.split_by_roles(...) calls."""
    return len(rbnodes) >= 3 and rbnodes[0].value == 'self' and rbnodes[1].value == 'split_by_roles'


def is_sum_by_entity(rbnodes):
    """Detects self.is_sum_by_entity(...) calls."""
    return len(rbnodes) >= 3 and rbnodes[0].value == 'self' and rbnodes[1].value == 'sum_by_entity'


def is_cast_from_entity_to_roles(rbnodes):
    """Detects self.cast_from_entity_to_role(...) or self.cast_from_entity_to_roles(...) calls."""
    return len(rbnodes) >= 3 and rbnodes[0].value == 'self' and rbnodes[1].value.startswith('cast_from_entity_to_role')
