import platform
import sys


def test_imports() -> None:
    import second  # noqa: F401

def test_python_is_64_bit() -> None:
    assert sys.maxsize > 2**32
    assert platform.machine() in {"AMD64", "x86_64"}