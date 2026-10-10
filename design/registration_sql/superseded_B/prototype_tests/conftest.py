"""Prototype fixtures: the repo's own, with the ledger cleared like attempt_tombstones."""
import psycopg
import pytest

from eyework.tests.conftest import app, app_url, owner_url, two_users  # noqa: F401  (fixtures)

_CLEAN = "TRUNCATE users, attempt_tombstones, registration_ledger RESTART IDENTITY CASCADE"


@pytest.fixture
def owner(owner_url):  # noqa: F811
    with psycopg.connect(owner_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(_CLEAN)
        yield connection
