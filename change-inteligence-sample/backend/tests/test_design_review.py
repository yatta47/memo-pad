from app.domain.models import DesignReviewIn
from app.services import design_review


def test_us07_shipping_address_extends_address(snap, rules):
    req = DesignReviewIn(name="shipping_address", description="注文時点の配送先住所を保存したい",
                         fields=["postal_code", "prefecture", "city", "address1"], system="Order System")
    r = design_review.review(snap, req, rules["design_review"])
    assert r.recommendation == "EXTEND"
    top = r.candidates[0]
    assert top.id in ("bo:address", "table:customer.customer_address")
    assert set(top.matchedFields) == {"postal_code", "prefecture", "city", "address1"}
    # lifecycle keyword "時点" -> CREATE alternative shown
    assert any(a["recommendation"] == "CREATE" for a in r.alternatives)
    assert any("責任チームが未設定" in s for s in r.rationale) or any("相談先" in s for s in r.rationale)


def test_reuse_when_fields_exist(snap, rules):
    req = DesignReviewIn(name="customer", description="顧客", fields=["customer_id", "name", "email", "phone", "status"])
    r = design_review.review(snap, req, rules["design_review"])
    assert r.recommendation == "REUSE"
    assert r.candidates[0].id in ("bo:customer", "table:customer.customer")


def test_create_when_nothing_similar(snap, rules):
    req = DesignReviewIn(name="warehouse_slot", description="倉庫の棚位置", fields=["slot_code", "aisle", "rack"])
    r = design_review.review(snap, req, rules["design_review"])
    assert r.recommendation == "CREATE"
