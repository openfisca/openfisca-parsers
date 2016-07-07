#! /usr/bin/env node

import {assoc, has, indexBy, pipe, prop} from 'ramda'
import read from 'read-file-stdin'

import {traverse} from './traverse'

// Visitors

const addUniqueIdentifiersVisitor = {
  __ALL__ (node, state) {
    const nodeWithId = assoc('id', state.nextId, node)
    state.nextId += 1
    return nodeWithId
  }
}

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

function addUniqueIdentifiers (nodes) {
  const state = {nextId: 0}
  return traverse(addUniqueIdentifiersVisitor, state, nodes)
}

function resolveReferences (nodes) {
  const variableByName = indexBy(prop('name'), nodes)
  const state = {onVariableNotFound: 'keep', variableByName}
  return traverse(resolveReferencesVisitor, state, nodes)
}

// Main function

function main (nodes) {
  const transform = pipe(addUniqueIdentifiers, resolveReferences)
  const transformedNode = transform(nodes)
  console.log(JSON.stringify(transformedNode, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  const nodes = JSON.parse(buffer)
  main(nodes)
})
