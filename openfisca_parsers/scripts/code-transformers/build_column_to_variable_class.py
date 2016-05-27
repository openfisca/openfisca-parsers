#! /usr/bin/env python
# -*- coding: utf-8 -*-


"""
Transform build_column function calls to Variables.

Launch with:

    grep -R -l 'build_column(' ~/Dev/openfisca/openfisca-france | \
        xargs python openfisca_parsers/scripts/build_column_to_variable_class.py

or, for one file at a time (with fish shell):

    for file in (grep -R -l 'build_column(' ~/Dev/openfisca/openfisca-france)
        python openfisca_parsers/scripts/build_column_to_variable_class.py $file
    end

Note: once there is no more build_column function calls in OpenFisca-France, this script is no more useful.
Or perhaps it's useful to external code which would still use build_column and would want to convert them.
"""


import argparse
import sys

from redflyingbaron import RedFlyingBaron


# Helpers

def generate_class_attribute_source(column_name, column_kwarg_by_name):
    if not column_kwarg_by_name:
        return column_name
    if len(column_kwarg_by_name) == 1:
        kwarg_name, kwarg_value = column_kwarg_by_name.items()[0]
        kwarg_value = unicode(kwarg_value)
        if len(kwarg_value.split('\n')) == 1:
            return u'{}({})'.format(
                column_name,
                u'{} = {}'.format(kwarg_name, kwarg_value),
                )
    class_attribute_source = u'{}(\n{}\n    )'.format(
        column_name,
        '\n'.join(
            u'    {} = {},'.format(
                kwarg_name,
                indent(unicode(kwarg_value), prefix=' ' * 4, skip=1),
                )
            for kwarg_name, kwarg_value in sorted(column_kwarg_by_name.items())
            ),
        )
    return class_attribute_source


def indent(text, prefix=' ' * 4, skip=0):
    lines = text.split('\n')
    assert skip <= len(lines), (skip, len(lines))
    return '\n'.join(lines[:skip] + [prefix + line for line in lines[skip:]])


def nice_repr(node, empty_strings_to_none=False):
    '''Bypass builtin repr function which escapes unicode characters, which is ugly in source code files.'''
    if node.type in ('atomtrailers', 'dict'):
        source = str(node).decode('utf-8')
        lines = [line.strip() for line in source.split('\n')]
        lines[1:] = [' ' * 4 + line for line in lines[1:]]
        return '\n'.join(lines)
    elif node.type == 'int':
        return node.to_python()
    elif node.type == 'name':
        return node.value
    elif node.type in ('string', 'unicode_string'):
        result = to_fixed_unicode(node.to_python())
        if not result:
            return None
        result = u'"{}"'.format(result)
        if node.type == 'unicode_string':
            result = 'u' + result
        return result
    raise ValueError('Unknown node type: {} for "{}"'.format(node.type, unicode(node)))


def to_fixed_unicode(string_or_unicode):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_files', nargs='+', help='Python source file to convert')
    args = parser.parse_args()

    red = RedFlyingBaron.from_paths(args.source_files, verbose=True)

    build_column_nodes = red('atomtrailers', value=lambda node: node.name.value == 'build_column')

    entity_class_str_by_symbol = {
        'fam': 'Familles',
        'foy': 'FoyersFiscaux',
        'ind': 'Individus',
        'men': 'Menages',
        }

    for build_column_node in build_column_nodes:
        variable_name = build_column_node.call[0].value.to_python()
        column_node = build_column_node.call[1].value
        column_name = column_node.name.value
        column_args_nodes = column_node[1].value
        # For column arguments transformed into Variable class attributes.
        class_attribute_by_name = {
            'entity_class': 'Individus',
            }
        column_kwarg_by_name = {}  # For column arguments kept as column arguments.
        for column_arg_node in column_args_nodes:
            assert column_arg_node.target is not None, 'Expected kwargs only. Node: "{}"'.format(str(column_arg_node))
            column_arg_name = column_arg_node.target.value
            column_arg_value_node = column_arg_node.value
            if column_arg_name in ('default', 'enum', 'max_length', 'val_type'):
                column_kwarg_by_name[column_arg_name] = nice_repr(column_arg_value_node)
            elif column_arg_name in ('cerfa_field', 'is_permanent', 'label'):
                class_attribute_by_name[column_arg_name] = nice_repr(column_arg_value_node, empty_strings_to_none=True)
            elif column_arg_name == 'entity':
                class_attribute_by_name['entity_class'] = entity_class_str_by_symbol[column_arg_value_node.to_python()]
            elif column_arg_name == 'start':
                class_attribute_by_name['start_date'] = unicode(column_arg_value_node)
            elif column_arg_name == 'end':
                class_attribute_by_name['stop_date'] = unicode(column_arg_value_node)
            else:
                raise ValueError('Unknown column_arg_name: {} for variable "{}"'.format(column_arg_name, variable_name))

        class_attribute_by_name['column'] = generate_class_attribute_source(column_name, column_kwarg_by_name)
        class_source_code = u'class {variable_name}(Variable):\n{attributes}\n\n'.format(
            attributes='\n'.join(
                u'    {} = {}'.format(
                    attribute_name,
                    indent(attribute_value, prefix=' ' * 4, skip=1),
                    )
                for attribute_name, attribute_value in sorted(class_attribute_by_name.items())
                if attribute_value
                ),
            variable_name=variable_name,
            )
        build_column_node.replace(class_source_code.encode('utf-8'))

    red.save()

    return 0


if __name__ == '__main__':
    sys.exit(main())
