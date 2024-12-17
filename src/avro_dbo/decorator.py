# Licensed under the Apache License, Version 2.0 (the "License");
# ...
# Attribution: The Unnatural Group, LLC, Tradesignals project

"""Avro schema decorator for attrs classes.

This module provides decorators and utilities for converting Python classes using attrs
into Avro schema compatible objects, with special handling for decimal types.

## Features:

- Automatically quantizes decimals to the scale of the field when assigned.
- Automatically updates the schema to reflect the quantized value.
- Supports all Avro primitives and logical types.
- Handles decimals to scale and quantize them to the scale of the field when assigned.
- Supports nested types, enums, maps, fixed, and unions.
- Supports default values, including factory functions.
- Supports docstrings and type hints.

## Example Usage:

1. define the model with @define from attrs
2. add the avro_schema decorator
3. add the field with the metadata
4. create an instance of the model
5. print the instance
6. print the avro schema

### `@avro_schema` Decorator Properties:
- name: str (name of the schema) - defaults to the class name
- namespace: str (namespace of the schema) - defaults to the module name
- doc: str (documentation of the schema) - defaults to the class docstring
- type: str (type of the schema) - defaults to 'record'

```python
@avro_schema(name="ExampleModel", namespace="com.example", doc="Example model with decimal fields")
@attrs.define
class ExampleModel:
    scaled_decimal: Decimal = attrs.field(
        default=Decimal("123.4567"),
        metadata={
            "logicalType": "decimal",
            "precision": 6,
            "scale": 2
        }
    )
```
#### Create an instance of the model:
>>> `m = ExampleModel()`
>>> `print(m.scaled_decimal)`
# Decimal('123.46') (quantized to scale=2)

#### Assign a value to the field:
>>> `m.scaled_decimal = Decimal("999.123456789")`
>>> `print(m.scaled_decimal)`
# Decimal('999.12') (quantized to scale=2)


# The schema is updated to reflect the quantized value.
>>> `print(m.avro_schema)`

{
  "type": "record",
  "name": "ExampleModel",
  "namespace": "com.example",
  "fields": [
    {
      "name": "scaled_decimal", 
#       "type": {
#         "type": "bytes", 
        "logicalType": "decimal", 
        "precision": 6,
        "scale": 2
      }
    }
  ]
}
"""

import json
from decimal import Decimal
from typing import Dict, Optional, Tuple, get_args, get_origin, Type
import attrs

converter_cache: Dict = {}

AVRO_PRIMITIVES: Dict[Type, str] = {
    str: "string",
    int: "int", 
    float: "float",
    bool: "boolean",
    bytes: "bytes"
}

LOGICAL_TYPE_BASE: Dict[str, str] = {
    "decimal": "bytes",
    "timestamp-millis": "long",
    "timestamp-micros": "long", 
    "timestamp-nanos": "long",
    "date": "int",
    "time-millis": "int",
    "time-micros": "long",
    "time-nanos": "long"
}

def infer_avro_type(py_type: Type, metadata: Dict) -> Tuple[str, Dict]:
    """Infer Avro type from Python type and metadata.
    
    Args:
        py_type: Python type to convert
        metadata: Field metadata dictionary
        
    Returns:
        Tuple of (avro_type, extra_attributes)
        
    Raises:
        ValueError: If type cannot be converted to Avro
    """
    logical_type = metadata.get("logicalType") or metadata.get("logical_type")
    extra: Dict = {}
    if logical_type:
        if logical_type not in LOGICAL_TYPE_BASE:
            raise ValueError(f"Unsupported logicalType: {logical_type}")
        base = LOGICAL_TYPE_BASE[logical_type]
        extra["logicalType"] = logical_type

        if logical_type == "decimal":
            if "precision" not in metadata or "scale" not in metadata:
                raise ValueError("Decimal logicalType requires precision and scale")
            extra["precision"] = metadata["precision"]
            extra["scale"] = metadata["scale"]
        return base, extra

    if "type" in metadata:
        avro_type = metadata["type"]
        return avro_type, extra

    if py_type == Decimal:
        raise ValueError("Decimal fields must specify logicalType=decimal and precision/scale in metadata.")

    origin = get_origin(py_type)
    if origin is list:
        return "array", extra
    if origin is dict:
        return "map", extra

    primitive = AVRO_PRIMITIVES.get(py_type)
    if primitive is None:
        raise ValueError(f"Unsupported Python type {py_type} for Avro schema.")
    return primitive, extra


def make_field_schema(f: attrs.Attribute) -> Dict:
    """Convert an attrs field to Avro field schema.
    
    Args:
        f: attrs.Attribute field to convert
        
    Returns:
        Dict containing Avro field schema
        
    Raises:
        ValueError: If field cannot be converted
    """
    metadata = f.metadata or {}
    py_type = f.type or type(None)

    field_name = metadata.get("alias", f.name)
    doc = metadata.get("doc")
    default_val = None
    if f.default is not attrs.NOTHING:
        default_val = f.default

    field_type, extra = infer_avro_type(py_type, metadata)

    if field_type == "array":
        if "items" in metadata:
            items_type = metadata["items"]
        else:
            args = get_args(py_type)
            if args and len(args) == 1:
                item_py_type = args[0]
                item_type, item_extra = infer_avro_type(item_py_type, {})
                if item_extra:
                    items_type = {"type": item_type, **item_extra}
                else:
                    items_type = item_type
            else:
                raise ValueError(f"Array field {f.name} requires 'items' or a simple generic type.")
        type_obj = {"type": "array", "items": items_type}

    elif field_type == "enum":
        if "symbols" not in metadata:
            raise ValueError(f"Enum field {f.name} requires 'symbols'.")
        type_obj = {"type": "enum", "symbols": metadata["symbols"]}

    elif field_type == "map":
        if "values" in metadata:
            values_type = metadata["values"]
        else:
            args = get_args(py_type)
            if args and len(args) == 2:
                val_type, val_extra = infer_avro_type(args[1], {})
                val_obj = {"type": val_type, **val_extra} if val_extra else {"type": val_type}
            else:
                raise ValueError(f"Map field {f.name} requires 'values' or a dict type with value hint.")
        type_obj = {"type": "map", "values": values_type}

    elif field_type == "fixed":
        if "size" not in metadata:
            raise ValueError(f"Fixed field {f.name} requires 'size'.")
        type_obj = {"type": "fixed", "size": metadata["size"]}

    elif field_type == "union":
        if "types" not in metadata:
            raise ValueError(f"Union field {f.name} requires 'types'.")
        type_obj = metadata["types"]

    else:
        if extra:
            type_obj = {"type": field_type, **extra}
        else:
            type_obj = {"type": field_type}

    field_schema = {"name": field_name, "type": type_obj}
    if doc:
        field_schema["doc"] = doc
    if default_val is not None:
        # If decimal, store default as string
        if isinstance(type_obj, dict) and type_obj.get("logicalType") == "decimal":
            default_val = str(default_val)
        if isinstance(default_val, Decimal):
            default_val = str(default_val)
        field_schema["default"] = default_val

    return field_schema


def make_avro_schema(
        cls: Type,
        name: Optional[str] = None, 
        namespace: Optional[str] = None, 
        doc: Optional[str] = None, 
        schema_type: str = 'record',
        **kwargs
    ) -> Dict:
    """Generate Avro schema from attrs class, allowing overrides via kwargs.
    
    Args:
        cls: @attrs.define decorated class, the model class to convert
        name: Optional schema name, overridden by kwargs
        namespace: Optional schema namespace, overridden by kwargs
        doc: Optional schema documentation, overridden by kwargs
        schema_type: Schema Type, defaults to 'record', overridden by kwargs
        
    Returns:
        Dict containing complete Avro schema
    """
    schema = {
        "type": kwargs.get("type", schema_type),
        "name": kwargs.get("name", name or cls.__name__),
        "namespace": kwargs.get("namespace", namespace or cls.__module__),
        "fields": [make_field_schema(f) for f in attrs.fields(cls)]
    }
    schema_doc = kwargs.get("doc", doc or getattr(cls, "__doc__", None))
    if schema_doc:
        schema["doc"] = schema_doc.strip()
    return schema


def quantize_decimal_converter(scale: int):
    """Create a converter function for decimal quantization.
    
    Args:
        scale: Number of decimal places
        
    Returns:
        Function that quantizes decimals to specified scale
    """
    quant = Decimal(10) ** (-scale)
    def conv(val):
        if val is None:
            return None
        val = Decimal(val)
        return val.quantize(quant)
    return conv

def avro_schema(cls: Type = None, **kwargs) -> Type:
    """Decorator to add Avro schema capabilities to attrs classes, allowing schema customization.
    
    Args:
        cls: attrs.define decorated class to decorate
        **kwargs: Keyword arguments for schema customization such as name, namespace, etc.
        
    Returns:
        Decorated class with Avro schema capabilities
    """
    def wrapper(cls):
        original_fields = attrs.fields(cls)
        changed = False
        new_attributes = {}

        for f in original_fields:
            metadata = f.metadata or {}
            default_arg = {}
            if f.default is not attrs.NOTHING:
                if isinstance(f.default, attrs.Factory):
                    default_arg['factory'] = f.default.factory
                else:
                    default_arg['default'] = f.default

            # Check if it's decimal
            if metadata.get("logicalType") == "decimal":
                scale = metadata["scale"]
                user_converter = f.converter
                
                def combined_converter(x, user_converter=user_converter, scale=scale):
                    x = user_converter(x) if user_converter else x
                    return quantize_decimal_converter(scale)(x)
                
                new_f = attrs.field(
                    init=f.init,
                    repr=f.repr,
                    hash=f.hash,
                    eq=f.eq,
                    order=f.order,
                    kw_only=f.kw_only,
                    on_setattr=attrs.setters.convert,
                    converter=combined_converter,
                    validator=f.validator,
                    metadata=metadata,
                    **default_arg
                )
                changed = True
            else:
                new_f = attrs.field(
                    init=f.init,
                    repr=f.repr,
                    hash=f.hash,
                    eq=f.eq,
                    order=f.order,
                    kw_only=f.kw_only,
                    on_setattr=f.on_setattr,
                    converter=f.converter,
                    validator=f.validator,
                    metadata=metadata,
                    **default_arg
                )

            new_attributes[f.name] = new_f

        if not changed:
            @property
            def avro_schema_property(self):
                return make_avro_schema(
                    type(self), 
                    **kwargs
                )
            
            cls.avro_schema = avro_schema_property
            return cls

        new_cls = attrs.make_class(
            cls.__name__,
            new_attributes,
            bases=cls.__bases__,
            auto_attribs=False
        )
        new_cls.__doc__ = cls.__doc__

        @property
        def avro_schema_property(self):
            return make_avro_schema(
                type(self),
                **kwargs
            )

        @classmethod
        def export_schema(cls, filename: str):
            """Export the Avro schema to a file.
            
            Args:
                filename: str, the filename to export the schema to
            """
            schema = make_avro_schema(cls, **kwargs)
            with open(filename, "w") as file:
                json.dump(schema, file)
            return schema

        new_cls.avro_schema = avro_schema_property
        new_cls.export_schema = export_schema
        return new_cls

    if cls is None:
        return wrapper
    else:
        return wrapper(cls)


# Example usage:
if __name__ == "__main__":

    # Example Usage
    # 1. define the model with @define from attrs
    # 2. add the avro_schema decorator
    # 3. add the field with the metadata
    # 4. create an instance of the model
    # 5. print the instance
    # 6. print the avro schema

    @avro_schema(
        name="Custo1111mName",
        schema_type="record", 
        namespace='com.namespace.com'
    )
    @attrs.define
    class ExampleModel:
        """Model with decimal automatically quantized."""
        
        field1: Decimal = attrs.field(
            default=Decimal("123.4567"),
            metadata={
                "logicalType": "decimal",
                "precision": 6,
                "scale": 2
            }
        )
        field2: Decimal = attrs.field(
            default=Decimal("10.999"),
            metadata={
                "logicalType": "decimal",
                "precision": 5,
                "scale": 3
            }
        )

    m = ExampleModel()
    print("Initially:", m.field1, m.field2)  # Should be quantized
    m.field1 = Decimal("999.9999")
    print("After assignment:", m.field1)  # Should quantize to scale=2 -> 1000.00
    m.field2 = Decimal("10.123456")
    print("After assignment:", m.field2)  # Scale=3 -> 10.123
    print("\n\n <<<<<<AVRO SCHEMA PRINT >>>>>> \n\n")
    print("Avro Schema:", json.dumps(m.avro_schema, indent=2))  # type: ignore
    print(">>>> \n\n")
    m.export_schema('schema.json')  # type: ignore
    print(">>>> \n\n")
    print("Avro Schema:", json.dumps(m.avro_schema, indent=2))  # type: ignore
    print(">>>> \n\n")

__all__ = ['avro_schema']
