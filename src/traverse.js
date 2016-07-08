import {curry, map, type} from 'ramda'

// Traversal functions

const traverse = curry((visitor, state, node) => {
  const nodeJSType = type(node)
  return nodeJSType === 'Array'
    ? map(traverse(visitor, state), node)
    : nodeJSType === 'Object'
      ? map(traverse(visitor, state), visit(visitor, state, node))
      : node
})

function visit (visitor, state, node) {
  const nodeType = node.type
  const visitorFunction = visitor[nodeType] || visitor.__ALL__
  if (visitorFunction) {
    Object.freeze(node)
    if (state.debug) {
      console.log('node:', node)
    }
    const visitedNode = visitorFunction(node, state)
    if (type(visitedNode) === 'Undefined') {
      throw Error(`Visitor function '${visitorFunction.name}' returned 'undefined' but it must return a node`)
    }
    if (state.debug) {
      console.log('visited node:', visitedNode)
    }
    return visitedNode
  } else {
    return node
  }
}

export default traverse
