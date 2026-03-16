from app.models import ApiCall


def test_api_calls_has_query_indexes():
    index_columns = {
        tuple(column.name for column in index.columns)
        for index in ApiCall.__table__.indexes
    }

    assert ("account_id", "created_at") in index_columns
    assert ("account_id", "service_key", "status", "created_at") in index_columns
    assert ("account_id", "sequence_id") in index_columns
