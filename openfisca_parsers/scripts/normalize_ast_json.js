#!/usr/bin/env node

import * as fs from 'fs'
import * as process from 'process'

import {normalize, valuesOf} from 'normalizr'

import {Variable} from './schemas'

function main (fileContent) {
  const node = JSON.parse(fileContent)
  const schema = node.type ? Variable : valuesOf(Variable)
  const result = normalize(node, schema)
  console.log(JSON.stringify(result, null, 2))
}

if (process.argv.length < 3 || !process.argv[2]) {
  let fileContent = ''
  process.stdin.setEncoding('utf8')
  process.stdin.on('readable', () => {
    var chunk = process.stdin.read()
    if (chunk !== null) {
      fileContent += chunk
    }
  })
  process.stdin.on('end', () => {
    main(fileContent)
  })
} else {
  if (process.argv.length > 3) {
    throw new Error('Provide a single file path')
  }
  const filePath = process.argv[2]
  const fileContent = fs.readFileSync(filePath)
  main(fileContent)
}
