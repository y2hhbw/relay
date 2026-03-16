from app.models import Deposit


def test_deposit_has_unique_constraint_on_tx_hash_and_log_index():
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in Deposit.__table__.constraints
        if hasattr(constraint, "columns")
    }

    assert ("tx_hash", "log_index") in constraint_columns
