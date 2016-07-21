import {assoc, contains, filter} from 'ramda'

import traverse from '../traverse'

export const visitor = {
  Module (node, state) {
    const regles = filter(
      regle => contains(state.applicationName, regle.applications),
      node.regles
    )
    return assoc('regles', regles, node)
  }
}

export const getInitialState = (applicationName) => (rootNode) => ({applicationName})

export const filterApplication = (applicationName) => (rootNode) => {
  const state = getInitialState(applicationName)(rootNode)
  return traverse(visitor, state, rootNode)
}
