import {Schema, arrayOf, unionOf as normalizrUnionOf} from 'normalizr'

export const ArithmeticOperation = new Schema('ArithmeticOperation')
export const Constant = new Schema('Constant')
export const Module = new Schema('Module')
export const Parameter = new Schema('Parameter')
export const ParameterAtInstant = new Schema('ParameterAtInstant')
export const Period = new Schema('Period')
export const PeriodOperation = new Schema('PeriodOperation')
export const Variable = new Schema('Variable')
export const ValueForEntity = new Schema('ValueForEntity')
export const ValueForPeriod = new Schema('ValueForPeriod')
export const ValueForRole = new Schema('ValueForRole')

function unionOf (obj) {
  return normalizrUnionOf(obj, {schemaAttribute: 'type'})
}

export const formula = unionOf({
  ArithmeticOperation,
  Constant,
  ParameterAtInstant,
  ValueForEntity,
  ValueForPeriod,
  ValueForRole
})

export const periodOrPeriodOperation = unionOf({
  Period,
  PeriodOperation
})

export const pyvariable = unionOf({
  ArithmeticOperation,
  Constant,
  Parameter,
  ParameterAtInstant,
  Period,
  PeriodOperation,
  ValueForEntity,
  ValueForPeriod,
  ValueForRole
})

export const variables = arrayOf(Variable)

ArithmeticOperation.define({
  operands: arrayOf(formula)
})

Module.define({
  variables
})

ParameterAtInstant.define({
  instant: PeriodOperation,
  parameter: Parameter
})

PeriodOperation.define({
  operand: periodOrPeriodOperation
})

Variable.define({
  formula,
  output_period: periodOrPeriodOperation
  // _pyvariables: valuesOf(pyvariable)
})

ValueForEntity.define({
  variable: unionOf({ValueForPeriod, ValueForRole})
})

ValueForPeriod.define({
  period: periodOrPeriodOperation,
  variable: Variable
})

ValueForRole.define({
  variable: ValueForPeriod
})
