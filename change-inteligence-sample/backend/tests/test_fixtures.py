from app.seed import validate_fixtures


def test_fixtures_are_consistent_with_ontology(fixtures, ontology):
    assert validate_fixtures(fixtures, ontology) == []


def test_relation_ids_unique(fixtures):
    ids = [r["id"] for r in fixtures["relations"]]
    assert len(ids) == len(set(ids))


def test_demo_scenario_objects_exist(fixtures):
    ids = {o["id"] for o in fixtures["objects"]}
    for required in ("bo:customer", "table:customer.customer", "api:customer-get", "service:order", "service:billing",
                     "batch:analytics-daily", "batch:analytics-legacy", "unknown:UNKNOWN-001"):
        assert required in ids
