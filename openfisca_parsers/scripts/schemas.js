import {Schema, arrayOf, unionOf as normalizrUnionOf, valuesOf} from 'normalizr'

export const ArithmeticOperator = new Schema('ArithmeticOperator')
export const Constant = new Schema('Constant')
export const Parameter = new Schema('Parameter')
export const ParameterAtInstant = new Schema('ParameterAtInstant')
export const Period = new Schema('Period')
export const PeriodOperator = new Schema('PeriodOperator')
export const Variable = new Schema('Variable')
export const ValueForEntity = new Schema('ValueForEntity')
export const ValueForPeriod = new Schema('ValueForPeriod')
export const ValueForRole = new Schema('ValueForRole')

function unionOf (obj) {
  return normalizrUnionOf(obj, {schemaAttribute: 'type'})
}

export const formula = unionOf({
  ArithmeticOperator,
  Constant,
  ParameterAtInstant,
  ValueForEntity,
  ValueForPeriod,
  ValueForRole
})

export const periodOrPeriodOperator = unionOf({
  Period,
  PeriodOperator
})

const pyvariable = unionOf({
  ArithmeticOperator,
  Constant,
  Parameter,
  ParameterAtInstant,
  Period,
  PeriodOperator,
  ValueForEntity,
  ValueForPeriod,
  ValueForRole
})

ArithmeticOperator.define({
  operands: arrayOf(formula)
})

ParameterAtInstant.define({
  instant: PeriodOperator,
  parameter: Parameter
})

PeriodOperator.define({
  operand: periodOrPeriodOperator
})

Variable.define({
  formula,
  output_period: periodOrPeriodOperator,
  _pyvariables: valuesOf(pyvariable)
})

ValueForEntity.define({
  variable: ValueForPeriod
})

ValueForPeriod.define({
  period: periodOrPeriodOperator,
  variable: Variable
})

ValueForRole.define({
  variable: ValueForPeriod
})
