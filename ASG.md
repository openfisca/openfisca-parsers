#  Abstract Semantic Graph spec

These are the OpenFisca ASG node types.
These nodes make a (directed) graph and not a tree.

> Inspired from https://github.com/babel/babylon/blob/master/ast/spec.md


- [Node objects](#node-objects)
- [Identifier](#identifier)

# Node objects

ASG nodes are represented as `Node` objects, which may have any prototype inheritance but which implement the following interface:

```js
interface Node {
  type: string;
}
```

The `type` field is a string representing the ASG variant type. Each subtype of `Node` is documented below with the specific string of its `type` field. You can use this field to determine which interface a node implements.

# Variable

```js
interface Variable <: Node {
  type: "Variable";
  name: string;
  label: string | null;
  docstring: string | null;
  value_type: ValueType;
  default_value: ?;
  entity: Entity;
  formula: Formula;
  is_period_size_independent: boolean;
  start_date: date;
  stop_date: date;
  input_period: Period;
  output_period: Period;
}
```

An OpenFisca simulation variable.

## Entity

```js
enum Entity {
  "famille" | "foyer_fiscal" | "individus" | "menage"
}
```

## ValueType

```js
enum ValueType {
  "age" | "float" | "int"
}
```

## Formula

```js
interface Formula <: ArithmeticOperation, Constant, ParameterAtInstant, ValueForEntity, ValueForPeriod, ValueForRole { }
```

# Constant

```js
interface Constant <: Node {
  type: "Constant";
  value: number;
}
```

# Period

```js
interface Period <: Node {
  type: "Period";
}
```

# PeriodOperation

```js
interface PeriodOperation <: Node {
  type: "PeriodOperation";
  operator: PeriodOperationOperator;
  operand: PeriodOperationOperand;
}
```

## PeriodOperationOperator

```js
enum PeriodOperationOperator {
  "this_year" | "last_year"
}
```

## PeriodOperationOperand

```js
interface PeriodOperationOperand <: Period, Instant { }
```

# Instant

```js
interface Instant <: PeriodOperation { }
```

# Parameter

```js
interface Parameter <: Node {
  type: "Parameter";
  path: [ string ];
}
```

# ParameterAtInstant

```js
interface ParameterAtInstant <: Node {
  type: "ParameterAtInstant";
  parameter: Parameter;
  instant: Instant;
}
```

# ValueForEntity

```js
interface ValueForEntity <: Node {
  type: "ValueForEntity";
  operator: ValueForEntityOperator;
  variable: Variable;
}
```

## ValueForEntityOperator

```js
enum ValueForEntityOperator {
  "sum"
}
```

# ValueForRole

```js
interface ValueForRole <: Node {
  type: "ValueForRole";
  role: Role;
  variable: Variable;
}
```

## Role

```js
enum Role {
  "VOUS" | "CONJ"
}
```

# ValueForPeriod

```js
interface ValueForPeriod <: Node {
  type: "ValueForPeriod";
  period: Period;
  variable: Variable;
}
```

# Arithmetic Operations

## ArithmeticOperation

```js
interface ArithmeticOperation <: Node {
  type: "ArithmeticOperation";
  operator: ArithmeticOperationOperator;
}
```

### ArithmeticOperationOperator

```js
enum ArithmeticOperationOperator {
  "sum" | "product" | "negate"
}
```

## SumArithmeticOperation

```js
interface SumArithmeticOperation <: ArithmeticOperation {
  operator: "sum";
  operands: [ Formula ];
}
```

## ProductArithmeticOperation

```js
interface ProductArithmeticOperation <: ArithmeticOperation {
  operator: "product";
  operands: [ Formula ];
}
```

## NegateArithmeticOperation

```js
interface NegateArithmeticOperation <: ArithmeticOperation {
  operator: "negate";
  operand: Formula;
}
```

# PythonVariableDeclaration

```js
interface PythonVariableDeclaration <: Node {
  type: "PythonVariableDeclaration";
  name: string;
  value: PythonVariableValue;
}
```

## PythonVariableValue

```js
interface PythonVariableValue <: ArithmeticOperation, Constant, Parameter, ParameterAtInstant, Period, PeriodOperation, ValueForEntity, ValueForPeriod, ValueForRole { }
```
