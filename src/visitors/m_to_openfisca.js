import {addIndex, chain, concat, head, prop, tail, map} from 'ramda'

const mapIndexed = addIndex(map)

export default {
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
