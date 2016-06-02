
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

const formula = unionOf({
  ArithmeticOperator: arithmeticOperator
}, {schemaAttribute: 'type'})

const operand = unionOf({
  ArithmeticOperator: arithmeticOperator,
  Number: number,
  Parameter: parameter,
  ParameterAtInstant: parameterAtInstant,
  VariableForPeriod: variableForPeriod
}, {schemaAttribute: 'type'})

arithmeticOperator.define({
  operands: arrayOf(operand)
})

parameterAtInstant.define({
  instant: periodOperator,
  parameter
})

periodOperator.define({
  operand: period
})

variable.define({
  formula,
  output_period: period
})

variableForPeriod.define({
  variable
})

function main (fileContent) {
  const node = JSON.parse(fileContent)
  const result = normalize(node, arrayOf(variable))
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
