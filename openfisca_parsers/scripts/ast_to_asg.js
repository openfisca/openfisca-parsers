#! /usr/bin/env node

import {curry, has, indexBy, map, prop, type} from 'ramda'
import read from 'read-file-stdin'

// Traversal functions

const traverse = curry((visitor, state, node) => {
  const nodeJSType = type(node)
  return nodeJSType === 'Array'
    ? map(traverse(visitor, state), node)
    : nodeJSType === 'Object'
      ? map(traverse(visitor, state), visit(visitor, state, node))
      : node
})

function visit (visitor, state, node) {
  const {type} = node
  if (type in visitor) {
    Object.freeze(node)
    return visitor[type](node, state)
  } else {
    return node
  }
}

// Visitor

const resolveReferencesVisitor = {
  VariableReference (node, state) {
    const {name} = node
    if (has(name, state.variableByName)) {
      return state.variableByName[name]
    } else {
      const message = `VariableReference node references a Variable node {name: '${name}', ...} but is not found`
      switch (state.onVariableNotFound) {
        case 'abort':
          throw new Error(message)
        case 'keep':
          return node
      }
    }
  }
}

// Main function

function main (nodes, {onVariableNotFound = 'keep'}) {
  const variableByName = indexBy(prop('name'), nodes)
  const state = {onVariableNotFound, variableByName}
  const transformedNode = traverse(resolveReferencesVisitor, state, nodes)
  console.log(JSON.stringify(transformedNode, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  const nodes = JSON.parse(buffer)
  const opts = {}
  main(nodes, opts)
})
