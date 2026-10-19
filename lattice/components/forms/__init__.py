"""Forms drawn from JSON Schema: JSON in, JSON out (ADR 0007).

Guide: lattice/help/developer/building-apps/json-forms.md.
"""

from lattice.components.forms.render import (
    FORMS,
    SCHEMAS,
    FormResult,
    build_form,
    parse_form,
    register_form,
    register_schema,
)
from lattice.components.forms.schema import infer
from lattice.components.forms.spec import FormSpec, SchemaDef

__all__ = ["FORMS", "SCHEMAS", "FormResult", "FormSpec", "SchemaDef", "build_form", "infer",
           "parse_form", "register_form", "register_schema"]
