import pytest
from social_reports.metrics import safe_div, percent_change, aggregate, compare

def test_safe_div():
    assert safe_div(10, 2) == 5.0
    assert safe_div(10, 0) == 0.0
    assert safe_div(0, 5) == 0.0

def test_percent_change():
    assert percent_change(150, 100) == 50.0
    assert percent_change(50, 100) == -50.0
    assert percent_change(100, 0) is None
    assert percent_change(100, 100) == 0.0

def test_aggregate():
    rows = [
        {"spend": 100, "impressions": 1000, "reach": 500, "clicks": 50, "purchases": 2, "purchase_value": 200, "leads": 5},
        {"spend": 50, "impressions": 500, "reach": 250, "clicks": 25, "purchases": 1, "purchase_value": 100, "leads": 2},
    ]
    
    totals = aggregate(rows)
    
    assert totals["spend"] == 150.0
    assert totals["impressions"] == 1500.0
    assert totals["reach"] == 750.0
    assert totals["clicks"] == 75.0
    assert totals["purchases"] == 3.0
    assert totals["purchase_value"] == 300.0
    assert totals["leads"] == 7.0
    
    assert totals["ctr"] == (75 / 1500) * 100
    assert totals["cpc"] == 150 / 75
    assert totals["cpm"] == (150 / 1500) * 1000
    assert totals["frequency"] == 1500 / 750
    assert totals["cpa_purchase"] == 150 / 3
    assert totals["cpl"] == 150 / 7
    assert totals["roas_meta"] == 300 / 150

def test_aggregate_empty():
    totals = aggregate([])
    assert totals["spend"] == 0.0
    assert totals["ctr"] == 0.0
    assert totals["cpc"] == 0.0

def test_compare():
    current = {"spend": 200, "clicks": 100, "ctr": 5.0}
    previous = {"spend": 100, "clicks": 50, "ctr": 2.5}
    
    changes = compare(current, previous)
    
    assert changes["spend"] == 100.0
    assert changes["clicks"] == 100.0
    assert changes["ctr"] == 100.0
    assert changes["impressions"] is None  # previous was 0 (default)
