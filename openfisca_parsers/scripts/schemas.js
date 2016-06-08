import {Schema, arrayOf, unionOf as normalizrUnionOf, valuesOf} from 'normalizr'

export const ArithmeticOperator = new Schema('ArithmeticOperator')
export const Number = new Schema('Number')
export const Parameter = new Schema('Parameter')
export const ParameterAtInstant = new Schema('ParameterAtInstant')
export const Period = new Schema('Period')
export const PeriodOperator = new Schema('PeriodOperator')
export const Variable = new Schema('Variable')
export const ValueForPeriod = new Schema('ValueForPeriod')
export const ValueForRole = new Schema('ValueForRole')

function unionOf (obj) {
  return normalizrUnionOf(obj, {schemaAttribute: 'type'})
}

export const formula = unionOf({
  ArithmeticOperator,
  Number,
  ParameterAtInstant,
  ValueForPeriod,
  ValueForRole
})

export const periodOrPeriodOperator = unionOf({
  Period,
  PeriodOperator
})

const pyvariable = unionOf({
  ArithmeticOperator,
  Number,
  Parameter,
  ParameterAtInstant,
  Period,
  PeriodOperator,
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

ValueForPeriod.define({
  period: periodOrPeriodOperator,
  variable: unionOf({Variable, ValueForRole})
})

ValueForRole.define({
  variable: unionOf({Variable, ValueForPeriod})
})
