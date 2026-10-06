from app.services import governance


def test_us05_direct_access_detected(snap, rules):
    rows = governance.direct_access(snap, rules["governance"])
    by_src = {r.source.id: r for r in rows}
    assert "service:billing" in by_src
    billing = by_src["service:billing"]
    assert billing.severity == "HIGH"
    assert billing.bypassesApi is True  # billing also calls the canonical Customer API
    assert any(a.id == "api:customer-get" for a in billing.canonicalApis)
    assert by_src["batch:analytics-daily"].severity == "MEDIUM"
    assert by_src["batch:analytics-daily"].bypassesApi is False
    assert "unknown:UNKNOWN-001" in by_src
    # owner access is not flagged
    assert "service:customer" not in by_src


def test_owner_missing(snap, rules):
    missing = {o.id for o in governance.owner_missing(snap, rules["governance"])}
    assert "bo:address" in missing
    assert "batch:analytics-legacy" in missing
    assert "service:customer" not in missing


def test_summary(snap, rules):
    s = governance.summary(snap, rules["governance"])
    assert s.unknownOpen == 1
    assert s.directAccessCount == 3
