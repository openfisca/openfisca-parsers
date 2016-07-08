import {assoc} from 'ramda'

import traverse from '../traverse'

export const visitor = {
  __ALL__ (node, state) {
    const nodeWithId = assoc('id', state.nextId, node)
    state.nextId += 1
    return nodeWithId
  }
}

export const getInitialState = (node) => ({nextId: 0})

export function addUniqueIdentifiers (node) {
  const state = getInitialState(node)
  return traverse(visitor, state, node)
}
