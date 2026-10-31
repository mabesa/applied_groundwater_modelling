"""AWEL monthly aggregation retains month-end semantics on Pandas 3."""
import ast
import json
from pathlib import Path

import pandas as pd


def test_awel_notebook_monthly_mean_uses_month_end():
    notebook = Path(__file__).parents[1] / "src/scripts/scripts_limmat_data_preprocessing/get_awel_gw_data.ipynb"
    cells = json.loads(notebook.read_text())["cells"]
    assignments = []
    for cell in cells:
        source = "".join(cell.get("source", []))
        if cell["cell_type"] != "code" or "ts_data.resample(" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "ts_data"
                for target in node.targets
            ) and "resample" in ast.unparse(node.value):
                assignments.append(node)
    assert len(assignments) == 1
    original = pd.Series(
        [1.0, 3.0, 5.0, 7.0, 9.0],
        index=pd.to_datetime(["2024-01-01", "2024-01-31", "2024-02-01", "2024-02-29", "2024-03-01"]),
    )
    namespace = {"ts_data": original.copy()}
    statement = ast.Module(body=assignments, type_ignores=[])
    exec(compile(ast.fix_missing_locations(statement), str(notebook), "exec"), namespace)
    actual = namespace["ts_data"]
    expected = original.resample(pd.offsets.MonthEnd()).mean()
    pd.testing.assert_series_equal(actual, expected)
    assert actual.index.is_month_end.all()
    assert actual.tolist() == [2.0, 6.0, 9.0]
