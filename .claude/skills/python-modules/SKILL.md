---
name: python-modules
description: Style and good practices when implementing or refactoring Python modules
---

# python-modules

Best practices and style guide for implementing Python modules.


## Architecture

Prefer deep modules over wide modules. A deep module has a small API surface 
yet implement a large set of features. Avoid exposing public functions that are 
trivial to implement and provide only marginal convenience. 


## Coding layout

All modules should include an import of "from __future__ import annotations". 
The module should be organized in the following order:

* Module docstring, if public.
* Future imports.
* Imports.
* Module-level constants. Those should be in all caps and separated by underscores.
* Module-level type aliases. Those should be in PascalCase.
* The main API entry points of the module. Can be a class or a function. If the
  module exposes multiple APIs, they should be grouped in a logical order, from
  the most important to the least important.
* Internal implementation of the module. Can be classes, functions or variables.
  Those should be named with a leading underscore. If the module is large, it
  can be split into multiple files and the internal implementation can be
  placed in a private module. 
* If you want to separate by sections, use the following comment style:

  ```python
  # 
  # SECTION TITLE
  #
  ```

  The section can also contain extra comments if they implement an unusual or
  complex behavior. The comments should be placed after the section title. 


## Public modules

All public modules should have a docstring at the top of the file with a short
description of the module's purpose. DO NOT list the exposed symbols in the 
docstring.

Public modules should also export a `__all__` variable with a list of the 
public symbols. You can separete sections within the exported symbols with 
comments like so:

```python
__all__ = [
    "MyClass",
    #: Section title
    #
    # Small paragraph describing the section.
    "fn1",
    "fn2",
]
```

## Private modules

Private modules do not contain neither a docstring nor an `__all__` variable.
Modules can be prived for two reasons:

* Internal use only, never export any public symbols.
* Implement some public symbol that is re-exported by a public module. It is
  mostly used to split a large implementation into multiple files.

The first should always be named with a leading underscore. The internal symbols
should be named with public names. Internal use modules should usually be imported
as namespaces like so:

```python
from . import _internal_module

# use some symbol:
_internal_module.some_symbol()
```
