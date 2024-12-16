# Licensed under the Apache License, Version 2.0 (the "License");
# ...
# Attribution: The Unnatural Group, LLC, Tradesignals project

import json
from decimal import Decimal, getcontext
from typing import Any, get_origin, get_args

from attrs import define, field, fields, NOTHING
from cattrs import Converter

converter = Converter()

AVRO_PRIMITIVES = {
    str: "string",
    int: "int",
    float: "float",
    bool: "boolean",
    bytes: "bytes"
}

LOGICAL_TYPE_BASE = {
    "decimal": "bytes",
    "timestamp-millis": "long",
    "timestamp-micros": "long",
    "timestamp-nanos": "long",
    "date": "int",
    "time-millis": "int",
    "time-micros": "long",
    "time-nanos": "long"
}


def infer_avro_type(py_type, metadata) -> (str, dict):
    logical_type = metadata.get("logicalType") or metadata.get("logical_type")
    extra = {}
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


def make_field_schema(f):
    metadata = f.metadata or {}
    py_type = f.type

    field_name = metadata.get("alias", f.name)
    doc = metadata.get("doc")
    default_val = None
    if f.default is not NOTHING:
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


def make_avro_schema(cls):
    name = cls.__name__
    namespace = cls.__module__
    doc = getattr(cls, "__doc__", None)
    field_schemas = [make_field_schema(f) for f in fields(cls)]
    schema = {
        "type": "record",
        "name": name,
        "namespace": namespace,
        "fields": field_schemas
    }
    if doc:
        schema["doc"] = doc.strip()
    return schema


def avro_schema(cls):
    @property
    def avro_schema_property(self):
        return make_avro_schema(type(self))
    cls.avro_schema = avro_schema_property
    return cls

def decimal_to_big_endian_bytes(d: Decimal, scale: int) -> bytes:
    """Convert Decimal to big-endian two's complement bytes."""
    unscaled = int((d * (10 ** scale)).to_integral_value(rounding="ROUND_HALF_EVEN"))

    if unscaled == 0:
        return b"\x00"

    # If negative, we will use two's complement
    sign = 1
    if unscaled < 0:
        sign = -1
        unscaled = -unscaled

    length = (unscaled.bit_length() + 7) // 8
    candidate = unscaled.to_bytes(length, 'big', signed=False)

    if sign == -1:
        # If negative, two's complement
        # Ensure leading bit is set, if not, prepend a byte:
        if (candidate[0] & 0x80) == 0:
            candidate = b"\x00" + candidate
        # Invert bits and add 1
        as_int = int.from_bytes(candidate, 'big')
        # Two's complement negative: value = 2^n - X
        # Easier: int.from_bytes with signed=True can do this directly:
        # Let's do manual:
        # Actually, Python 3.2+ supports signed=True in from_bytes, but we are constructing manually.
        # We'll do the complement:
        inverted = bytes(b ^ 0xFF for b in candidate)
        as_int = int.from_bytes(inverted, 'big') + 1
        candidate = as_int.to_bytes(len(candidate), 'big')
    else:
        # If positive and top bit set, prepend 0x00
        if (candidate[0] & 0x80) == 0x80:
            candidate = b"\x00" + candidate

    return candidate

def big_endian_bytes_to_decimal(hex_str: str, scale: int) -> Decimal:
    """Convert a hex string representing big-endian two's complement bytes back to Decimal."""
    b = bytes.fromhex(hex_str)
    length = len(b)
    # Interpret as signed big-endian two's complement
    value = int.from_bytes(b, 'big', signed=True)
    # Apply scale
    getcontext().prec = max(scale+28, 28)  # some extra precision
    d = Decimal(value) * (Decimal(10) ** (-scale))
    return d


def serialize_avro_value(value, schema):
    if isinstance(schema, list):
        # Union type: try each branch
        for branch in schema:
            try:
                return serialize_avro_value(value, branch)
            except:
                continue
        raise ValueError("No union branch matched the value")

    if isinstance(schema, dict):
        t = schema["type"]
        if t == "array":
            items_schema = schema["items"]
            return [serialize_avro_value(i, items_schema) for i in value]
        elif t == "map":
            values_schema = schema["values"]
            return {k: serialize_avro_value(v, values_schema) for k, v in value.items()}
        elif t == "enum":
            # Enum as string symbol
            if value not in schema["symbols"]:
                raise ValueError(f"Invalid enum symbol {value}")
            return value
        elif t == "fixed":
            # fixed is bytes, hex encode
            return value.hex()
        elif t in ("record", "error"):
            # record: value should be an object
            result = {}
            for f in schema["fields"]:
                field_name = f["name"]
                attr_value = getattr(value, field_name, None)
                result[field_name] = serialize_avro_value(attr_value, f["type"])
            return result
        else:
            logical_type = schema.get("logicalType")
            if logical_type == "decimal":
                scale = schema["scale"]
                d = Decimal(value)
                big_endian = decimal_to_big_endian_bytes(d, scale)
                return big_endian.hex()
            # Other logical types: just return the value directly
            return value
    else:
        # Primitive
        return value


def deserialize_avro_value(data, schema):
    if isinstance(schema, list):
        # Union: try each
        # In a real scenario, you'd have a discriminator or try all branches.
        for branch in schema:
            try:
                return deserialize_avro_value(data, branch)
            except:
                pass
        raise ValueError("No union branch could handle the data")

    if isinstance(schema, dict):
        t = schema["type"]
        if t == "array":
            items_schema = schema["items"]
            return [deserialize_avro_value(i, items_schema) for i in data]
        elif t == "map":
            values_schema = schema["values"]
            return {k: deserialize_avro_value(v, values_schema) for k, v in data.items()}
        elif t == "enum":
            # Already a string symbol
            if data not in schema["symbols"]:
                raise ValueError(f"Invalid enum symbol {data}")
            return data
        elif t == "fixed":
            # Convert hex to bytes
            return bytes.fromhex(data)
        elif t in ("record", "error"):
            # Need to reconstruct a record
            # We'll return a dict here; caller can structure it back into a class
            result = {}
            for fdef in schema["fields"]:
                fname = fdef["name"]
                fdata = data.get(fname)
                result[fname] = deserialize_avro_value(fdata, fdef["type"])
            return result
        else:
            logical_type = schema.get("logicalType")
            if logical_type == "decimal":
                scale = schema["scale"]
                # data should be hex string
                return big_endian_bytes_to_decimal(data, scale)
            # Other logical types: just return data as is
            return data
    else:
        # Primitive
        return data


def to_avro_data(instance):
    schema = instance.avro_schema
    if schema["type"] != "record":
        raise ValueError("Top-level schema must be a record")
    result = {}
    for f in schema["fields"]:
        field_name = f["name"]
        # Find corresponding attrs field by matching alias or name
        # We'll match by alias or name
        for attr_field in fields(type(instance)):
            alias = attr_field.metadata.get("alias", attr_field.name)
            if alias == field_name:
                attr_value = getattr(instance, attr_field.name)
                break
        else:
            attr_value = None

        result[field_name] = serialize_avro_value(attr_value, f["type"])
    return result


def from_avro_data(data, schema, cls):
    if schema["type"] != "record":
        raise ValueError("Top-level schema must be a record")
    # Deserialize data to a dict of field values
    field_values = {}
    for f in schema["fields"]:
        fname = f["name"]
        # Find original attr field
        for attr_field in fields(cls):
            alias = attr_field.metadata.get("alias", attr_field.name)
            if alias == fname:
                original_name = attr_field.name
                break
        else:
            original_name = fname

        field_values[original_name] = deserialize_avro_value(data.get(fname), f["type"])

    # Use cattrs or attrs.factory to construct the instance
    return cls(**field_values)


# Example usage:
if __name__ == "__main__":
    @avro_schema
    @define
    class ExampleModel:
        """Example model with a decimal field."""
        field1: str = field(default="hello", metadata={"doc": "A string field"})
        field2: Decimal = field(
            default=Decimal("123.45"),
            metadata={
                "logicalType": "decimal",
                "precision": 6,
                "scale": 2,
                "doc": "A decimal field"
            }
        )

    instance = ExampleModel()
    instance.field2 = Decimal("1.452432424")
    # Serialize to Avro data
    avro_data = to_avro_data(instance)
    print("Serialized Avro Data:", json.dumps(avro_data, indent=2))

    # Deserialize back to instance
    new_instance = from_avro_data(avro_data, instance.avro_schema, ExampleModel)
    print(f"{new_instance.field2 = } is equal to {instance.field2 = }")
    print("Deserialized Instance:", new_instance)
    print("Deserialized Decimal field:", new_instance.field2, type(new_instance.field2))