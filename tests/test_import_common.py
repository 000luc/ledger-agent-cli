from decimal import Decimal

import pytest

from ledger_agent_cli.importers.common import apply_mapping, money_to_cents, parse_date_text


def test_money_to_cents_accepts_commas_and_parentheses():
    assert money_to_cents("1,234.56") == 123456
    assert money_to_cents("(1,234.56)") == -123456
    assert money_to_cents("") == 0
    assert money_to_cents(None) == 0
    assert money_to_cents(Decimal("12.30")) == 1230


def test_parse_date_text_normalizes_common_formats():
    assert parse_date_text("2025/01/31") == "2025-01-31"
    assert parse_date_text("2025-1-5") == "2025-01-05"


def test_apply_mapping_preserves_raw_json():
    row = {"公司": "公司A", "科目名称": "差旅费", "多余列": "保留"}
    mapping = {"company": "公司", "account_name": "科目名称"}

    mapped = apply_mapping(row, mapping)

    assert mapped["company"] == "公司A"
    assert mapped["account_name"] == "差旅费"
    assert mapped["raw"]["多余列"] == "保留"


def test_apply_mapping_raises_for_missing_required_field():
    row = {"公司": "公司A"}
    mapping = {"company": "公司", "account_name": "科目名称"}

    with pytest.raises(ValueError, match="Missing mapped field: account_name"):
        apply_mapping(row, mapping, required=["company", "account_name"])
