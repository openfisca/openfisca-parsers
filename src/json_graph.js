#! /usr/bin/env node

import read from 'read-file-stdin'


function unserialize(json_graph) {
  console.assert(Object.keys(json_graph).length == 1);
  console.assert('graph' in json_graph);
  let graph = json_graph.graph;

  console.assert(graph.directed);

  let edges = graph.edges;
  let input_nodes = graph.nodes;

  let output_nodes = {};

  for (var i = 0; i < input_nodes.length; i++) {
    let input_node = input_nodes[i];
    let input_id = input_node.id;
    delete input_node['id'];

    output_nodes[input_id] = input_node;
  }

  for (var i = 0; i < edges.length; i++) {
    let edge = edges[i];
    let source_id = edge.source;
    let target_id = edge.target;
    let label = edge.label;

    let source_node = output_nodes[source_id];
    let target_node = output_nodes[target_id];

    if (['input_period', 'output_period', 'operand', 'parameter',
         'instant', 'variable', 'period', 'formula', 'value'].includes(label)) {
      source_node[label] = target_node;
    } else {
      let regexp = /^operands\[([0-9]+)\]/;
      let index = regexp.exec(label);
      if (index) {
        index = parseInt(index);
        if (!('operands' in Object.keys(source_node))) {
          source_node.operands = [];
        }
        source_node.operands[index] = target_node;
      } else {
        throw 'Unknown label : ' + label;
      }
    }
  }
  return output_nodes;
}


function main(json_graph) {
  let nodes = unserialize(json_graph);

  console.log(nodes);
}


read(process.argv[2], (err, buffer) => {
  if (err) { throw err; }
  const json_graph = JSON.parse(buffer);
  main(json_graph);
});
