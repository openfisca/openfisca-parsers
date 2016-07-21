import {chain, prop, indexBy, pipe} from 'ramda'

import traverse from '../traverse'

export const visitor = {
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
  symbol (node, state) {
    const formula = state.formulaNodeByName[node.value]
    return {
      type: 'Variable',
      name: node.value,
      formula
    }
  }
}

export const getInitialState = (rootNode) => ({
  debug: false,
  formulaNodeByName: pipe(
    chain(prop('formulas')),
    indexBy(prop('name'))
  )(rootNode.regles)
})

export function mToOpenFisca (rootNode) {
  const state = getInitialState(rootNode)
  return traverse(visitor, state, rootNode)
}
