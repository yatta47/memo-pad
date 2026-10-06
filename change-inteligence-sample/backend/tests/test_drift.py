from datetime import datetime, timezone

from app.services import drift

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def _by(kind, rows):
    return {(r.source.id if r.source else None, r.target.id if r.target else None): r for r in rows if r.kind == kind}


def test_declared_only_detected(snap):
    rows = drift.detect(snap, stale_days=30, now=NOW)
    d = _by("declared_only", rows)
    assert ("service:order", "api:customer-update") in d
    # a relation with both declared and observed evidence is not flagged
    assert ("service:order", "api:customer-get") not in d


def test_observed_only_shadow_dependency(snap):
    rows = drift.detect(snap, stale_days=30, now=NOW)
    d = _by("observed_only", rows)
    assert ("service:billing", "api:customer-get") in d
    assert {"team:billing", "team:customer"} <= {o.id for o in d[("service:billing", "api:customer-get")].notify}
    assert d[("service:billing", "table:customer.customer")].severity == "HIGH"  # direct DB access
    # owner access and Unknowns are not "shadow" dependencies
    assert ("service:customer", "table:customer.customer") not in d
    assert ("unknown:UNKNOWN-001", "table:customer.customer") not in d


def test_stale_observation(snap):
    rows = drift.detect(snap, stale_days=30, now=NOW)
    d = _by("stale", rows)
    assert ("batch:analytics-daily", "table:customer.customer") in d
    assert d[("batch:analytics-daily", "table:customer.customer")].daysSince >= 30
    assert ("service:billing", "table:customer.customer") not in d
    # notify both ends' owners
    names = {o.id for o in d[("batch:analytics-daily", "table:customer.customer")].notify}
    assert {"team:analytics", "team:customer"} <= names


def test_unknown_open_too_long(snap):
    rows = drift.detect(snap, stale_days=30, now=NOW)
    d = _by("unknown_open", rows)
    assert ("unknown:UNKNOWN-001", "table:customer.customer") in d


def test_threshold_respected(snap):
    rows = drift.detect(snap, stale_days=365, now=NOW)
    assert not [r for r in rows if r.kind in ("stale", "unknown_open")]
