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


from toolz.curried import assoc, concatv, keyfilter, map
from toolz.curried.operator import attrgetter
import redbaron.nodes

from . import ofnodes as ofn, rbnodes as rbn
from .contexts import LOCAL, VARIABLES


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


# Generic visitor: rbnode, context -> ofnode | dict
# All specific visitors must call it to concentrate flow (ie log calls).


def visit_rbnode(rbnode, context):
    visitors = keyfilter(lambda key: key.startswith('visit_'), globals())
    visitor = visitors.get('visit_' + rbnode.type)
    if visitor is None:
        raise NotImplementedError(u'Visitor not declared for type="{type}", source="{source}"\n{template}'.format(
            source=rbnode,
            template=u'''\
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
    return ofn.make_ofnode({
        'type': 'ArithmeticOperator',
        'operator': rbnode.value,
        'operands': [
            visit_rbnode(rbnode.first, context),
            visit_rbnode(rbnode.second, context),
            ],
        }, rbnode, context)


def visit_assignment(rbnode, context):
    """Just forward to right hand side node."""
    return visit_rbnode(rbnode.value, context)


def visit_associative_parenthesis(rbnode, context):
    """Just forward to inner node."""
    return visit_rbnode(rbnode.value, context)


def visit_atomtrailers(rbnode, context):
    # Atomtrailers is a generic Python expression (a.b.c, a[0].b(1 + 2), etc.).

    def apply_rbnode_to_ofnode(ofnode, rbnode):
        """Return a new ofnode resulting from applying a rbnode to an ofnode."""
        if ofnode['type'] in ('Period', 'PeriodOperator'):
            if rbnode.value in ('start', 'this_year'):
                return ofn.make_ofnode({
                    'type': 'PeriodOperator',
                    'operator': rbnode.value,
                    'operand': ofnode,
                    }, rbnode, context)
            else:
                raise NotImplementedError(rbnode)
        elif ofnode['type'] == 'Parameter':
            parameter_path_fragment = rbnode.value
            return ofn.make_ofnode(
                assoc(ofnode, 'path', list(concatv(ofnode['path'], [parameter_path_fragment]))),
                rbnode,
                context,
                )
        elif ofnode['type'] == 'ParameterAtInstant':
            new_parameter_ofnode = apply_rbnode_to_ofnode(ofnode['parameter'], rbnode)
            return ofn.make_ofnode(assoc(ofnode, 'parameter', new_parameter_ofnode), rbnode, context)
        else:
            raise NotImplementedError(ofnode)

    if rbn.is_simulation_calculate(rbnode.value):
        variable_name = to_unicode(rbnode.call[0].value.to_python())
        period_pyvariable_name = rbnode.call[1].value.value
        variable_ofnode = ofn.find_variable_by_name(context[VARIABLES], variable_name)
        if variable_ofnode is None:
            # Create a stub which will be completed when the real Variable class will be parsed.
            variable_ofnode = ofn.make_ofnode({
                '_stub': True,
                'type': 'Variable',
                'name': variable_name,
                }, rbnode, context)
        return ofn.make_ofnode({
            'type': 'VariableForPeriod',
            'period': context[LOCAL][period_pyvariable_name],
            'variable': variable_ofnode,
            }, rbnode, context)
    elif rbn.is_legislation_at(rbnode.value):
        period_ofnode = visit_rbnode(rbnode.call[0].value, context)
        parameter_path_rbnodes = rbnode[rbnode.call.index_on_parent + 1:]
        parameter_path_fragments = list(map(attrgetter('value'), parameter_path_rbnodes)) or None
        parameter_ofnode = ofn.find_parameter_by_path_fragments(context[VARIABLES], parameter_path_fragments)
        if parameter_ofnode is None:
            parameter_ofnode = ofn.make_ofnode({
                'type': 'Parameter',
                'path': parameter_path_fragments,
                }, rbnode, context)
        return ofn.make_ofnode({
            'type': 'ParameterAtInstant',
            'parameter': parameter_ofnode,
            'instant': period_ofnode,
            }, rbnode, context)
    else:
        # The first rbnode must be an existing variable in the local context of the function.
        first_rbnode = rbnode.value[0]
        assert first_rbnode.type == 'name', first_rbnode
        name_ofnode = visit_rbnode(first_rbnode, context)
        if first_rbnode.value in context[LOCAL]:
            # first_rbnode is a local variable of the function.
            other_rbnodes = rbnode.value[1:]
            ofnode = reduce(apply_rbnode_to_ofnode, other_rbnodes, name_ofnode)
            return ofnode
        else:
            # first_rbnode is a function, imported or builtin.
            # TODO Could be other things like a Python module.
            assert rbnode[1].type == 'call', rbnode
            call_arguments_rbnodes = rbnode.call.value
            # name_ofnode is a stub which was created by visit_name.
            assert name_ofnode['type'] == 'ArithmeticOperator', name_ofnode
            operands_ofnodes = [
                visit_rbnode(call_argument_rbnode.value, context)
                for call_argument_rbnode in call_arguments_rbnodes
                ]
            ofn.update_ofnode_stub(name_ofnode, merge={'operands': operands_ofnodes})
            # TODO Handle ".x" in f().x.
            rbnodes_after_call = rbnode[rbnode.call.index_on_parent + 1:]
            assert len(rbnodes_after_call) == 0, rbnodes_after_call
            return name_ofnode


def visit_class(rbnode, context):
    column_rbnode = rbn.find_class_attribute(rbnode, name='column')
    variable_type = get_variable_type(column_rbnode.name.value)
    default_value = rbn.find_column_default_value(column_rbnode)

    label_rbnode = rbn.find_class_attribute(rbnode, name='label')
    label = to_unicode(label_rbnode.to_python()) if label_rbnode is not None else None

    entity_rbnode = rbn.find_class_attribute(rbnode, name='entity_class')

    start_date_rbnode = rbn.find_class_attribute(rbnode, name='start_date')
    start_date = '-'.join(map(lambda rbnode: rbnode.value.value, start_date_rbnode.call.filtered())) \
        if start_date_rbnode is not None \
        else None

    stop_date_rbnode = rbn.find_class_attribute(rbnode, name='stop_date')
    stop_date = '-'.join(map(lambda rbnode: rbnode.value.value, stop_date_rbnode.call.filtered())) \
        if stop_date_rbnode is not None \
        else None

    def_rbnode = rbn.find_formula_function(rbnode)
    formula_dict = {}
    if def_rbnode is not None:
        formula_dict = visit_rbnode(def_rbnode, context)

    variable_name = rbnode.name

    ofnode_dict = {
        'type': 'Variable',
        'default_value': default_value,
        'docstring': formula_dict.get('docstring'),
        'entity': get_entity_name(entity_rbnode.value),
        'formula': formula_dict.get('formula_ofnode'),
        'label': label,
        'name': variable_name,
        'output_period': formula_dict.get('output_period_ofnode'),
        'start_date': start_date,
        'stop_date': stop_date,
        'variable_type': variable_type,
        }

    variable_ofnode = ofn.find_variable_by_name(context[VARIABLES], variable_name)
    if variable_ofnode is None:
        variable_ofnode = ofn.make_ofnode(ofnode_dict, rbnode, context)
        context[VARIABLES].append(variable_ofnode)
        return variable_ofnode
    else:
        # variable_ofnode is a stub which was created by visit_atomtrailers.
        ofn.update_ofnode_stub(variable_ofnode, merge=ofnode_dict)
        return variable_ofnode


def visit_comparison(rbnode, context):
    return ofn.make_ofnode({
        'type': 'ArithmeticOperator',
        'operator': rbnode.value.first,
        'operands': [
            visit_rbnode(rbnode.first, context),
            visit_rbnode(rbnode.second, context),
            ],
        }, rbnode, context)


def visit_def(rbnode, context):
    body_rbnodes = rbnode.value.filter(is_significant_rbnode)
    docstring_rbnode = body_rbnodes.find(('string', 'unicode_string'), recursive=False)
    docstring = to_unicode(docstring_rbnode.to_python().strip()) if docstring_rbnode is not None else None
    context[LOCAL] = {
        'period': ofn.make_ofnode({'type': 'Period'}, rbnode, context)
        }
    output_period_ofnode = formula_ofnode = None
    for index, rbnode in enumerate(body_rbnodes):
        if rbnode.type in ('comment', 'string'):
            continue
        elif rbnode.type == 'assignment':
            ofnode = visit_rbnode(rbnode, context)
            context[LOCAL][rbnode.target.value] = ofnode
        elif rbnode.type == 'return':
            # TODO Ensure there is no forgotten nodes after return.
            # assert index == len(body_rbnodes) - 1, u'return is not the last function statement'
            output_period_ofnode, formula_ofnode = visit_rbnode(rbnode.value, context)
        else:
            raise NotImplementedError((rbnode.type, rbnode))
    del context[LOCAL]
    # Just return extracted data, not an ofnode.
    return {
        'docstring': docstring,
        'formula_ofnode': formula_ofnode,
        'output_period_ofnode': output_period_ofnode,
        }


def visit_int(rbnode, context):
    return ofn.make_ofnode({
        'type': 'Number',
        'value': rbnode.to_python(),
        }, rbnode, context)


def visit_name(rbnode, context):
    name = rbnode.value
    if name in context[LOCAL]:
        # name is a local variable of the function.
        return context[LOCAL][name]
    else:
        # name is a function, imported or builtin.
        # TODO name could be another thing, like a Python module.
        # Create a stub which will be completed by visit_atomtrailers when parsing function call arguments.
        return ofn.make_ofnode({
            '_stub': True,
            'type': 'ArithmeticOperator',
            'operator': name,
            'operands': None,
            }, rbnode, context)


def visit_tuple(rbnode, context):
    ofnodes = [
        visit_rbnode(rbnode1, context)
        for rbnode1 in rbnode.value
        ]
    return ofnodes