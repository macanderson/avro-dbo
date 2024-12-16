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
    py_type = f.type

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
                if val_extra:
                    val_obj = {"type": val_type, **val_extra}
                else:
                    val_obj = val_type
                values_type = val_obj
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
            type_obj = {"type": field_type}
            type_obj.update(extra)
        else:
            type_obj = field_type

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


def make_avro_schema(cls: Type, name: Optional[str]=None, namespace: Optional[str]=None, 
                    doc: Optional[str]=None, type: str='record') -> Dict:
    """Generate Avro schema from attrs class.
    
    Args:
        cls: @attrs.define decorated class, the model class to convert
        name: str, Optional schema name
        namespace: str, Optional schema namespace
        doc: str, Optional schema documentation
        type: str, Schema Type, defaults to 'record'
        
    Returns:
        Dict containing complete Avro schema
    """
    name = name or cls.__name__
    namespace = namespace or cls.__module__
    doc = doc or getattr(cls, "__doc__", None)
    field_schemas = [make_field_schema(f) for f in attrs.fields(cls)]
    schema = {
        "type": "record",
        "name": name,
        "namespace": namespace,
        "fields": field_schemas
    }
    if doc:
        schema["doc"] = doc.strip()
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

def avro_schema(cls: Type) -> Type:
    """Decorator to add Avro schema capabilities to attrs classes.
    
    Args:
        cls: attrs.define decorated class to decorate
        
    Returns:
        Decorated class with Avro schema capabilities
    """
    original_fields = attrs.fields(cls)
    changed = False
    new_attributes = {}

    # Add schema properties with override capability
    @property  # type: ignore # we know what we're doing
    def avro_schema_name(self):
        return getattr(self, '__avro_name__', self.__class__.__name__)
    
    @avro_schema_name.setter
    def avro_schema_name(self, value):
        self.__avro_name__ = value
    
    @property  # type: ignore # we know what we're doing
    def avro_schema_namespace(self):
        return getattr(self, '__avro_namespace__', self.__class__.__module__)
    
    @avro_schema_namespace.setter
    def avro_schema_namespace(self, value):
        self.__avro_namespace__ = value or self.__class__.__module__
    
    @property # type: ignore # we know what we're doing
    def avro_schema_doc(self):
        return getattr(self, '__avro_doc__', self.__class__.__doc__)
    
    @avro_schema_doc.setter  # type: ignore # we know what we're doing
    def avro_schema_doc(self, value):
        self.__avro_doc__ = value or self.__class__.__doc__
        
    @property  # type: ignore # we know what we're doing
    def avro_schema_type(self):
        return getattr(self, '__avro_type__', 'record')
    

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
            # Use on_setattr=attrs.setters.convert to ensure runtime assignments also get converted
            new_f = attrs.field(
                init=f.init,
                repr=f.repr,
                hash=f.hash,
                eq=f.eq,
                order=f.order,
                kw_only=f.kw_only,
                on_setattr=attrs.setters.convert,  # ensure converter runs on assignment
                converter=combined_converter,
                validator=f.validator,
                metadata=metadata,
                **default_arg
            )
            changed = True
        else:
            # Just replicate the field
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
        @property  # type: ignore # we know what we're doing
        def avro_schema_property(self):
            return make_avro_schema(
                type(self), 
                name=self.avro_schema_name, 
                namespace=self.avro_schema_namespace,
                doc=self.avro_schema_doc or 'No documentation provided.',
                type=self.avro_schema_type or 'record'
            )
        
        cls.avro_schema = avro_schema_property  # type: ignore
        return cls

    # Remove unsupported arguments like module or inherited.
    # We'll just use name, new_attributes, bases and auto_attribs.
    new_cls = attrs.make_class(
        cls.__name__,
        new_attributes,
        bases=cls.__bases__,
        auto_attribs=False
    )
    new_cls.__doc__ = cls.__doc__

    @property  # type: ignore # we know what we're doing
    def avro_schema_property(self):
        return make_avro_schema(type(self))

    def export_schema(self, filename: Optional[str] = None) -> None:
        """Export schema to file.
        
        Args:
            filename: Optional filename, defaults to schema name + .avsc
        """
        filename = filename or self.__class__.__name__ + '.avsc'
        schema = make_avro_schema(
            type(self), 
            name=self.__class__.__name__,
            namespace=self.__class__.__module__,
            doc=self.__class__.__doc__,
            type='record'
        )
        with open(filename, "w") as f:
            json.dump(schema, f, indent=2)

    # ignore the type errors because we know what we're doing
    new_cls.export_avro_schema = export_schema  # type: ignore
    new_cls.avro_schema = avro_schema_property  # type: ignore
    return new_cls


# Example usage:
if __name__ == "__main__":

    # Example Usage
    # 1. define the model with @define from attrs
    # 2. add the avro_schema decorator
    # 3. add the field with the metadata
    # 4. create an instance of the model
    # 5. print the instance
    # 6. print the avro schema

    @avro_schema
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
    m.export_avro_schema()  # type: ignore
    print(">>>> \n\n")
    print("Avro Schema:", json.dumps(m.avro_schema, indent=2))  # type: ignore
    print(">>>> \n\n")

__all__ = ['avro_schema']
