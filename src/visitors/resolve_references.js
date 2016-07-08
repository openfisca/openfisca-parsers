import {has, indexBy, prop} from 'ramda'

export default {
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

export const getInitialState = (node) => ({
  onVariableNotFound: 'keep',
  variableByName: indexBy(prop('name'), node)
})
