
import * as fs from 'fs'
import * as process from 'process'

import {normalize, Schema, arrayOf, unionOf} from 'normalizr'

const arithmeticOperator = new Schema('ArithmeticOperator')
const number = new Schema('Number')
const parameter = new Schema('Parameter')
const parameterAtInstant = new Schema('ParameterAtInstant')
const period = new Schema('Period')
const periodOperator = new Schema('PeriodOperator')
const variable = new Schema('Variable')
const variableForPeriod = new Schema('VariableForPeriod')

const expression = unionOf({
  ArithmeticOperator: arithmeticOperator,
  Number: number,
  Parameter: parameter,
  ParameterAtInstant: parameterAtInstant,
  VariableForPeriod: variableForPeriod
}, {schemaAttribute: 'type'})

const periodOrPeriodOperator = unionOf({
  Period: period,
  PeriodOperator: periodOperator
}, {schemaAttribute: 'type'})

arithmeticOperator.define({
  operands: arrayOf(expression)
})

parameterAtInstant.define({
  instant: periodOperator,
  parameter
})

periodOperator.define({
  operand: periodOrPeriodOperator
})

variable.define({
  formula: expression,
  output_period: periodOrPeriodOperator
})

variableForPeriod.define({
  period: periodOrPeriodOperator,
  variable
})

function main (fileContent) {
  const node = JSON.parse(fileContent)
  const schema = Array.isArray(node) ? arrayOf(variable) : variable
  const result = normalize(node, schema)
  console.log(JSON.stringify(result, null, 2))
}

if (process.argv.length < 3 || !process.argv[2]) {
  let fileContent = ''
  process.stdin.setEncoding('utf8')
  process.stdin.on('readable', () => {
    var chunk = process.stdin.read()
    if (chunk !== null) {
      fileContent += chunk
    }
  })
  process.stdin.on('end', () => {
    main(fileContent)
  })
} else {
  if (process.argv.length > 3) {
    throw new Error('Provide a single file path')
  }
  const filePath = process.argv[2]
  const fileContent = fs.readFileSync(filePath)
  main(fileContent)
}
