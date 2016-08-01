

from toolz.curried import keyfilter


from .exceptions import my_assert, NotImplementedParsingError


def visit_function_rbnode(rbnode, s):
    visitors = keyfilter(lambda key: key.startswith('visit_function_'), globals()) # should be defined once
    visitor = visitors.get('visit_function_' + rbnode.type)
    if visitor is None:
        raise NotImplementedParsingError(
            'Function visitor not declared for type="{type}"'.format(
                type=rbnode.type,
                ), rbnode, s)
    ofnode = visitor(rbnode, s)

    if s['keyword'] == 'expression':
        if 'var_tmp' not in s:
            raise ParsingException('No var_tmp after expression parsing.', rbnode, s)

    return ofnode


def visit_function_endl(rbnode, s):
    return


def visit_function_assignment(rbnode, s):
    my_assert(s['keyword'] == 'function', rbnode, s)

    if rbnode.target.type != 'name':
        raise FunctionTooComplexException('assignment target is not a name', rbnode, s)

    name = rbnode.target.value

    child_state = {
        'keyword': 'expression',
        'local_variables': s['local_variables'],
        'auxiliary_functions': s['auxiliary_functions'],
    }
    visit_function_rbnode(rbnode.value, child_state)
    if 'var_tmp' not in child_state:
        raise ParsingError('No var_tmp after expression parsing', rbnode, s)
    s['local_variables'][name] = child_state['var_tmp']


def visit_function_atomtrailers(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s, s['keyword'])

    child_state = {
        'keyword': 'expression',
        'local_variables': s['local_variables'],
        'auxiliary_functions': s['auxiliary_functions'],
    }
    visit_function_rbnode(rbnode.value[0], child_state)
    base = child_state['var_tmp']

    for i in range(1, len(rbnode.value)):
        child_state = {
            'keyword': 'atomtrailers',
            'local_variables': s['local_variables'],
            'auxiliary_functions': s['auxiliary_functions'],
            'atomtrailers_base': base,
        }
        visit_function_rbnode(rbnode.value[i], child_state)
        base = child_state['atomtrailers_new_base']

    s['var_tmp'] = base


def visit_function_binary_operator(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    op = rbnode.value

    parsed_args = []
    for arg in [rbnode.first, rbnode.second]:
        child_state = {
            'keyword': 'expression',
            'local_variables': s['local_variables'],
            'auxiliary_functions': s['auxiliary_functions'],
        }
        visit_function_rbnode(arg, child_state)
        parsed_arg = child_state['var_tmp']
        parsed_args.append(parsed_arg)

    var_tmp = {
        'type': 'value',
        'nodetype': 'arithmetic_operation',
        'op': op,
        'operands': parsed_args,
    }
    s['var_tmp'] = var_tmp
    return


def visit_function_unitary_operator(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    op = rbnode.value

    arg = rbnode.target
    child_state = {
        'keyword': 'expression',
        'local_variables': s['local_variables'],
        'auxiliary_functions': s['auxiliary_functions'],
    }
    visit_function_rbnode(arg, child_state)
    parsed_arg = child_state['var_tmp']

    var_tmp = {
        'type': 'value',
        'nodetype': 'arithmetic_operation',
        'op': op,
        'operands': [parsed_arg],
    }
    s['var_tmp'] = var_tmp
    return


def visit_function_name(rbnode, s):
    name = rbnode.value

    if s['keyword'] == 'expression':
        if name in s['local_variables']:
            s['var_tmp'] = s['local_variables'][name]
            return

        if name in s['auxiliary_functions']:
            # to complex (TODO)
            raise FunctionTooComplexException('auxiliary function used', rbnode, s)

        if name == 'period':
            var_tmp = {
                'type': 'period',
                'nodetype': 'builtin-period'
            }
            s['var_tmp'] = var_tmp
            return

        if name == 'simulation':
            var_tmp = {
                'type': 'simulation'
            }
            s['var_tmp'] = var_tmp
            return

        if name == 'self':
            var_tmp = {
                'type': 'self'
            }
            s['var_tmp'] = var_tmp
            return

        if name in ['round', 'around', 'sum', 'not_', 'or_', 'and_', 'min_', 'max_', 'mini', 'maxi']:
            var_tmp = {
                'type': 'arithmetic_operation_tmp',
                'nodetype': 'arithmetic_operation_tmp',
                'op': name,
            }
            s['var_tmp'] = var_tmp
            return

        if name in ['datetime64']:
            var_tmp = {
                'type': 'instant_op_tmp',
                'nodetype': 'instant_op_tmp',
                'op': name,
            }
            s['var_tmp'] = var_tmp
            return

        if name in ['CHEF', 'CONJ', 'CREF', 'ENFS', 'PAC1', 'PAC2', 'PAC3', 'PART', 'PREF', 'VOUS']:
            var_tmp = {
                'type': 'role',
                'name': name,
            }
            s['var_tmp'] = var_tmp
            return

        if name == 'apply_thresholds':
            # to deal with specifically (TODO)
            var_tmp = {
                'type': 'apply_thresholds_tmp',
                'nodetype': 'apply_thresholds',
            }
            s['var_tmp'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown name {}'.format(name), rbnode, s)

    if s['keyword'] == 'atomtrailers':
        base = s['atomtrailers_base']

        if base['type'] == 'instant':
            instant_op = name
            if instant_op in ['offset', 'period']:
                var_tmp = {
                    'type': 'instant_op_tmp',
                    'nodetype': 'instant_op_tmp',
                    'op': instant_op,
                    'input_instant': base,
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            raise NotImplementedParsingError('Unknown instant operand', rbnode, s)

        if base['type'] == 'period':
            period_op = name
            if period_op in ['this_month', 'n_2', 'last_year', 'this_year']:
                var_tmp = {
                    'type': 'period',
                    'nodetype': 'period-operation',
                    'operator': period_op,
                    'operands': [base],
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            if period_op == 'start':
                var_tmp = {
                    'type': 'instant',
                    'nodetype': 'period-to-instant',
                    'operator': 'start',
                    'operands': [base],
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            if period_op == 'offset':
                var_tmp = {
                    'type': 'period_tmp',
                    'nodetype': 'period_tmp',
                    'operator': 'offset',
                    'input_period': base,
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            raise NotImplementedParsingError('Unknown period operand', rbnode, s)

        if base['type'] == 'simulation':
            simulation_op = name
            if simulation_op in ['calculate', 'calculate_add', 'compute', 'compute_add']:
                var_tmp = {
                    'type': 'simulation_operation_tmp',
                    'nodetype': 'simulation_operation_tmp',
                    'operator': simulation_op,
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            if simulation_op == 'legislation_at':
                var_tmp = {
                    'type': 'legislation_at_tmp',
                    'nodetype': 'legislation_at_tmp',
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            raise NotImplementedParsingError('Unknown simulation op.', rbnode, s)

        if base['type'] == 'self':
            self_op = name
            if self_op in ['split_by_roles', 'sum_by_entity', 'filter_role']:
                var_tmp = {
                    'type': 'self_operation_tmp',
                    'nodetype': 'self_operation_tmp',
                    'operator': self_op,
                }
                s['atomtrailers_new_base'] = var_tmp
                return

            raise NotImplementedParsingError('Unknown self op {}.'.format(self_op), rbnode, s)

        if base['type'] == 'parameter':
            var_tmp = {
                'type': 'parameter',
                'nodetype': 'parameter',
                'instant': base['instant'],
                'path': base['path'] + [name],
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        if base['type'] == 'apply_thresholds_tmp':
            var_tmp = {
                'type': 'value',
                'nodetype': 'apply_thresholds',
                'rbnode': rbnode,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown op {}'.format(name), rbnode, s)

    raise NotImplementedParsingError('Wrong keyword {}'.format(name), rbnode, s)


def visit_function_int(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    var_tmp = {
        'type': 'value',
        'nodetype': 'int',
        'value': rbnode.value,
    }
    s['var_tmp'] = var_tmp
    return


def visit_function_float(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    var_tmp = {
        'type': 'value',
        'nodetype': 'float',
        'value': rbnode.value,
    }
    s['var_tmp'] = var_tmp
    return


def visit_function_associative_parenthesis(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    visit_function_rbnode(rbnode.value, s)


def visit_function_return(rbnode, s):
    my_assert(s['keyword'] == 'function', rbnode, s)

    my_assert(rbnode.value.type == 'tuple', rbnode, s)

    returned_tuple = rbnode.value
    my_assert(len(returned_tuple.value) ==  2, rbnode, s)

    rb_period = returned_tuple.value[0]
    child_state = {
        'keyword': 'expression',
        'local_variables': s['local_variables'],
        'auxiliary_functions': s['auxiliary_functions'],
    }
    visit_function_rbnode(rb_period, child_state)
    returned_period = child_state['var_tmp']
    my_assert(returned_period['type'] == 'period', rbnode, s)

    rb_value = returned_tuple.value[1]
    child_state = {
        'keyword': 'expression',
        'local_variables': s['local_variables'],
        'auxiliary_functions': s['auxiliary_functions'],
    }
    visit_function_rbnode(rb_value, child_state)
    returned_value = child_state['var_tmp']
    my_assert(returned_value['type'] == 'value', rbnode, s)

    returned_value = {
        'type': 'return',
        'nodetype': 'return',
        'period': returned_period,
        'value': returned_value,
    }
    my_assert('return' not in s, rbnode, s)
    s['return'] = returned_value
    return


def visit_function_comparison(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    my_assert(rbnode.value.type == "comparison_operator", rbnode, s)
    op = rbnode.value.first
    my_assert(not rbnode.value.second, rbnode, s)

    parsed_args = []
    for arg in [rbnode.first, rbnode.second]:
        child_state = {
            'keyword': 'expression',
            'local_variables': s['local_variables'],
            'auxiliary_functions': s['auxiliary_functions'],
        }
        visit_function_rbnode(arg, child_state)
        parsed_arg = child_state['var_tmp']
        parsed_args.append(parsed_arg)

    var_tmp = {
        'type': 'value',
        'nodetype': 'arithmetic_operation',
        'op': op,
        'operands': parsed_args,
    }
    s['var_tmp'] = var_tmp
    return


def visit_function_comment(rbnode, s):
    # ignored (TODO)
    return


def visit_function_list(rbnode, s):
    my_assert(s['keyword'] == 'expression', rbnode, s)

    # ignored (TODO)
    var_tmp = {
        'type': 'list',
        'nodetype': 'list',
        'rbnode': rbnode,
    }
    s['var_tmp'] = var_tmp
    return


def visit_function_for(rbnode, s):
    my_assert(s['keyword'] == 'function', rbnode, s)

    # too complex (TODO)
    raise FunctionTooComplexException('foo loop', rbnode, s)
    return


def visit_function_def(rbnode, s):
    my_assert(s['keyword'] == 'function', rbnode, s)

    # too complex (TODO)
    raise FunctionTooComplexException('inner function', rbnode, s)
    return


def visit_function_string(rbnode, s):
    if s['keyword'] == 'function':
        # documentation string (TODO)
        return

    if s['keyword'] == 'expression':
        var_tmp = {
            'type': 'string',
            'nodetype': 'string',
            'rbnode': rbnode.value,
        }
        s['var_tmp'] = var_tmp
        return

    raise NotImplementedParsingError('', rbnode, s)


def visit_function_call(rbnode, s):
    my_assert(s['keyword'] == 'atomtrailers', rbnode, s)

    arg_list = []
    arg_dict = {}

    no_target = True
    args = rbnode.value
    for arg in args:
        my_assert(arg.type == 'call_argument', rbnode, s)
        if arg.target:
            no_target = False
            my_assert(arg.target.type == 'name', rbnode, s)
            target = arg.target.value
        else:
            my_assert(no_target, rbnode, s)

        child_state = {
            'keyword': 'expression',
            'local_variables': s['local_variables'],
            'auxiliary_functions': s['auxiliary_functions'],
        }
        visit_function_rbnode(arg.value, child_state)
        value = child_state['var_tmp']

        if arg.target:
            arg_dict[target] = value
        else:
            arg_list.append(value)


    base = s['atomtrailers_base']

    if base['type'] == 'simulation':
        if simulation_op in ['calculate', 'calculate_add', 'compute', 'compute_add']:
            my_assert(len(arg_list) in [1, 2], rbnode, s)
            my_assert(not arg_dict, rbnode, s)

            my_assert(arg_list[0]['type'] == 'string', rbnode, s)
            called_var = arg_list[0]['value']
            operands = [called_var]

            if len(arg_list) == 2:
                arg_period = arg_list[1]
                my_assert(arg_period['type'] == 'period', rbnode, s)
                operands.append(arg_period)

            var_tmp = {
                'type': 'value',
                'nodetype': 'variable_for_period',
                'operator': simulation_op,
                'operands': operands,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown simulation op {}'.format(simulation_op), rbnode, s)

    if base['type'] == 'legislation_at_tmp':
        my_assert(len(arg_list) == 1, rbnode, s)
        my_assert(len(arg_dict) == 0, rbnode, s)

        instant_arg = arg_list[0]
        my_assert(instant_arg['type'] == 'instant', rbnode, s)

        var_tmp = {
            'type': 'parameter',
            'nodetype': 'parameter',
            'instant': instant_arg,
            'path': [],
        }
        s['atomtrailers_new_base'] = var_tmp
        return

    if base['type'] == 'self_operation_tmp':
        self_op = base['operator']

        if self_op in ['sum_by_entity', 'filter_role']:
            # no assertion about args (TODO)
            var_tmp = {
                'type': 'value',
                'nodetype': 'self_operation',
                'operator': self_op,
                'arg_list': arg_list,
                'arg_dict': arg_dict,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        if self_op in ['split_by_roles']:
            # no assertion about args (TODO)
            var_tmp = {
                'type': 'split_by_roles',
                'nodetype': 'split_by_roles',
                'operator': self_op,
                'arg_list': arg_list,
                'arg_dict': arg_dict,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown self_operation_tmp {}'.format(self_op), rbnode, s)

    if base['type'] == 'instant_op_tmp':
        instant_op = base['op']
        if instant_op in ['offset', 'datetime64']:
            var_tmp = {
                'type': 'instant',
                'nodetype': 'instant_op',
                'op': instant_op,
                'arg_list': arg_list,
                'arg_dict': arg_dict,
            }
            if 'input_instant' in base:
                input_instant = base['input_instant']
                var_tmp['input_instant'] = input_instant
            s['atomtrailers_new_base'] = var_tmp
            return

        if instant_op in ['period']:
            input_instant = base['input_instant']
            var_tmp = {
                'type': 'period',
                'nodetype': 'instant_to_period',
                'op': instant_op,
                'input_instant': input_instant,
                'arg_list': arg_list,
                'arg_dict': arg_dict,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown instant op {}'.format(instant_op), rbnode, s)

    if base['type'] == 'arithmetic_operation_tmp':
        op = base['op']

        if op in ['round', 'around', 'sum', 'not_', 'or_', 'and_', 'min_', 'max_', 'mini', 'maxi']:
            # no assertion about args (TODO)
            var_tmp = {
                'type': 'value',
                'nodetype': 'arithmetic_operation',
                'op': base['op'],
                'arg_list': arg_list,
                'arg_dict': arg_dict,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown arithmetic_operation_tmp.', rbnode, s)

    if base['type'] == 'simulation_operation_tmp':
        simulation_op = base['operator']

        if simulation_op in ['calculate', 'calculate_add', 'compute', 'compute_add']:
            var_tmp = {
                'type': 'value',
                'nodetype': 'simulation_operation',
                'operator': simulation_op,
                'arg_list': arg_list,
                'arg_dict': arg_dict,
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown simulation_operation_tmp.', rbnode, s)

    if base['type'] == 'period_tmp':
        period_op = base['operator']

        if period_op in ['offset']:
            var_tmp = {
                'type': 'period',
                'nodetype': 'period_operation',
                'operator': period_op,
                'arg_list': arg_list,
                'arg_dict': arg_dict,
                'input_period': base['input_period'],
            }
            s['atomtrailers_new_base'] = var_tmp
            return

        raise NotImplementedParsingError('Unknown period_tmp op.', rbnode, s)

    raise NotImplementedParsingError('Unknown caller', rbnode, s)


def visit_function_getitem(rbnode, s):
    my_assert(s['keyword'] == 'atomtrailers', rbnode, s)

    base = s['atomtrailers_base']

    child_state = {
        'keyword': 'expression',
        'local_variables': s['local_variables'],
        'auxiliary_functions': s['auxiliary_functions'],
    }
    visit_function_rbnode(rbnode.value, child_state)
    role = child_state['var_tmp']

    if base['type'] == 'split_by_roles':
        var_tmp = {
            'type': 'value',
            'nodetype': 'slit_by_roles_with_role',
            'operator': base['operator'],
            'split_arg_list': base['arg_list'],
            'split_arg_dict': base['arg_dict'],
            'role': role
        }
        s['atomtrailers_new_base'] = var_tmp
        return

    raise NotImplementedParsingError('Unknown getitem source.', rbnode, s)


def parse(parsed_modules, parsed_classes):
    parsed_functions = {}
    parsed_functions_counter = 0
    functions_too_complex = []

    for module_name, module in parsed_classes.items():
        print('Visiting module {}'.format(module_name))

        parsed_functions[module_name] = {
            'classes': {},
        }

        for class_name, cl in module['parsed_classes'].items():
            print('Visiting class {} to parse its function(s)'.format(class_name))

            parsed_functions[module_name]['classes'][class_name] = {
                'parsed_functions': {},
            }

            for function_name, fn in cl['class_functions'].items():
                print('Visiting function {}'.format(function_name))

                s = {
                    'keyword': 'function',
                    'module_name': module_name,
                    'class_name': class_name,
                    'auxiliary_functions': parsed_modules[module_name]['auxiliary_functions'],
                    'function_name': function_name,
                    'local_variables': {},
                }

                try:
                    for rbnode in fn['instructions']:
                        visit_function_rbnode(rbnode, s)
                except FunctionTooComplexException as e:
                    functions_too_complex.append({
                            'module_name': module_name,
                            'class_name': class_name,
                            'function_name': function_name,
                            'message': e.message,
                            'rbnode': e.rbnode,
                            'state': e.s,
                        })
                else:
                    parsed_functions[module_name]['classes'][class_name]['parsed_functions'][function_name] = {
                        'return': s['return'],
                        }
                    parsed_functions_counter += 1
