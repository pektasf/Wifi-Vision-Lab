import ast
from pathlib import Path


def test_app_module_has_valid_python_syntax():
    source = Path("app.py").read_text(encoding="utf-8")
    ast.parse(source, filename="app.py")
