import {assoc} from 'ramda'

import traverse from '../traverse'

export const visitor = {
  __ALL__ (node, state) {
    const nodeWithId = assoc('id', state.nextId, node)
    state.nextId += 1
    return nodeWithId
  }
}

export const getInitialState = (rootNode) => ({nextId: 0})

export function addUniqueIdentifiers (rootNode) {
  const state = getInitialState(rootNode)
  return traverse(visitor, state, rootNode)
}
