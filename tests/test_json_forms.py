"""Forms drawn from JSON Schema (ADR 0007): render, post back, validate, and edit the shape."""

from datetime import date
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

import pytest
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from starlette.datastructures import FormData

from lattice.api import (
    AppManifest,
    FormSpec,
    NavNode,
    SchemaDef,
    build_form,
    parse_form,
    render_page,
)
from lattice.components.forms import nodes
from lattice.components.forms.schema import infer
from lattice.testing import csrf


class Colour(StrEnum):
    red = "red"
    blue = "blue"


class Address(BaseModel):
    street: str
    city: str = Field(title="Town or city")


class Card(BaseModel):
    method: Literal["card"] = "card"
    number: str = Field(min_length=4)


class Invoice(BaseModel):
    method: Literal["invoice"] = "invoice"
    terms_days: int = 30


class Customer(BaseModel):
    name: str = Field(min_length=2)
    age: int | None = Field(None, ge=0, le=150)
    vip: bool = False
    colour: Colour = Colour.red
    since: date | None = None
    address: Address
    tags: list[str] = []
    contacts: list[Address] = []
    payment: Card | Invoice = Field(discriminator="method")


DOC = {"name": "Ada", "age": 36, "vip": True, "colour": "blue", "since": "2020-01-02",
       "address": {"street": "1 Main St", "city": "Leeds"}, "tags": ["a", "b"],
       "contacts": [{"street": "2 Side St", "city": "York"}],
       "payment": {"method": "invoice", "terms_days": 14}, "legacy_id": "X-1"}

CUSTOMER = FormSpec("people.customer", schema=Customer)
FREE = FormSpec("people.free")
NAMED = FormSpec("people.named", schema="people.address", switchable=True)
STORE: dict = {}
router = APIRouter()


@router.get("/{key}")
def show(key: str, request: Request):
    spec = {"customer": CUSTOMER, "free": FREE, "named": NAMED}[key]
    return render_page(request, "people/form_page.html", "people", form=build_form(request, spec, STORE[key]),
                       action=f"/people/{key}")


@router.post("/{key}")
async def save(key: str, request: Request):
    spec = {"customer": CUSTOMER, "free": FREE, "named": NAMED}[key]
    result = parse_form(request, spec, await request.form())
    if not result.ok:
        return render_page(request, "people/form_page.html", "people", form=result.form,
                           action=f"/people/{key}", status_code=400)
    STORE[key] = result.data
    return {"saved": result.data}


@pytest.fixture
def host_apps():
    return [AppManifest(key="people", label="People", routers=[router], forms=[CUSTOMER, FREE, NAMED],
                        schemas=[SchemaDef("people.address", "Address", Address)],
                        templates=Path(__file__).parent / "templates",
                        nav=[NavNode("people", "People", "/people", hidden=True)])]


class _Inputs(HTMLParser):
    """What a browser would post from the first form on the page."""

    def __init__(self):
        super().__init__()
        self.pairs, self._select, self._textarea, self._text = [], None, None, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("name") and "disabled" not in a:
            if a.get("type") in ("checkbox", "radio") and "checked" not in a:
                return
            self.pairs.append((a["name"], a.get("value", "")))
        elif tag == "select" and a.get("name"):
            self._select = [a["name"], None, None]
        elif tag == "option" and self._select:
            value = a.get("value", "")
            if self._select[1] is None:
                self._select[1] = value
            if "selected" in a:
                self._select[2] = value
        elif tag == "textarea":
            self._textarea, self._text = a.get("name"), ""

    def handle_data(self, data):
        if self._textarea:
            self._text += data

    def handle_endtag(self, tag):
        if tag == "select" and self._select:
            name, first, chosen = self._select
            self.pairs.append((name, chosen if chosen is not None else first or ""))
            self._select = None
        elif tag == "textarea" and self._textarea:
            self.pairs.append((self._textarea, self._text))
            self._textarea = None


def inputs(html: str) -> list[tuple[str, str]]:
    p = _Inputs()
    p.feed(html)
    return [(k, v) for k, v in p.pairs if k not in ("__pick",)]


def as_data(pairs) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, v in pairs:
        out.setdefault(k, []).append(v)
    return out


def post(client, key, pairs, **changes):
    pairs = [(k, v) for k, v in pairs if k not in changes] + list(changes.items())
    return client.post(f"/people/{key}", data=as_data(pairs), headers={"X-CSRF-Token": csrf(client)})


def test_round_trip_keeps_the_document_including_unknown_fields(as_user):
    STORE["customer"] = DOC
    c = as_user("viewer")
    pairs = inputs(c.get("/people/customer").text)
    res = post(c, "customer", pairs)
    assert res.status_code == 200, res.text
    assert res.json()["saved"] == {**DOC, "since": "2020-01-02"}


def test_fields_follow_the_schema(as_user):
    STORE["customer"] = DOC
    html = as_user("viewer").get("/people/customer").text
    assert 'name="data/address/city"' in html and "Town or city" in html   # nested, titled
    assert 'type="date"' in html                                            # format: date
    assert 'name="data/payment/__variant"' in html                          # discriminated union
    assert 'name="data/payment/terms_days"' in html                         # the invoice branch
    assert 'name="data/payment/number"' not in html
    assert "Other fields (1)" in html and "legacy_id" in html


def test_validation_errors_are_shown_at_their_fields(as_user):
    STORE["customer"] = DOC
    c = as_user("viewer")
    pairs = inputs(c.get("/people/customer").text)
    res = post(c, "customer", pairs, **{"data/name": "A", "data/age": "200",
                                        "data/address/street": ""})
    assert res.status_code == 400
    assert "At least 2 characters." in res.text
    assert "At most 150." in res.text
    assert "Required." in res.text


def test_a_word_in_a_number_field(as_user):
    STORE["customer"] = DOC
    c = as_user("viewer")
    res = post(c, "customer", inputs(c.get("/people/customer").text), **{"data/age": "old"})
    assert res.status_code == 400 and "Enter a whole number." in res.text


def test_shape_edits_through_the_endpoint(as_user):
    STORE["customer"] = DOC
    c = as_user("viewer")
    pairs = inputs(c.get("/people/customer").text)

    def edit(op, pairs=pairs, **changes):
        body = [(k, v) for k, v in pairs if k not in changes] + list(changes.items()) + [("__op", op)]
        res = c.post("/_form/people.customer/render", data=as_data(body),
                     headers={"X-CSRF-Token": csrf(c)})
        assert res.status_code == 200
        return res.text

    html = edit("add:data/tags")
    assert 'name="data/tags/2"' in html
    html = edit("remove:data/tags/0")
    assert 'name="data/tags/1"' not in html and 'value="b"' in html
    html = edit("up:data/tags/1")
    assert html.index('value="b"') < html.index('value="a"')
    html = edit("variant:data/payment", **{"data/payment/__variant": "0"})
    assert 'name="data/payment/number"' in html
    html = edit("mode:json")
    assert 'name="__json"' in html and "legacy_id" in html


def test_json_tab_saves_raw_json(as_user):
    STORE["customer"] = DOC
    c = as_user("viewer")
    doc = {**DOC, "name": "Grace"}
    import json
    res = post(c, "customer", [("__mode", "json"), ("__json", json.dumps(doc))])
    assert res.json()["saved"]["name"] == "Grace"
    res = post(c, "customer", [("__mode", "json"), ("__json", "{oops")])
    assert res.status_code == 400 and "Not valid JSON" in res.text


def test_without_a_schema_the_document_is_inferred_and_can_grow(as_user):
    STORE["free"] = {"title": "Note", "count": 3, "when": "2026-10-18", "flags": {"on": True}}
    c = as_user("viewer")
    pairs = inputs(c.get("/people/free").text)
    res = post(c, "free", pairs, **{"data/__new/key": "extra", "data/__new/type": "integer",
                                    "data/__new/value": "7"})
    assert res.json()["saved"] == {**STORE["free"], "extra": 7}


def test_the_user_can_apply_another_schema(as_user):
    STORE["named"] = {"street": "1 Main St", "city": "Leeds", "zip": "LS1"}
    c = as_user("viewer")
    html = c.get("/people/named").text
    assert 'value="schema:people.address" selected' in html
    assert "Other fields (1)" in html


def test_infer():
    assert infer({"a": 1, "b": [{"x": "2026-01-01"}], "c": "l1\nl2"}) == {
        "type": "object", "properties": {
            "a": {"type": "integer"},
            "b": {"type": "array", "items": {"type": "object", "properties": {
                "x": {"type": "string", "format": "date"}}}},
            "c": {"type": "string", "x-widget": "textarea"}}}


def test_parse_leaves_out_empty_optional_fields():
    schema = Customer.model_json_schema()
    ctx = nodes.Context(root=schema, ui={}, errors={})
    form = FormData([("data/name", "Ada"), ("data/age", ""), ("data/address/street", "x"),
                     ("data/address/city", "y"), ("data/payment/__variant", "1")])
    data = nodes.parse(schema, form, ctx, required=True)
    assert data["age"] is None                      # Optional: empty is null
    assert "since" not in data or data["since"] is None
    assert data["payment"] == {"method": "invoice"}
