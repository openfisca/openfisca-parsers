import {Schema, arrayOf, unionOf, valuesOf} from 'normalizr'

export const ArithmeticOperator = new Schema('ArithmeticOperator')
export const Number = new Schema('Number')
export const Parameter = new Schema('Parameter')
export const ParameterAtInstant = new Schema('ParameterAtInstant')
export const Period = new Schema('Period')
export const PeriodOperator = new Schema('PeriodOperator')
export const Variable = new Schema('Variable')
export const VariableForPeriod = new Schema('VariableForPeriod')

export const expression = unionOf({
  ArithmeticOperator,
  Number,
  Parameter,
  ParameterAtInstant,
  VariableForPeriod
}, {schemaAttribute: 'type'})

export const periodOrPeriodOperator = unionOf({
  Period,
  PeriodOperator
}, {schemaAttribute: 'type'})

const pyvariable = unionOf({
  ArithmeticOperator,
  Number,
  Parameter,
  ParameterAtInstant,
  Period,
  PeriodOperator,
  VariableForPeriod
}, {schemaAttribute: 'type'})

ArithmeticOperator.define({
  operands: arrayOf(expression)
})

ParameterAtInstant.define({
  instant: PeriodOperator,
  parameter: Parameter
})

PeriodOperator.define({
  operand: periodOrPeriodOperator
})

Variable.define({
  formula: expression,
  output_period: periodOrPeriodOperator,
  _pyvariables: valuesOf(pyvariable)
})

VariableForPeriod.define({
  period: periodOrPeriodOperator,
  variable: Variable
})
