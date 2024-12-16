# Avro DBO 🚀

[![PyPI version](https://badge.fury.io/py/avro-dbo.svg)](https://badge.fury.io/py/avro-dbo)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/avro-dbo.svg)](https://pypi.org/project/avro-dbo/)

A powerful Python library for working with Apache Avro schemas, providing seamless integration with data serialization and schema management. Perfect for data engineering pipelines and stream processing applications.

## ✨ Features

- 🏗️ **Schema-First Development** - Generate Python classes directly from Avro schemas
- 🔄 **Full Type Support** - Complete support for all Avro logical types
- 🛠️ **Custom Serialization** - Flexible serializers and deserializers
- 🌐 **Schema Registry Integration** - Native support for Confluent Schema Registry
- 🔒 **Type Safety** - Full static type checking support
- ⚡ **High Performance** - Optimized for production workloads

## 🚀 Quick Start

### Install from PyPI

```bash
pip install avro-dbo
```

### Install from source

**UV is required to build and publish the package.**

#### Install UV package manager: https://github.com/astral-sh/uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Build and publish the package

```bash
uv sync --upgrade
uv build
```

## 📚 Documentation

For detailed usage instructions, type hints, and examples, please refer to the [documentation](https://avro-dbo.readthedocs.io/en/latest/).

## 🤝 Contributing

We welcome contributions! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) file for more information.

## 📜 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.
