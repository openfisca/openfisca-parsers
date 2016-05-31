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


"""
Functions converting RedBaron nodes to OpenFisca AST nodes.

Vocabulary:
- rbnode: redbaron nodes
- ofnode: openfisca node
- pyvariable: python variable
- AST nodes are JSON-like objects describing OpenFisca elements, but in a higher-level fashion
    (no more columns for example)
"""


from toolz.curried import assoc, filter, map, pipe, take
import redbaron.nodes

from . import navigators


# Helpers


def singleton_or_none(iterable):
    values = list(iterable)
    return values[0] if values else None


# RedBaron nodes helpers


def is_significant_rbnode(rbnode):
    return not isinstance(rbnode, (redbaron.nodes.EndlNode, redbaron.nodes.CommaNode, redbaron.nodes.DotNode))


def to_unicode(string_or_unicode):
    """
    Fixes wrong unicode strings containing utf-8 bytes.
    Cf http://stackoverflow.com/questions/3182716/python-unicode-string-with-utf-8#comment43141617_14306718
    """
    if isinstance(string_or_unicode, str):
        string_or_unicode = string_or_unicode.decode('utf-8')
    else:
        assert isinstance(string_or_unicode, unicode), string_or_unicode
        string_or_unicode = string_or_unicode.encode('raw_unicode_escape').decode('utf-8')
    return string_or_unicode


# OpenFisca-Core names to OpenFisca AST names


def get_entity_name(entity_class_name):
    return {
        'Familles': 'famille',
        'FoyersFiscaux': 'foyer_fiscal',
        'Individus': 'individus',
        'Menages': 'menage',
        }[entity_class_name]


def get_variable_type(column_class_name):
    return {
        'FloatCol': 'float',
        'IntCol': 'int',
        }[column_class_name]


# OpenFisca AST node related helpers


ofnode_next_id = 0


def make_ofnode(ofnode, context):
    global ofnode_next_id
    ofnode = assoc(ofnode, 'id', ofnode_next_id)
    ofnode_next_id += 1
    context['ofnodes'].append(ofnode)
    return ofnode


# Visitors: rbnode -> ofnode


def visit_rbnode(rbnode, context):
    visitors = {
        function_name: function
        for function_name, function in globals().items()
        if function_name.startswith('visit_')
        }
    visitor = visitors.get('visit_' + rbnode.type)
    if visitor is None:
        raise Exception('Visitor not declared "def visit_{}(rbnode, context):", rbnode="{}"'.format(
            rbnode.type, rbnode))
    return visitor(rbnode, context)


def visit_atomtrailers(rbnode, context):
    def apply_rbnode_to_ofnode(ofnode, rbnode):
        """Return a new ofnode resulting from applying a rbnode to an ofnode."""
        if ofnode['type'] == 'Period':
            if rbnode.value in ('start', 'this_year'):
                return make_ofnode({
                    'operation': 'PeriodTransformation',
                    'rbnode': rbnode,
                    'target': ofnode,
                    'transformation': rbnode.value,
                    'type': 'Period',
                    }, context)
            else:
                raise Exception('unsupported')
        else:
            raise Exception('unsupported')

    if navigators.is_simulation_calculate_rbnodes(rbnode.value):
        variable_name = to_unicode(rbnode.call[0].value.to_python())
        period_pyvariable_name = rbnode.call[1].value.value
        variable_ofnode = pipe(
            context['ofnodes'],
            filter(lambda ofnode: ofnode['type'] == 'Variable' and ofnode['name'] == variable_name),
            take(1),
            singleton_or_none,
            )
        return make_ofnode({
            'operation': 'PeriodProjectionOnVariable',
            'period': context['ofnode_by_pyvariable_name'][period_pyvariable_name],
            'rbnode': rbnode,
            'type': 'Vector',
            'variable': variable_ofnode,
            }, context)
    elif navigators.is_legislation_at_rbnodes(rbnode.value):
        period_ofnode = visit_rbnode(rbnode.call[0].value, context)
        return make_ofnode({
            'operation': 'PeriodProjectionOnParameter',
            'parameter': 'TODO',
            'period': period_ofnode,
            'rbnode': rbnode,
            'type': 'ParameterValue',
            }, context)
    else:
        first_rbnode = rbnode.value[0]
        other_rbnodes = rbnode.value[1:]
        initial_ofnode = context['ofnode_by_pyvariable_name'][first_rbnode.value]
        ofnode = reduce(apply_rbnode_to_ofnode, other_rbnodes, initial_ofnode)
        return make_ofnode(ofnode, context)


def visit_class(rbnode, context):
    column_rbnode = navigators.find_class_attribute(rbnode, name='column')
    variable_type = get_variable_type(column_rbnode.name.value)
    default_value = navigators.find_column_default_value(column_rbnode)

    label_rbnode = navigators.find_class_attribute(rbnode, name='label')
    label = to_unicode(label_rbnode.to_python()) if label_rbnode is not None else None

    entity_rbnode = navigators.find_class_attribute(rbnode, name='entity_class')

    start_date_rbnode = navigators.find_class_attribute(rbnode, name='start_date')
    start_date = '-'.join(map(lambda rbnode: rbnode.value.value, start_date_rbnode.call.filtered())) \
        if start_date_rbnode is not None \
        else None

    stop_date_rbnode = navigators.find_class_attribute(rbnode, name='stop_date')
    stop_date = '-'.join(map(lambda rbnode: rbnode.value.value, stop_date_rbnode.call.filtered())) \
        if stop_date_rbnode is not None \
        else None

    def_rbnode = navigators.find_formula_function_rbnode(rbnode)
    formula_ofnode = visit_rbnode(def_rbnode, context) if def_rbnode is not None else None

    return make_ofnode({
        'default_value': default_value,
        'entity': get_entity_name(entity_rbnode.value),
        'formula': formula_ofnode,
        'label': label,
        'name': rbnode.name,
        'start_date': start_date,
        'stop_date': stop_date,
        'type': 'Variable',
        'variable_type': variable_type,
        }, context)


def visit_def(rbnode, context):
    body_rbnodes = rbnode.value.filter(is_significant_rbnode)
    # docstring_rbnode = body_rbnodes.find(('string', 'unicode_string'), recursive=False)
    # docstring = to_unicode(docstring_rbnode.to_python().strip()) if docstring_rbnode is not None else None
    ofnode_by_pyvariable_name = context['ofnode_by_pyvariable_name'] = {
        'period': make_ofnode({
            'name': 'period',
            'rbnode': rbnode,
            'type': 'Period',
            'unit': None,
            }, context)
        }
    for rbnode in body_rbnodes:
        if rbnode.type == 'string':
            print u'skip {}'.format(rbnode.type)
            print rbnode
            continue
        ofnode = visit_rbnode(rbnode.value, context)
        ofnode = assoc(ofnode, 'name', rbnode.target.value)
        ofnode_by_pyvariable_name[rbnode.target.value] = ofnode
    del context['ofnode_by_pyvariable_name']
    return ofnode
