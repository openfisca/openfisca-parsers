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


"""Functions to access OpenFisca-Core and OpenFisca-France data."""


from toolz.curried import get

from openfisca_france.model import base


def get_all_roles(entity_name):
    enum_by_entity_name = {
        'famille': base.QUIFAM,
        'foyer_fiscal': base.QUIFOY,
        'menage': base.QUIMEN,
        }
    enum = enum_by_entity_name[entity_name]
    all_roles = list(map(get(0), enum.itervars()))
    return all_roles


def get_entity_name(entity_class_name):
    return {
        'Familles': 'famille',
        'FoyersFiscaux': 'foyer_fiscal',
        'Individus': 'individus',
        'Menages': 'menage',
        }[entity_class_name]


def get_variable_type(column_class_name):
    variable_type = {
        'FloatCol': 'float',
        'IntCol': 'int',
        }.get(column_class_name)
    assert variable_type is not None
    return variable_type
