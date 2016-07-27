#  Raw Graph spec

A raw graph is what is derived directly from the parsing of OpenFisca python/numpy source code. Some constructs are still dependent to the python/numpy code and should be abstracted to produce an abstract OpenFisca graph.

Here is the specification of the OpenFisca raw graph nodes.

- [Node objects](#node-objects)
- ...


# Typing in OpenFisca

Several typing systems are complementary in an OpenFisca graph.

## OpenFisca Type

The result of a computation can be of any of the following types :
* period
* instant
* value : have a entity type and a value type
* period-dependent value : have a entity type and a value type. A period-dependent value can be computed over a period to generate a value.
* instant-dependant value : have a entity type and a value type. A instant-dependent value can be computed at an instant to generate a value.

Because any node type constrains the OpenFisca types, the latter are implicit.

## Node Type

OpenFisca nodes have several types specifying several behaviors. These types can be :
* `Variable`
* `Constant`
* `Period`
* `PeriodOperation`
* `Instant`
* `PeriodToInstant`
* `InstantOperation`
* `Parameter`
* `ParameterAtInstant`
* `ValueForEntity`
* `ValueForRole`
* `ValueForPeriod`
* `ArithmeticOperation`
* `PythonVariableDeclaration`

Each node has a `type` attribute that declares its node type.

Node are strongly typed with relation to OpenFisca types.

## Value Type

A value, a time-dependant value or a parameter has a value type that can be :
* `age`
* `bool`
* `int`
* `float`

The value type is declared in the node.

## Entity Type

A value or a time-dependent value is binded to an entity :
* `individus`
* `foyer_fiscal`
* `famille`
* `menage`

The entity type is explicit for `Variable` nodes and implicit for other nodes.


# Node Types

## Variable

An OpenFisca simulation variable.

### fields

* type: "Variable"
* name: string
* label: string | null
* docstring: string | null
* value_type: value type
* default_value: ?
* entity: the entity type of the variable
* formula: node of same entity type, OpenFisca type and value type
* is_period_size_independent: boolean
* start_date: date;
* stop_date: date;
* input_period: `Period` node
* output_period: node of OpenFisca type period

TODO : add url

### OpenFisca type

**period-dependent value** if `is_period_size_independent` if false, **value** else


## Constant

### fields

* type: "Constant"
* value_type : value type

### OpenFisca type

value


## Period

Each `Variable` node has a field `input_period` pointing to a `Period` node.

### fields

* type: "Period"

### OpenFisca type

period


## PeriodOperation

### fields

* type: "PeriodOperation"
* operator: 'this_year' or 'last_year'
* operands: depending on the operator :
  * 'this_year' : a period node
  * 'last_year' : a period node

### OpenFisca type

period


## Instant

### fields

* type: "Instant"
* ...

### OpenFisca type

instant


## PeriodToInstant

### fields

* type: "PeriodToInstant"
* operator: 'start'
* operands: depending on the operator :
  * 'start' : a period node

### OpenFisca type

instant


## InstantOperation

### fields

* type: 'InstantOperation'
* operator: ...
* operands: depending on the operator :
  * ...

### OpenFisca type

instant


## Parameter

### fields

* type: "Parameter"
* path: [ string ]

### type

instant-dependent value


## ParameterAtInstant

### fields

* type: "ParameterAtInstant"
* parameter: an instant-dependent value : for the moment this can only be a parameter
* instant: an instant

### type

value


## SwitchEntity

Must involve the entity `individuals` as input or output.

Possible roles are :
* "VOUS", "CONJ" for `foyer_fiscal`
* ...
* ...

### fields

* type: "ValueForEntity"
* variable: `Variable` node
* input_entity : entity of variable
* output_entity : entity of the node
* role: parameter of the switch
* how: how results are aggregated, etc. :
  * 'sum' : all results are summed up

### OpenFisca type

same as variable


## ValueForPeriod

### fields

* type: "ValueForPeriod"
* period: period node
* variable: `Variable` node of type period-dependent value.

### OpenFisca type

value


## ArithmeticOperations

### fields

* type: "ArithmeticOperation"
* operator: "sum" | "product" | "negate"
* operands: list of value nodes

### OpenFisca type

value


## PythonVariableDeclaration

This node type is mainly used for debugging purposes.

### fields

* type: "PythonVariableDeclaration";
* name: string
* value: any kind of node
