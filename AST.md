# OpenFisca AST nodes spec

## General

```json
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "type": "object",
  "properties": {
    "_id": { "type": "integer" },
    "_stub": { "type": "boolean" },
    "type": {
      "type": "string",
      "enum": ["Parameter", "Period", "PeriodOperator", "ArithmeticOperator", "Number", "Variable"],
      "description": "The operator in the AST, not the node output data type."
    }
  },
  "required": [
    "_id",
    "type"
  ]
}
```
