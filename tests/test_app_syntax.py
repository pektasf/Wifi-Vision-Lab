import ast
from pathlib import Path


def test_app_module_has_valid_python_syntax():
    source = Path("app.py").read_text(encoding="utf-8")
    ast.parse(source, filename="app.py")


def test_every_page_renderer_references_a_defined_function():
    source = Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="app.py")
    defined_functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    renderer_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "PAGE_RENDERERS"
            for target in node.targets
        )
    )
    renderer_names = {
        value.id
        for value in renderer_assignment.value.values
        if isinstance(value, ast.Name)
    }
    assert renderer_names <= defined_functions
