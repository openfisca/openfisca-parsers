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

ofnodes are JSON-like data structures describing OpenFisca elements,
but replace some OpenFisca-Core specific vocabulary by more generic (no more columns for example).

ofnodes have this shape: {'type': 'CamelCase'}. The other fields depend on the 'type' field.
"""


from toolz.curried import filter, keyfilter, map, merge
from toolz.curried.operator import attrgetter
import redbaron.nodes

from . import navigators, shortid


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


# OpenFisca AST nodes related helpers


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


def find_variable_by_name(ofnodes, name):
    """
    Return the ofnode corresponding to a Variable ofnode of given name or None if not found.
    Raises if more than 1 result.
    """
    matching_ofnodes = list(filter(
        lambda ofnode: ofnode['type'] == 'Variable' and ofnode['name'] == name,
        ofnodes,
        ))
    assert len(matching_ofnodes) <= 1, (name, matching_ofnodes)
    return matching_ofnodes or None


def make_ofnode(ofnode, rbnode, context, with_rbnodes=False):
    """Create and return a new ofnode. The ofnode is also added to the list of nodes in the context."""
    id = shortid.generate()
    ofnode = merge(ofnode, {'id': id})
    if with_rbnodes:
        ofnode = merge(ofnode, {'rbnode': rbnode})
    context['ofnodes'].append(ofnode)
    return ofnode


# Generic visitor: rbnode -> ofnode. All specific visitors must call it to concentrate flow (ie log calls).


def visit_rbnode(rbnode, context):
    visitors = keyfilter(lambda key: key.startswith('visit_'), globals())
    visitor = visitors.get('visit_' + rbnode.type)
    if visitor is None:
        raise Exception(u'Visitor not declared for type="{type}", source="{source}"\n{stub}'.format(
            source=rbnode,
            stub=u'''\
def visit_{}(rbnode, context):
    rbnode.help()
    import ipdb; ipdb.set_trace()
    return make_ofnode({{
        'type': '',
        }}, rbnode, context)
'''.format(rbnode.type),
            type=rbnode.type,
            ))
    return visitor(rbnode, context)


# Specific visitors: rbnode -> ofnode


def visit_binary_operator(rbnode, context):
    return make_ofnode({
        'name': rbnode.value,
        'operands': [
            visit_rbnode(rbnode.first, context),
            visit_rbnode(rbnode.second, context),
            ],
        'type': 'Operator',
        }, rbnode, context)


def visit_associative_parenthesis(rbnode, context):
    """Just forward to child node."""
    return visit_rbnode(rbnode.value, context)


def visit_atomtrailers(rbnode, context):
    def apply_rbnode_to_ofnode(ofnode, rbnode):
        """Return a new ofnode resulting from applying a rbnode to an ofnode."""
        if ofnode['type'] == 'Period':
            if rbnode.value in ('start', 'this_year'):
                return make_ofnode({
                    'operation': 'PeriodTransformation',
                    'target': ofnode,
                    'transformation': rbnode.value,
                    'type': 'Period',
                    }, rbnode, context)
            else:
                raise NotImplementedError(rbnode)
        elif ofnode['type'] == 'Parameter':
            # Patch existing Parameter ofnode because parameter path fragments are not considered
            # OpenFisca AST operations.
            parameter_path_fragment = rbnode.value
            ofnode['path'].append(parameter_path_fragment)
            return ofnode
        elif ofnode['type'] == 'ParameterAtInstant':
            return apply_rbnode_to_ofnode(ofnode['parameter'], rbnode)
        else:
            raise NotImplementedError(ofnode)

    if navigators.is_simulation_calculate_rbnodes(rbnode.value):
        variable_name = to_unicode(rbnode.call[0].value.to_python())
        period_pyvariable_name = rbnode.call[1].value.value
        variable_ofnode = find_variable_by_name(context['ofnodes'], variable_name)
        if variable_ofnode is None:
            # Create a Variable ofnode stub which will be completed when the real Variable class will be parsed.
            variable_ofnode = make_ofnode({
                'name': variable_name,
                'type': 'Variable',
                }, rbnode, context)
        return make_ofnode({
            'period': context['ofnode_by_pyvariable_name'][period_pyvariable_name],
            'type': 'VariableForPeriod',
            'variable': variable_ofnode,
            }, rbnode, context)
    elif navigators.is_legislation_at_rbnodes(rbnode.value):
        period_ofnode = visit_rbnode(rbnode.call[0].value, context)
        parameter_path_rbnodes = rbnode[rbnode.call.index_on_parent + 1:]
        parameter_path_fragments = list(map(attrgetter('value'), parameter_path_rbnodes))
        parameter_ofnode = find_parameter_by_path_fragments(context['ofnodes'], parameter_path_fragments)
        if parameter_ofnode is None:
            parameter_ofnode = make_ofnode({
                'path': parameter_path_fragments,
                'type': 'Parameter',
                }, rbnode, context)
        return make_ofnode({
            'parameter': parameter_ofnode,
            'period': period_ofnode,
            'type': 'ParameterAtInstant',
            }, rbnode, context)
    else:
        # Atomtrailers is a generic Python expression (a.b.c, a[0].b(1 + 2), etc.).
        # The first rbnode must be an existing variable in the local context of the function.
        first_rbnode = rbnode.value[0]
        assert first_rbnode.type == 'name', first_rbnode
        name_ofnode = visit_rbnode(first_rbnode, context)
        if first_rbnode.value in context['ofnode_by_pyvariable_name']:
            other_rbnodes = rbnode.value[1:]
            ofnode = reduce(apply_rbnode_to_ofnode, other_rbnodes, name_ofnode)
            return ofnode
        else:
            call_arguments_rbnodes = rbnode.call.value
            # visit_name returned a stub.
            ofnode = name_ofnode
            ofnode['operands'] = [
                visit_rbnode(call_argument_rbnode.value, context)
                for call_argument_rbnode in call_arguments_rbnodes
                ]
            return ofnode


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
    formula_dict = {}
    if def_rbnode is not None:
        formula_dict = visit_rbnode(def_rbnode, context)

    return make_ofnode({
        'default_value': default_value,
        'docstring': formula_dict.get('docstring'),
        'entity': get_entity_name(entity_rbnode.value),
        'formula': formula_dict.get('formula_ofnode'),
        'label': label,
        'name': rbnode.name,
        'output_period': formula_dict.get('output_period_ofnode'),
        'start_date': start_date,
        'stop_date': stop_date,
        'type': 'Variable',
        'variable_type': variable_type,
        }, rbnode, context)


def visit_def(rbnode, context):
    body_rbnodes = rbnode.value.filter(is_significant_rbnode)
    docstring_rbnode = body_rbnodes.find(('string', 'unicode_string'), recursive=False)
    docstring = to_unicode(docstring_rbnode.to_python().strip()) if docstring_rbnode is not None else None
    context['ofnode_by_pyvariable_name'] = {
        'period': make_ofnode({
            'name': 'period',
            'type': 'Period',
            'unit': None,
            }, rbnode, context)
        }
    output_period_ofnode = formula_ofnode = None
    for index, rbnode in enumerate(body_rbnodes):
        if rbnode.type in ('comment', 'string'):
            continue
        elif rbnode.type == 'assignment':
            ofnode = visit_rbnode(rbnode.value, context)
            context['ofnode_by_pyvariable_name'][rbnode.target.value] = ofnode
        elif rbnode.type == 'return':
            # assert index == len(body_rbnodes) - 1, u'return is not the last function statement'
            output_period_ofnode, formula_ofnode = visit_rbnode(rbnode.value, context)
        else:
            raise NotImplementedError((rbnode.type, rbnode))
    del context['ofnode_by_pyvariable_name']
    # Just return extracted data, not an ofnode.
    return {
        'docstring': docstring,
        'formula_ofnode': formula_ofnode,
        'output_period_ofnode': output_period_ofnode,
        }


def visit_int(rbnode, context):
    return make_ofnode({
        'type': 'Int',
        'value': rbnode.to_python(),
        }, rbnode, context)


def visit_name(rbnode, context):
    name = rbnode.value
    if name in context['ofnode_by_pyvariable_name']:
        # name is a local variable of the function.
        return context['ofnode_by_pyvariable_name'][name]
    else:
        # name is a function, imported or builtin.
        # Just return a stub of Operator ofnode, which will be completed by visit_atomtrailers
        # who has access to CallArguments rbnodes.
        return make_ofnode({
            'name': name,
            'operands': None,
            'type': 'Operator',
            }, rbnode, context)


def visit_tuple(rbnode, context):
    ofnodes = [
        visit_rbnode(rbnode1, context)
        for rbnode1 in rbnode.value
        ]
    return ofnodes
