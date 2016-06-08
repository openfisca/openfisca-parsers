#!/usr/bin/env node

import {normalize, valuesOf} from 'normalizr'
import read from 'read-file-stdin'

import * as schemas from './schemas'

function main (fileContent) {
  const node = JSON.parse(fileContent)
  const schema = node.type ? schemas[node.type] : valuesOf(schemas.Variable)
  const result = normalize(node, schema)
  console.log(JSON.stringify(result, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  main(buffer)
})
