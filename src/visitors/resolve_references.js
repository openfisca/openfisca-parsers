import {has, indexBy, prop} from 'ramda'

import traverse from '../traverse'

export const visitor = {
  VariableReference (node, state) {
    const {name} = node
    if (has(name, state.variableByName)) {
      return state.variableByName[name]
    } else {
      const message = `VariableReference node references a Variable node {name: '${name}', ...} but is not found`
      switch (state.onVariableNotFound) {
        case 'abort':
          throw new Error(message)
        case 'keep':
          return node
      }
    }
  }
}

export const getInitialState = (rootNode) => ({
  onVariableNotFound: 'keep',
  variableByName: indexBy(prop('name'), rootNode.variables)
})

export function resolveReferences (rootNode) {
  const state = getInitialState(rootNode)
  return traverse(visitor, state, rootNode)
}
