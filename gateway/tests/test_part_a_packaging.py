"""Verify the root and Part A distributions coexist without namespace shadowing."""


def test_root_and_part_a_packages_import_together():
    import gateway.app
    import zerotrace.db.models

    assert gateway.app is not zerotrace.db.models
