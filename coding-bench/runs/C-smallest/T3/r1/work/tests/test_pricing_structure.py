import ast
import pathlib

import inventory_service.pricing as pricing


def test_no_function_in_pricing_is_longer_than_40_lines():
    tree = ast.parse(pathlib.Path(pricing.__file__).read_text(encoding="utf-8"))
    long = [(n.name, n.end_lineno - n.lineno + 1) for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.end_lineno - n.lineno + 1 > 40]
    assert long == []
