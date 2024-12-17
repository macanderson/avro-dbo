# **Avro DBO 🚀**

[![PyPI version](https://badge.fury.io/py/avro-dbo.svg)](https://badge.fury.io/py/avro-dbo)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/avro-dbo.svg)](https://pypi.org/project/avro-dbo/)

**Avro DBO** is a robust Python library designed for handling Apache **Avro** schemas. It facilitates seamless data serialization and schema management, making it ideal for data engineering pipelines and stream processing applications.

## ✨ **Features**

- 🏗️ **Schema-First Development**: Generate Python classes from Avro schemas.
- 🔄 **Full Type Support**: Supports all Avro logical types including arrays and enums.
- 🛠️ **Custom Serialization**: Offers flexible serializers and deserializers.
- 🌐 **Schema Registry Integration**: Integrates natively with Confluent Schema Registry.
- 🔒 **Type Safety**: Ensures full static type checking.
- ⚡ **High Performance**: Optimized for high-load production environments.

## 🚀 Quick Start

**Step 1: Install from PyPI**

```python
pip install avro-dbo
```

**Step 2: Import attrs and avro_dbo**
Import the `attrs` and `avro_dbo` modules.

For more information on using `attrs`, visit the [attrs documentation](https://www.attrs.org/).


```python
from attrs import field, define
from avro_dbo import avro_schema
```

**Step 3: Define your schema**
Defining your schema is optional.  If you don't define a schema, the class will be created without any schema metadata.

```python
@define
@avro_schema(
    name="OverrideNameOptional",  # optional overrides inherits from the class name
    namespace="OverrideNamespaceOptional",  # optional overrides inherits from the class namespace
    type="record",  # optional overrides inherits from the class type
    doc="OverrideDocOptional"  # optional overrides inherits from the class doc
)
class DecimalModel:
    amount: Decimal = field(
        default=Decimal("100.00"),
        metadata={
            "logicalType": "decimal",
            "precision": 10,
            "scale": 2
        }
    )
```

**Step 4: Use your schema**

```python
my_model = DecimalModel()
print(my_model.amount)
# > Decimal("100.00")
# extra precision is truncated to the scale
my_model.amount = Decimal("100.00383889328932")
print(my_model.amount)
    # > Decimal("100.00")

# values are validated and coerced to the correct type
# against the defined schema rules!
```

### **Avro Primitive and Logical Types Supported**

At this time all Avro logical types are supported.  Avro DBO will automatically coerce the values to the correct type and scale.

**Avro Logical Types Supported**
- `decimal`
- `date`
- `time-millis`
- `timestamp-millis`
- `uuid`
- `fixed`
- `enum`
- `array`
- `map`
- `union`
- `error`

**Avro Primitive Types Supported**
- `string`
- `bytes`
- `int`
- `long`
- `float`
- `double`

#### **`decimal` Type**

`decimal.Decimal` are automatically coerced to the correct type and scale.  Avro DBO quantizes the precision to the scale of the field everytime the field is set in any instance of the attrs.define decorated class.

```python
from attrs import field, define
from decimal import Decimal

@define
@avro_schema
class DecimalModel:
    amount: Decimal = field(
        default=Decimal("100.00"),
        metadata={
            "logicalType": "decimal",
            "precision": 10,
            "scale": 2
        }
    )
```

#### **`timestamp-millis` and `time-millis` and `date` Type**
Timestamps are automatically coerced to the correct type (`datetime.datetime` and `datetime.date`).

All python datetime, date, and time types are supported.

The values serialize and deserialize to the correct type `long` (milliseconds since the epoch), or `int` (milliseconds since the epoch) for `date` types.

```python
from attrs import field, define
import datetime

@define
@avro_schema
class TimestampModel:
    created_at: datetime.datetime = field(
        metadata={
            "logicalType": "timestamp-millis"
        }
    )
```

#### **`enum` Type**
Enums are supported and will be serialized to the correct type.

```python
from attrs import field, define
from enum import Enum

class Status(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

@define
@avro_schema
class EnumModel:
    status: Status = field(
        default=Status.ACTIVE,
        metadata={
            "logicalType": "enum",
            "symbols": list(Status)
        }
    )
```

**This produces the following schema:**

```json
{
  "type": "record",
  "name": "EnumModel",
  "fields": [{"name": "status", "type": "enum", "symbols": ["ACTIVE", "INACTIVE"]}]
}
```

#### **`array` Type**
```python
from attrs import field, define
from typing import List

@define
@avro_schema
class ArrayModel:
    tags: List[str] = field(
        factory=list,
        metadata={
            "logicalType": "array",
            "items": "string"
        }
    )
```

#### **Kitchen Sink Example**
The following example demonstrates all the supported types and logical types.

```python
from attrs import field, define
from decimal import Decimal
from enum import Enum
from typing import List
import datetime

class Status(Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

@define
@avro_schema
class KitchenSinkModel:
    name: str = field(default="")
    amount: Decimal = field(
        default=Decimal("999.99"),
        metadata={
            "logicalType": "decimal",
            "precision": 10,
            "scale": 2
        }
    )
    status: Status = field(
        default=Status.ACTIVE,
        metadata={
            "logicalType": "enum",
            "symbols": list(Status)
        }
    )
    created_at: datetime.datetime = field(
        metadata={
            "logicalType": "timestamp-millis"
        }
    )
    tags: List[str] = field(
        factory=list,
        metadata={
            "logicalType": "array",
            "items": "string"
        }
    )
```
### **Example Avro Schema Output**

You can use the `export_schema()` method to export the schema as a JSON object.

#### **Running the Example**

```python
# ... import the KitchenSinkModel class
print(KitchenSinkModel.export_schema())
```

The result will be a JSON object that can be used to define the schema in a Confluent Schema Registry.


#### **Example Avro Schema Output**

```json
{
  "type": "record",
  "name": "KitchenSinkModel",
  "fields": [
    {"name": "name", "type": "string", "default": ""},
    {"name": "amount", "type": "decimal", "precision": 10, "scale": 2},
    {"name": "status", "type": "enum", "symbols": ["ACTIVE", "INACTIVE"]},
    {"name": "created_at", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "tags", "type": "array", "items": "string"}
  ]
}
```

### **Saving an Avro Schema to a File**

You can use the `export_schema()` method to export the schema as a JSON object.

`KitchenSinkModel.export_schema(filename="kitchen_sink_model.json")`

### **Coercing a Python Class Using Avro Schema Model**

Avro-DBO will coerce automnatically all fields in the schema to the correct type.

Avro to datetime, date, decimal, enum, array, and more.

#### **Example with `decimal.Decimal`**

```python
from attrs import field, define
from decimal import Decimal

@define
@avro_schema
class DecimalModel:
    amount: Decimal = field(
        default=Decimal("100.00"),
        metadata={
            "logicalType": "decimal",
            "precision": 10,
            "scale": 2
        }
    )

my_model = DecimalModel()
print(my_model.amount)
# > Decimal("100.00")
# extra precision is truncated to the scale
my_model.amount = Decimal("100.00383889328932")
print(my_model.amount)
# > Decimal("100.00")
```

<!-- ## 📚 Documentation

For detailed usage instructions, type hints, and comprehensive examples, please refer to our [documentation](https://avro-dbo.readthedocs.io/en/latest/). -->
## Additional Information

The following links are useful for more information on the project.

- [Documentation](https://avro-dbo.readthedocs.io/en/latest/)
- [GitHub Repository](https://github.com/mac-anderson/avro-dbo)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [LICENSE](LICENSE)

### 🤝 Contributing

We welcome contributions! To submit issues or propose changes, please visit our [GitHub repository](https://github.com/mac-anderson/avro-dbo). See the [CONTRIBUTING.md](CONTRIBUTING.md) file for more information on how to contribute.

### 📜 License

This project is licensed under the `Apache 2.0 License` - see the [LICENSE](LICENSE) file for details.

### About Mac Anderson (Author)

Avro DBO was created and is maintained by [Mac Anderson](https://github.com/mac-anderson). For more insights into my other projects, visit [Mac Anderson's GitHub](https://github.com/mac-anderson).

For additional information on my professional work, explore [Tradesignals](https://tradesignals.ai) and connect with me on [LinkedIn](https://www.linkedin.com/in/macanderson/).

Thank you!

-- _Mac Anderson_
