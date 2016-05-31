#! /usr/bin/env python
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


"""Convert Python formulas to JSON using RedBaron."""


import argparse
import json
import logging
import sys
import pkg_resources

from redbaron import RedBaron
from toolz.curried import assoc, filter, map, pipe, take
from toolz.curried.operator import attrgetter
import redbaron.nodes


# Vocabulary:
# - rbnode: redbaron nodes
# - ofnode: openfisca node
# - pyvariable: python variable
# - AST nodes are JSON-like objects describing OpenFisca elements, but in a higher-level fashion
#   (no more columns for example)


# Helpers


def is_significant_rbnode(rbnode):
    return not isinstance(rbnode, (redbaron.nodes.EndlNode, redbaron.nodes.CommaNode, redbaron.nodes.DotNode))


def show_json(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8'))


def singleton_or_none(iterable):
    values = list(iterable)
    return values[0] if values else None


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


# OpenFisca names to AST names


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


# RedBaron Node navigation functions


def find_all_variable_class(rbnode):
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


# Context helpers

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
        raise Exception('Visitor not declared (def visit_{}(rbnode, context):), rbnode={}'.format(rbnode.type, rbnode))
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

    if is_simulation_calculate_rbnodes(rbnode.value):
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
    elif is_legislation_at_rbnodes(rbnode.value):
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
    column_rbnode = find_class_attribute(rbnode, name='column')
    variable_type = get_variable_type(column_rbnode.name.value)
    default_value = find_column_default_value(column_rbnode)

    label_rbnode = find_class_attribute(rbnode, name='label')
    label = to_unicode(label_rbnode.to_python()) if label_rbnode is not None else None

    entity_rbnode = find_class_attribute(rbnode, name='entity_class')

    start_date_rbnode = find_class_attribute(rbnode, name='start_date')
    start_date = '-'.join(map(lambda rbnode: rbnode.value.value, start_date_rbnode.call.filtered())) \
        if start_date_rbnode is not None \
        else None

    stop_date_rbnode = find_class_attribute(rbnode, name='stop_date')
    stop_date = '-'.join(map(lambda rbnode: rbnode.value.value, stop_date_rbnode.call.filtered())) \
        if stop_date_rbnode is not None \
        else None

    def_rbnode = find_formula_function_rbnode(rbnode)
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
        # assert rbnode.type == 'assignment', rbnode
        if rbnode.type != 'assignment':
            print u'skip {}'.format(rbnode.type)
            print rbnode
            continue
        ofnode = visit_rbnode(rbnode.value, context)
        ofnode = assoc(ofnode, 'name', rbnode.target.value)
        ofnode_by_pyvariable_name[rbnode.target.value] = ofnode
    del context['ofnode_by_pyvariable_name']
    return ofnode


# Parsing functions


def parse_string(source_code):
    red = RedBaron(source_code)

    # Parse all `Variable` instances with a `function`
    variable_class_rbnodes = find_all_variable_class(red)
    # print(variable_class_rbnodes.help())
    context = {'ofnodes': []}
    ofnodes = [visit_rbnode(rbnode, context) for rbnode in variable_class_rbnodes]
    context['ofnodes'].extend(ofnodes)
    return ofnodes


# Main function for script


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # parser.add_argument('file_path', help=u'path of the file to parse')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="increase output verbosity")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, stream=sys.stdout)

    openfisca_france_location = pkg_resources.get_distribution('OpenFisca-France').location
    source_file_path = '{}/openfisca_france/model/prelevements_obligatoires/isf.py'.format(openfisca_france_location)
    with open(source_file_path) as source_file:
        source_code = source_file.read()

    # It seems that RedBaron expects an utf-8 string, not an unicode string.
    # source_code = source_code.decode('utf-8')
    # print(type(source_code))

    ofnodes = parse_string(source_code)
    show_json(ofnodes)

    return 0


if __name__ == "__main__":
    sys.exit(main())
