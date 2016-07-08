#! /usr/bin/env node

import {normalize} from 'normalizr'
import {type} from 'ramda'
import read from 'read-file-stdin'

import * as schemas from './schemas'

function main (node) {
  if (type(node) !== 'Object' || node.type !== 'Module') {
    throw new TypeError('JSON data must be an object like {type: "Module", ...}')
  }
  // Skip Module node to simplify graph.
  const result = normalize(node.variables, schemas.variables)
  console.log(JSON.stringify(result, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  const node = JSON.parse(buffer)
  main(node)
})
