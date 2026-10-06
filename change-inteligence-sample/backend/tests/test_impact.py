from app.services import impact


def _by_id(result):
    return {a.id: a for a in result.affected}


def test_us01_table_schema_change(snap, rules):
    r = impact.analyze(snap, "table:customer.customer", "schema_change", rules["impact"])
    assert r is not None
    a = _by_id(r)
    # direct physical consumers
    assert a["service:billing"].direct and a["service:billing"].path == ["READS"]
    assert a["service:billing"].accessMode == "direct"
    assert a["batch:analytics-daily"].direct
    assert a["unknown:UNKNOWN-001"].direct
    # indirect consumer via the canonical route
    assert "service:order" in a and not a["service:order"].direct
    assert a["service:order"].path[-1] == "CALLS"
    assert r.unknownCount == 1
    assert any(w.startswith("正規ルート外") for w in r.warnings)
    assert any("正体が分かっていない利用元" in w for w in r.warnings)
    assert r.risk == "HIGH"
    assert {"team:customer", "team:billing", "team:order", "team:analytics"} <= set(r.owners)


def test_us02_api_change(snap, rules):
    r = impact.analyze(snap, "api:customer-get", "api_change", rules["impact"])
    a = _by_id(r)
    assert a["service:order"].direct and a["service:order"].path == ["CALLS"]
    assert a["service:billing"].direct
    assert a["service:customer"].path == ["PROVIDES"]
    # sibling APIs of the same provider are NOT impacted by a change to one API
    assert "api:customer-update" not in a
    assert "team:order" in r.owners and "team:billing" in r.owners and "team:customer" in r.owners
    assert r.unknownCount == 0


def test_us08_delete_api_without_consumers(snap, rules):
    r = impact.analyze(snap, "api:billing-invoice-get", "delete", rules["impact"])
    assert r.canDelete is True
    assert r.risk == "LOW"
    # the provider is listed for information but does not block
    assert [x.id for x in r.affected] == ["service:billing"]
    assert "team:billing" in r.owners


def test_us08_delete_table_with_consumers_and_unknown(snap, rules):
    r = impact.analyze(snap, "table:customer.customer", "delete", rules["impact"])
    assert r.canDelete is False
    assert r.unknownCount == 1
    assert any("利用している先があります" in w for w in r.warnings)
    assert any("正体が分かっていない利用元" in w for w in r.warnings)


def test_resolved_unknown_is_ignored(snap, rules):
    snap.nodes["unknown:UNKNOWN-001"].props["status"] = "resolved"
    try:
        r = impact.analyze(snap, "table:customer.customer", "schema_change", rules["impact"])
        assert r.unknownCount == 0
    finally:
        snap.nodes["unknown:UNKNOWN-001"].props["status"] = "open"


def test_unknown_object_returns_none(snap, rules):
    assert impact.analyze(snap, "nope", "schema_change", rules["impact"]) is None
