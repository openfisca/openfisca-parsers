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


"""Functions to convert an OpenFisca ASG to a JSON Graph format data structure."""

import re
import copy

from toolz.curried import dissoc, merge, valfilter

from .ofnodes import is_ofnode, show_json


def asg_to_json_graph(root_ofnode):
    id_by_ofnode_address = {}
    nodes = []
    edges = []

    def append_edge(edge):
        '''
        Mutates `edges` in outer scope.

        Workaround due to a limitation of graphlib npm module which has only `setEdge` method.
        Consequence: it is not possible to add many edges having the same source and target.
        Even if graphviz supports it.
        See: https://github.com/cpettitt/graphlib/blob/master/lib/graph.js#L353
        '''
        for edge1 in edges:
            if edge['source'] == edge1['source'] and edge['target'] == edge1['target']:
                edge1['label'] += '\n' + edge['label']
                return
        edges.append(edge)

    class ShortIdGenerator(object):
        next_shortid = 0

        def generate(self):
            result = self.next_shortid
            self.next_shortid += 1
            return result

    short_id_generator = ShortIdGenerator()

    def visit(ofnode):
        assert is_ofnode(ofnode), ofnode
        ofnode_address = id(ofnode)
        if ofnode_address in id_by_ofnode_address:
            return
        ofnode_id = short_id_generator.generate()
        id_by_ofnode_address[ofnode_address] = ofnode_id
        jgfnode = merge(ofnode, {
            'id': ofnode_id,
            })
        for key, value in ofnode.items():
            if isinstance(value, list):
                if key != 'path':
                    jgfnode = dissoc(jgfnode, key)
                    for index, item in enumerate(value):
                        if is_ofnode(item):
                            visit(item)
                            append_edge({
                                'source': ofnode_id,
                                'target': id_by_ofnode_address[id(item)],
                                'label': u'{}[{}]'.format(key, index),
                                })
            elif is_ofnode(value):
                jgfnode = dissoc(jgfnode, key)
                visit(value)
                edge = {
                    'source': ofnode_id,
                    'target': id_by_ofnode_address[id(value)],
                    'label': key,
                    }
                # if ofnode['type'] == 'ValueForPeriod' and key == 'period':
                #     edge['color'] = 'red'
                append_edge(edge)
        nodes.append(jgfnode)

    if isinstance(root_ofnode, list):
        for item in root_ofnode:
            visit(item)
    else:
        visit(root_ofnode)
    return {
        'graph': {
            'directed': True,
            'nodes': nodes,
            'edges': edges,
            },
        }


def show_json_graph(ofnode):
    show_json(asg_to_json_graph(ofnode))


def json_graph_to_asg(json_graph):
    assert json_graph.keys() == ['graph']
    graph = json_graph['graph']

    assert graph['directed']

    edges = graph['edges']
    input_nodes = graph['nodes']

    output_nodes = {}

    for input_node in input_nodes:
        node_id = input_node['id']

        output_node = copy.deepcopy(input_node)
        del output_node['id']
        output_nodes[node_id] = output_node

    for edge in edges:
        source_id = edge['source']
        target_id = edge['target']
        label = edge['label']

        source_node = output_nodes[source_id]
        target_node = output_nodes[target_id]

        if label in ['input_period', 'output_period', 'operand', 'parameter',
                     'instant', 'variable', 'period', 'formula', 'value']:
            source_node[label] = target_node
        else:
            m = re.match(r'^operands\[([0-9]+)\]$', label)
            if m:
                index = int(m.groups()[0])
                if 'operands' in source_node.keys():
                    ops = source_node['operands']
                    if index < len(ops):
                        ops[index] = target_node
                    else:
                        ops += (index - len(ops)) * [None] + [target_node]
                else:
                    source_node['operands'] = index * [None] + [target_node]
            else:
                raise ValueError('Unknown label : {0}'.format(label))

    return output_nodes


def print_deep_diff(d1, d2, path=""):
    for k in d1:
        if k not in d2:
            print path, ":"
            print k + " as key not in d2", "\n"
        else:
            if isinstance(d1[k], dict):
                path = k \
                    if path == '' \
                    else path + '->' + k
                print_deep_diff(d1[k], d2[k], path)
            else:
                if d1[k] != d2[k]:
                    print path, ":"
                    print " - ", k, " : ", d1[k]
                    print " + ", k, " : ", d2[k]
