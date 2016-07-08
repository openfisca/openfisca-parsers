import {assoc} from 'ramda'

export default {
  __ALL__ (node, state) {
    const nodeWithId = assoc('id', state.nextId, node)
    state.nextId += 1
    return nodeWithId
  }
}

export const getInitialState = (node) => ({nextId: 0})
