#! /usr/bin/env node

import {pipe, type} from 'ramda'
import read from 'read-file-stdin'

import {addUniqueIdentifiers} from './visitors/add_unique_identifiers'
import {resolveReferences} from './visitors/resolve_references'

function main (node) {
  if (type(node) !== 'Object' || node.type !== 'Module') {
    throw new TypeError('JSON data must be an object like {type: "Module", ...}')
  }
  const transform = pipe(addUniqueIdentifiers, resolveReferences)
  const transformedNode = transform(node)
  console.log(JSON.stringify(transformedNode, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  const node = JSON.parse(buffer)
  main(node)
})
