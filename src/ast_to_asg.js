#! /usr/bin/env node

import {pipe} from 'ramda'
import read from 'read-file-stdin'

import addUniqueIdentifiersVisitor, {getInitialState as getAddUniqueIdentifiersInitialState} from './visitors/add_unique_identifiers'
import resolveReferencesVisitor, {getInitialState as getResolveReferencesInitialState} from './visitors/resolve_references'
import traverse from './traverse'

function addUniqueIdentifiers (nodes) {
  const state = getAddUniqueIdentifiersInitialState(nodes)
  return traverse(addUniqueIdentifiersVisitor, state, nodes)
}

function resolveReferences (nodes) {
  const state = getResolveReferencesInitialState(nodes)
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
