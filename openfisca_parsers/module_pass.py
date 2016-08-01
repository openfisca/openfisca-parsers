from toolz.curried import keyfilter

from .exceptions import my_assert, NotImplementedParsingError




def parse_enum(atomtrailers, s):
    my_assert(atomtrailers.type == 'atomtrailers', atomtrailers, s)

    my_assert(len(atomtrailers.value) == 2, atomtrailers, s)
    my_assert(atomtrailers.value[0].type == 'name', atomtrailers, s)
    my_assert(atomtrailers.value[0].value == 'Enum', atomtrailers, s)

    call_node = atomtrailers.value[1]
    my_assert(call_node.type == 'call', atomtrailers, s)
    my_assert(len(call_node.value) == 1, atomtrailers, s)
    my_assert(call_node.value[0].type == 'call_argument', atomtrailers, s)
    my_assert(not call_node.value[0].target, atomtrailers, s)

    enum_list_node = call_node.value[0].value
    my_assert(enum_list_node.type == 'list', atomtrailers, s)

    enum_list = []
    for element in enum_list_node.value:
        my_assert(element.type == 'unicode_string', atomtrailers, s)
        enum_list.append(element.value)

    return enum_list




def visit_module_rbnode(rbnode, s):
    visitors = keyfilter(lambda key: key.startswith('visit_module_'), globals()) # should be defined once
    visitor = visitors.get('visit_module_' + rbnode.type)
    if visitor is None:
        raise NotImplementedParsingError(
            'Module visitor not declared for type="{type}"'.format(
                type=rbnode.type,
                ), rbnode, s)
    ofnode = visitor(rbnode, s)
    return ofnode


def visit_module_endl(rbnode, s):
    return


def visit_module_from_import(rbnode, s):
    # unmodified (TODO)
    s['imports'].append(rbnode)


def visit_module_import(rbnode, s):
    # unmodified (TODO)
    s['imports'].append(rbnode)


def visit_module_comment(rbnode, s):
    # comments are discarded for the moment (TODO)
    return


def visit_module_class(rbnode, s):
    name = rbnode.name

    if name == 'rsa_ressource_calculator':
        return

    my_assert(not rbnode.decorators, rbnode, s)

    upper_classes = []
    for upper_class in rbnode.inherit_from:
        my_assert(upper_class.type == 'name', rbnode, s)
        upper_classes.append(upper_class.value)

    class_obj = {
        'type': 'class',
        'name': name,
        'upper_classes': upper_classes,
        'content': rbnode.value,
        }

    s['classes'].append(class_obj)


def visit_module_def(rbnode, s):
    if rbnode.name in ['_revprim', 'preload_zone_apl']:
        return

    # unmodified (TODO)
    s['auxiliary_functions'][rbnode.name] = rbnode


def visit_module_assignment(rbnode, s):
    my_assert(rbnode.operator == '', rbnode, s)

    my_assert(rbnode.target.type == 'name', rbnode, s)
    name = rbnode.target.value

    if name in ['zone_apl_by_depcom']:
        return

    if rbnode.value.type == 'int':
        s['constants'].append({
                'name': name,
                'type': 'int',
                'value': rbnode.value.value,
            })
        return

    if rbnode.value.type == 'name':
        my_assert(rbnode.value.value == 'None', rbnode, s)
        s['constants'].append({
                'name': name,
                'type': 'None',
                'value': None,
            })
        return

    if rbnode.value.type == 'atomtrailers':
        atomtrailers = rbnode.value

        my_assert(atomtrailers.value[0].type == 'name', rbnode, s)
        function_name = atomtrailers.value[0].value
        if function_name == 'Enum':
            enum_list = parse_enum(atomtrailers, s)

            s['enums'].append({
                'name': name,
                'enum_list': enum_list,
            })
            return

        if function_name == 'logging':
            # ignore logging
            return

        raise NotImplementedParsingError('Unknown atomtrailers', rbnode, s)

    raise NotImplementedParsingError('Unknown type', rbnode, s)


def parse(redbaron_trees):
    parsed_modules = {}

    for name, red in redbaron_trees.items():
        # print('Visiting ' + name)

        s = {
            'module_name': name,
            'imports': [],
            'classes': [],
            'enums': [],
            'auxiliary_functions': {},
            'constants': [],
            }

        for rbnode in red:
            visit_module_rbnode(rbnode, s)

        parsed_modules[name] = {
            'imports': s['imports'],
            'classes': s['classes'],
            'enums': s['enums'],
            'auxiliary_functions': s['auxiliary_functions'],
            'constants': s['constants'],
        }

    return parsed_modules
