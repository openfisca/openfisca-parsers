#! /usr/bin/env node

import {addIndex, chain, concat, head, prop, tail, map} from 'ramda'
import read from 'read-file-stdin'

import {traverse} from './traverse'

const mapIndexed = addIndex(map)

// Example: jq --slurpfile chap1 json/chap-1.json '. + $chap1[].variables' json/isf.json > json/isf_with_chap1.json

// Visitor

const mToOpenFiscaVisitor = {
  Module (node, state) {
    return {
      type: 'Module',
      variables: chain(prop('formulas'), node.regles)
    }
  },
  formula (node, state) {
    return {
      type: 'Variable',
      name: node.name,
      formula: node.expression
    }
  },
  sum_expression (node, state) {
    const operandsHead = head(node.operands)
    const operandsTail = tail(node.operands)
    const operands = concat(
      [operandsHead],
      mapIndexed(
        (operator, index) => operator === '+'
          ? operandsTail[index]
          : {
            type: 'ArithmeticOperation',
            operator: '-',
            operands: operandsTail[index]
          },
        node.operators
      )
    )
    return {
      type: 'ArithmeticOperation',
      operator: '+',
      operands
    }
  },
  symbol (node, state) {
    return {
      type: 'VariableReference',
      name: node.value
    }
  }
}

// Main function

function main (nodes) {
  const moduleNode = {
    type: 'Module',
    regles: nodes
  }
  const state = {debug: false}
  const transformedNode = traverse(mToOpenFiscaVisitor, state, moduleNode)
  console.log(JSON.stringify(transformedNode, null, 2))
}

read(process.argv[2], (err, buffer) => {
  if (err) throw err
  const nodes = JSON.parse(buffer)
  main(nodes)
})
