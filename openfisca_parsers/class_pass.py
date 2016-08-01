
from toolz.curried import keyfilter

from .exceptions import my_assert, NotImplementedParsingError


def parse_date(atomtrailer, s):
    my_assert(atomtrailer.type == 'atomtrailers', atomtrailer, s)
    my_assert(len(atomtrailer.value) == 2, atomtrailer, s)
    my_assert(atomtrailer.value[0].type == 'name', atomtrailer, s)
    my_assert(atomtrailer.value[0].value == 'date', atomtrailer, s)
    call_node = atomtrailer.value[1]
    my_assert(call_node.type == 'call', atomtrailer, s)
    my_assert(len(call_node.value) == 3, atomtrailer, s)
    my_assert(call_node.value[0].type == 'call_argument', atomtrailer, s)
    my_assert(not call_node.value[0].target, atomtrailer, s)
    my_assert(call_node.value[0].value.type == 'int', atomtrailer, s)
    year = call_node.value[0].value.value
    my_assert(call_node.value[1].type == 'call_argument', atomtrailer, s)
    my_assert(not call_node.value[1].target, atomtrailer, s)
    my_assert(call_node.value[1].value.type == 'int', atomtrailer, s)
    month = call_node.value[1].value.value
    my_assert(call_node.value[2].type == 'call_argument', atomtrailer, s)
    my_assert(not call_node.value[2].target, atomtrailer, s)
    my_assert(call_node.value[2].value.type == 'int', atomtrailer, s)
    day = call_node.value[2].value.value

    return {'year': year, 'month': month, 'day': day}



def visit_class_rbnode(rbnode, s):
    visitors = keyfilter(lambda key: key.startswith('visit_class_'), globals()) # should be defined once
    visitor = visitors.get('visit_class_' + rbnode.type)
    if visitor is None:
        raise NotImplementedParsingError(
            'Class visitor not declared for type="{type}"'.format(
                type=rbnode.type,
                ), rbnode, s)
    ofnode = visitor(rbnode, s)
    return ofnode


def visit_class_endl(rbnode, s):
    return


def visit_class_assignment(rbnode, s):
    my_assert(rbnode.operator == '', rbnode, s)

    my_assert(rbnode.target.type == 'name', rbnode, s)
    target = rbnode.target.value

    if target == 'column':
        if rbnode.value.type == 'atomtrailers':
            my_assert(len(rbnode.value.value) == 2, rbnode, s)

            my_assert(rbnode.value.value[0].type == 'name', rbnode, s)
            column_name = rbnode.value.value[0].value

            call_node = rbnode.value.value[1]
            my_assert(call_node.type == 'call', rbnode, s)
            column_args = {}
            for arg in call_node.value:
                my_assert(arg.target.type == 'name', rbnode, s)
                column_args[arg.target.value] = arg.value

            my_assert('column' not in s['class_variables'].keys(), rbnode, s)
            s['class_variables']['column'] = column_name
            s['class_variables']['column_args'] = column_args

        elif rbnode.value.type == 'name':
            column_name = rbnode.value.value

            my_assert('column' not in s['class_variables'].keys(), rbnode, s)
            s['class_variables']['column'] = column_name
        else:
            raise NotImplementedParsingError('Unknown type', rbnode, s)

    elif target == 'entity_class':
        my_assert(rbnode.value.type == 'name', rbnode, s)

        my_assert('entity_class' not in s, rbnode, s)
        s['entity_class'] = rbnode.value.value

    elif target == 'label':
        # can be unicode_string or string_chain ! (TODO)
        # my_assert(rbnode.value.type == 'unicode_string', rbnode, s)

        my_assert('label' not in s, rbnode, s)
        s['label'] = rbnode.value

    elif target == 'start_date':
        date = parse_date(rbnode.value, s)

        my_assert('start_date' not in s, rbnode, s)
        s['start_date'] = date

    elif target == 'stop_date':
        date = parse_date(rbnode.value, s)

        my_assert('stop_date' not in s, rbnode, s)
        s['stop_date'] = date

    elif target == 'url':
        # can be a tuple, see revnet (TODO)
        # my_assert(rbnode.value.type in ['string', 'unicode_string'], rbnode, s)

        my_assert('url' not in s, rbnode, s)
        s['url'] = rbnode.value.value


    elif target == 'operation':
        my_assert(rbnode.value.type == 'string', rbnode, s)

        my_assert('operation' not in s, rbnode, s)
        s['operation'] = rbnode.value.value


    elif target == 'variable':
        my_assert(rbnode.value.type == 'name', rbnode, s)

        my_assert('variable' not in s, rbnode, s)
        s['variable'] = rbnode.value.value

    elif target == 'cerfa_field':
        # my_assert(rbnode.value.type == 'unicode_string', rbnode, s)
        # can be a unicode string or a dict

        my_assert('cerfa_field' not in s, rbnode, s)
        s['cerfa_field'] = rbnode.value

    elif target == 'is_permanent':
        my_assert(rbnode.value.type == 'name', rbnode, s)
        my_assert(rbnode.value.value in ['True', 'False'], rbnode, s)

        my_assert('is_permanent' not in s, rbnode, s)
        s['is_permanent'] = rbnode.value.value == 'True'

    elif target == 'base_function':
        my_assert(rbnode.value.type == 'name', rbnode, s)

        my_assert('base_function' not in s, rbnode, s)
        s['base_function'] = rbnode.value.value

    elif target == 'calculate_output':
        my_assert(rbnode.value.type == 'name', rbnode, s)

        my_assert('calculate_output' not in s, rbnode, s)
        s['calculate_output'] = rbnode.value.value

    elif target == 'set_input':
        my_assert(rbnode.value.type == 'name', rbnode, s)

        my_assert('set_input' not in s, rbnode, s)
        s['set_input'] = rbnode.value.value

    elif target == 'role':
        my_assert(rbnode.value.type == 'name', rbnode, s)

        my_assert('role' not in s, rbnode, s)
        s['role'] = rbnode.value.value


    else:
        raise NotImplementedParsingError('Unknown class variable {}'.format(target), rbnode, s)


def visit_class_def(rbnode, s):
    name = rbnode.name

    decorators = rbnode.decorators

    arguments = []
    for arg in rbnode.arguments:
        my_assert(arg.type == 'def_argument', rbnode, s)
        my_assert(arg.target.type == 'name', rbnode, s)
        arguments.append(arg.target.value)
        my_assert(not arg.value, rbnode, s)

    instructions = rbnode.value # unmodified (TODO)

    my_assert(name not in s['class_functions'], rbnode, s)
    s['class_functions'][name] = {
        'arguments': arguments,
        'decorators': decorators,
        'instructions': instructions,
    }


def visit_class_comment(rbnode, s):
    # ignored (TODO)
    return


def visit_class_string(rbnode, s):
    # ignored (TODO)
    return


def parse(parsed_modules):
    parsed_classes = {}

    for module_name, module in parsed_modules.items():
        # print('Visiting module {} to parse its classes.'.format(module_name))

        parsed_classes[module_name] = {
            'parsed_classes': {},
        }

        for cl in module['classes']:
            class_name = cl['name']
            # print('Visiting class {}'.format(class_name))

            s = {
                'keyword': 'class',
                'class_name': class_name,
                'class_variables': {},
                'class_functions': {},
                }

            for rbnode in cl['content']:
                visit_class_rbnode(rbnode, s)

            parsed_classes[module_name]['parsed_classes'][class_name] = {
                'class_variables': s['class_variables'],
                'class_functions': s['class_functions'],
                }

    return parsed_classes
