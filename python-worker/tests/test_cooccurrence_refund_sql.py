"""Checks the co-purchase queries subtract refunds consistently.

The refund arithmetic itself needs Postgres. What is checked here is the thing
that actually rots: three queries sharing one basket definition. k11, k12/k21
and the order total must be counted over the same population, and the bug that
would cause — one query quietly not filtering refunds — stays invisible until a
merchant asks why a returned item is still being recommended.

Reads the source rather than importing it, so it runs without the worker's
dependencies installed (the worker itself only ever runs in Docker).

Run: python3 tests/test_cooccurrence_refund_sql.py
"""

import ast
import re
import sys
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "recommandations"
    / "edges"
    / "cooccurrence.py"
).read_text()


def _basket_cte() -> str:
    """The shared CTE, read as a literal from the module source."""
    tree = ast.parse(SOURCE)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_BASKETS_CTE" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("_BASKETS_CTE is gone from cooccurrence.py")


def _queries() -> dict:
    """Compose each `text(f\"\"\"...\"\"\")` query with the CTE substituted in."""
    cte = _basket_cte()
    found = {}
    for name in ("_PAIR_SQL", "_ITEM_SQL", "_TOTAL_SQL"):
        match = re.search(
            rf'{name}\s*=\s*text\(\s*f"""(.*?)"""\s*\)', SOURCE, re.DOTALL
        )
        assert match, f"{name} is not a text(f\"\"\"...\"\"\") query any more"
        found[name] = match.group(1).replace("{_BASKETS_CTE}", cte)
    return found


CTE = _basket_cte()
QUERIES = _queries()


def test_every_query_subtracts_refunds():
    for name, sql in QUERIES.items():
        assert "refund_data" in sql, f"{name} does not look at refunds"
        assert (
            "HAVING SUM(li.quantity) > COALESCE(MAX(r.refunded_qty), 0)" in sql
        ), f"{name} does not subtract refunded quantity"


def test_queries_share_one_basket_definition():
    """No query may hand-roll its own copy of the basket predicate."""
    for name in QUERIES:
        assert f"{{_BASKETS_CTE}}" in re.search(
            rf'{name}\s*=\s*text\(\s*f"""(.*?)"""\s*\)', SOURCE, re.DOTALL
        ).group(1), f"{name} has drifted from _BASKETS_CTE"


def test_total_counts_the_basket_population():
    """An order emptied by refunds must leave the denominator too.

    Counting it in the total while none of its products count in k11 makes
    every surviving pair look rarer than it is.
    """
    sql = QUERIES["_TOTAL_SQL"]
    assert "COUNT(DISTINCT order_id)" in sql
    assert "FROM baskets" in sql


def test_partial_refund_keeps_the_item():
    """The predicate compares quantities rather than merely detecting a refund.

    Bought 3, returned 1 -> the shopper kept 2, and those 2 are still evidence.
    A predicate like `r.refunded_qty IS NULL` would throw that away.
    """
    having = CTE.split("HAVING")[-1]
    assert "IS NULL" not in having
    assert ">" in having


def test_refund_rows_are_scoped_to_the_shop():
    """A missing shop filter on the refund CTE would leak across tenants."""
    refunded_block = CTE.split("baskets AS")[0]
    assert "rd.shop_id = :shop_id" in refunded_block


def test_parentheses_balance():
    for name, sql in QUERIES.items():
        assert sql.count("(") == sql.count(")"), f"{name} has unbalanced parens"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"pass  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    print("\n" + ("all passed" if not failures else f"{failures} failed"))
    sys.exit(1 if failures else 0)
