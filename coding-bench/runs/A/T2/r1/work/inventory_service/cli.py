"""Command line: python -m inventory_service --state state.json <command> ...

Commands:
  import-products FILE            add or update products from CSV
  import-stock FILE [--add]       set stock counts from CSV (or add them with --add)
  add-customer ID NAME [--tier T] [--region R]
  quote CUSTOMER SKU:QTY... [--coupon C] [--currency CODE]
  order CUSTOMER SKU:QTY... [--coupon C] [--currency CODE]
  ship ORDER | cancel ORDER
  refund ORDER SKU:QTY... [--no-restock]
  report sales|top|valuation|low-stock|aov [--n N] [--threshold T]
  export-orders [FILE]
Exit code 0 on success, 2 on a usage or validation error (the message goes to stderr).
"""
from __future__ import annotations

import argparse
import sys

from . import csv_io, reports, storage
from .currency import format_amount
from .models import Customer, ValidationError
from .money import money_str
from .pricing import quote


def parse_items(items: list[str]) -> list[tuple[str, int]]:
    out = []
    for it in items:
        sku, sep, qty = it.partition(":")
        if not sep or not qty.strip().lstrip("-").isdigit():
            raise ValidationError(f"expected SKU:QTY, got {it!r}")
        out.append((sku.strip().upper(), int(qty)))
    return out


def amount_str(amount, currency: str) -> str:
    """An amount for printing: '12.30' in USD, '11.49 EUR' in another currency."""
    if currency == "USD":
        return money_str(amount)
    return f"{format_amount(amount, currency)} {currency}"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="inventory_service")
    ap.add_argument("--state", default="state.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("import-products"); p.add_argument("file")
    p = sub.add_parser("import-stock"); p.add_argument("file"); p.add_argument("--add", action="store_true")
    p = sub.add_parser("add-customer"); p.add_argument("id"); p.add_argument("name")
    p.add_argument("--tier", default="standard"); p.add_argument("--region", default="US-CA")
    for name in ("quote", "order"):
        p = sub.add_parser(name); p.add_argument("customer"); p.add_argument("items", nargs="+")
        p.add_argument("--coupon"); p.add_argument("--currency", default="USD", metavar="CODE")
    for name in ("ship", "cancel"):
        p = sub.add_parser(name); p.add_argument("order")
    p = sub.add_parser("refund"); p.add_argument("order"); p.add_argument("items", nargs="+")
    p.add_argument("--no-restock", action="store_true")
    p = sub.add_parser("report"); p.add_argument("kind", choices=["sales", "top", "valuation", "low-stock", "aov"])
    p.add_argument("--n", type=int, default=3); p.add_argument("--threshold", type=int, default=5)
    p = sub.add_parser("export-orders"); p.add_argument("file", nargs="?")
    return ap


def run(argv: list[str], out=None) -> int:
    out = out or sys.stdout
    a = build_parser().parse_args(argv)
    state = storage.load(a.state)
    svc = state.orders
    changed = True
    if a.cmd == "import-products":
        with open(a.file, encoding="utf-8") as f:
            r = csv_io.import_products(f.read(), state.catalog)
        print(f"added {r.added}, updated {r.updated}, errors {len(r.errors)}", file=out)
        for n, msg in r.errors:
            print(f"  line {n}: {msg}", file=out)
    elif a.cmd == "import-stock":
        with open(a.file, encoding="utf-8") as f:
            r = csv_io.import_stock(f.read(), state.inventory, state.catalog, "add" if a.add else "set")
        print(f"updated {r.updated}, errors {len(r.errors)}", file=out)
        for n, msg in r.errors:
            print(f"  line {n}: {msg}", file=out)
    elif a.cmd == "add-customer":
        svc.add_customer(Customer(a.id, a.name, a.tier, a.region))
        print(f"customer {a.id} added", file=out)
    elif a.cmd == "quote":
        changed = False
        customer = svc.customers.get(a.customer)
        if customer is None:
            raise ValidationError(f"unknown customer {a.customer}")
        b = quote(state.catalog, customer, parse_items(a.items), a.coupon, currency=a.currency)
        for k, v in b.to_dict().items():
            print(f"{k}: {amount_str(v, b.currency)}", file=out)
    elif a.cmd == "order":
        o = svc.create_order(a.customer, parse_items(a.items), a.coupon, currency=a.currency)
        print(f"order {o.id} reserved, total {amount_str(o.totals['total'], o.currency)}", file=out)
    elif a.cmd == "ship":
        print(f"order {svc.ship(a.order).id} shipped", file=out)
    elif a.cmd == "cancel":
        print(f"order {svc.cancel(a.order).id} cancelled", file=out)
    elif a.cmd == "refund":
        r = svc.refund(a.order, dict(parse_items(a.items)), restock=not a.no_restock)
        print(f"refund {r.id}: {money_str(r.amount)}", file=out)
    elif a.cmd == "report":
        changed = False
        orders = list(svc.orders.values())
        if a.kind == "sales":
            for cat, amount in reports.sales_by_category(orders, state.catalog).items():
                print(f"{cat}: {money_str(amount)}", file=out)
        elif a.kind == "top":
            for sku, units in reports.top_products(orders, a.n):
                print(f"{sku}: {units}", file=out)
        elif a.kind == "valuation":
            print(money_str(reports.inventory_valuation(state.inventory, state.catalog)), file=out)
        elif a.kind == "low-stock":
            for line in reports.low_stock_report(state.inventory, state.catalog, a.threshold):
                print(line, file=out)
        else:
            print(money_str(reports.average_order_value(orders)), file=out)
    elif a.cmd == "export-orders":
        changed = False
        text = csv_io.export_orders(svc.orders.values())
        if a.file:
            with open(a.file, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        else:
            out.write(text)
    if changed:
        storage.save(state, a.state)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(sys.argv[1:] if argv is None else argv)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
