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


from toolz.curried import assoc, filter, valfilter


def find_parameter_by_path_fragments(ofnodes, path_fragments):
    """
    Return the ofnode corresponding to a Parameter ofnode of given path_fragments or None if not found.
    Raises if more than 1 result.
    """
    matching_ofnodes = list(filter(
        lambda ofnode: ofnode['type'] == 'Parameter' and ofnode['path'] == path_fragments,
        ofnodes,
        ))
    assert len(matching_ofnodes) <= 1, (path_fragments, matching_ofnodes)
    return matching_ofnodes or None


def make_ofnode(items, rbnode, context, with_rbnode=False):
    """
    Create and return a new ofnode.
    with_rbnode: if True, reference the rbnode from the '_rbnode' key in the ofnode.
    """
    id = context['generate_shortid']()
    ofnode = assoc(items, 'id', id)
    if with_rbnode:
        ofnode = assoc(ofnode, '_rbnode', rbnode)
    return valfilter(lambda value: value is not None, ofnode)


def update_ofnode_stub(ofnode, merge):
    assert '_stub' in ofnode, ofnode
    ofnode.update(valfilter(lambda value: value is not None, merge))
    del ofnode['_stub']
    return ofnode
