#! /usr/bin/env node

import {pipe} from 'ramda'
import read from 'read-file-stdin'

import {addUniqueIdentifiers} from './visitors/add_unique_identifiers'
import {resolveReferences} from './visitors/resolve_references'

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
