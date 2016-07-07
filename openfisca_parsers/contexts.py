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


"""Functions to manage context used in RedBaron nodes visitors."""


from toolz.curried import merge


# Contextual to whole file parsing.
FILE = 'current_source_file_path'

# Contextual to visit_def.
LOCAL_PYVARIABLES = 'ofnode_by_local_pyvariable_name'
LOCAL_SPLIT_BY_ROLES = 'split_by_role_infos_by_pyvariable_name'

# Global to tax and benefit system.
PARAMETERS = 'ofnode_by_parameter_path'
WITH_PYVARIABLES = 'add_pyvariables_to_variable_ofnodes'


def create(initial_context={}):
    return merge(
        {
            PARAMETERS: {},
            },
        initial_context,
        )
