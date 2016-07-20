#! /usr/bin/env node

import {pipe, type} from 'ramda'
import read from 'read-file-stdin'

import {mToOpenFisca} from './visitors/m_to_openfisca'
import {filterApplication} from './visitors/filter_application'

// Example:
// jq --slurpfile chap1 json/chap-1.json '{type: "Module", variables: (.variables + $chap1[].variables)}' json/isf.json

function main (nodes) {
  if (type(nodes) !== 'Array') {
    throw new TypeError('JSON data must be an array')
  }
  const moduleNode = {
    type: 'Module',
    regles: nodes
  }
  const transform = pipe(filterApplication('batch'), mToOpenFisca)
  const transformedNode = transform(moduleNode)
  console.log(JSON.stringify(transformedNode, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  const nodes = JSON.parse(buffer)
  main(nodes)
})
