#!/usr/bin/env node

import * as fs from 'fs'
import * as process from 'process'

import ArraySchema from 'normalizr/lib/IterableSchema'
import EntitySchema from 'normalizr/lib/EntitySchema'
import UnionSchema from 'normalizr/lib/UnionSchema'

import * as schemas from './schemas'

const titleKeyByEntityType = {
  Number: 'value',
  Variable: 'name'
}

function referenceKeys (schema) {
  return Object.keys(schema).filter(key => {
    const value = schema[key]
    return value instanceof ArraySchema || value instanceof EntitySchema || value instanceof UnionSchema
  })
}

function main (fileContent) {
  const data = JSON.parse(fileContent)
  if (!data.result || !data.entities) {
    throw new Error('Provide a normalized AST file (see normalize_ast_json.js script)')
  }
  // Build nodes and edges
  const nodes = []
  const edges = []
  const {entities} = data
  for (let type in entities) {
    const entityById = entities[type]
    for (let id in entityById) {
      const entity = entityById[id]
      const titleKey = titleKeyByEntityType[type] || 'id'
      nodes.push({
        id,
        label: `${type} ${entity[titleKey]}`
      })
      const schema = schemas[type]
      for (let referenceKey of referenceKeys(schema)) {
        const referencedSchema = schema[referenceKey]
        if (referencedSchema instanceof EntitySchema) {
          edges.push({
            source: id,
            target: entity[referenceKey],
            directed: true,
            label: referenceKey
          })
        } else if (referencedSchema instanceof ArraySchema) {
          const targets = entity[referenceKey]
          for (let target of targets) {
            edges.push({
              source: id,
              target: target.id,
              directed: true,
              label: referenceKey
            })
          }
        } else if (referencedSchema instanceof UnionSchema) {
          if (!entity._stub) {
            edges.push({
              source: id,
              target: entity[referenceKey].id,
              directed: true,
              label: referenceKey
            })
          }
        } else {
          throw new Error('Not implemented')
        }
      }
    }
  }
  const result = {
    graph: {
      directed: true,
      nodes,
      edges
    }
  }
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
