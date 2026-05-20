# ABOUTME: PKG-15 AC-1 — restore.sh shim renders mongorestore command for one BSON dump.
# ABOUTME: Shim is the mechanism that closes the mongo init gap surfaced by dab-mongo-probe.

import pytest

from razorback_plugin_dab.generate.mongo_init import render_mongo_restore_sh


def test_shim_invokes_mongorestore_with_db_and_dump_path():
    text = render_mongo_restore_sh(db_name="articles_db", dump_folder_basename="agnews_articles")
    assert text.startswith("#!/bin/sh\n")
    assert "set -eu" in text
    assert "mongorestore" in text
    assert "--db articles_db" in text
    assert "/docker-entrypoint-initdb.d/agnews_articles/articles_db" in text


def test_shim_quotes_db_name_safely():
    with pytest.raises(ValueError):
        render_mongo_restore_sh(db_name="articles_db; rm -rf /", dump_folder_basename="agnews_articles")


def test_shim_rejects_path_traversal_in_dump_folder():
    with pytest.raises(ValueError):
        render_mongo_restore_sh(db_name="articles_db", dump_folder_basename="../../etc")
