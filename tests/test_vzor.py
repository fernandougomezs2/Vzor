import vzor


def test_vzor_imports():
    assert vzor is not None


def test_version_comes_from_rust_core():
    assert vzor.version() == "0.4.1"
    assert vzor.__version__ == vzor.version()
