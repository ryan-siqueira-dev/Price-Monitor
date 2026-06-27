import argparse
import json
import logging
import time
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from price_monitor.config import get_settings
from price_monitor.db import SessionLocal, init_db
from price_monitor.models import Product
from price_monitor.notifications import build_notifier
from price_monitor.scrapers import PriceScraper
from price_monitor.scrapers.parser import parse_price
from price_monitor.services import MonitorService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor de preços de notebooks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="cadastra um produto")
    add.add_argument("--name", required=True)
    add.add_argument("--url", required=True)
    add.add_argument("--target-price", required=True)

    subparsers.add_parser("list", help="lista produtos")
    subparsers.add_parser("run", help="verifica todos os produtos ativos uma vez")

    check = subparsers.add_parser("check", help="verifica um produto")
    check.add_argument("product_id", type=int)

    daemon = subparsers.add_parser("daemon", help="executa continuamente no intervalo configurado")
    daemon.add_argument("--interval-hours", type=float)
    return parser


def _service(session) -> MonitorService:
    settings = get_settings()
    return MonitorService(session, PriceScraper(settings), build_notifier(settings))


def _run_once() -> int:
    with SessionLocal() as session:
        stats = _service(session).run_all()
    print(json.dumps(asdict(stats), ensure_ascii=False))
    return 1 if stats.failed else 0


def main() -> int:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parser().parse_args()
    init_db()

    if args.command == "add":
        target_price = parse_price(args.target_price)
        if target_price is None:
            raise SystemExit("preço inválido; use 2500 ou 2500,00")
        with SessionLocal() as session:
            product = Product(name=args.name, url=args.url, target_price=target_price)
            session.add(product)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise SystemExit("esta URL já está cadastrada") from None
            print(f"produto {product.id} cadastrado")
        return 0

    if args.command == "list":
        with SessionLocal() as session:
            products = list(session.scalars(select(Product).order_by(Product.id)))
            for product in products:
                state = "ativo" if product.active else "inativo"
                print(
                    f"{product.id}: {product.name} | meta R$ {product.target_price:.2f} | "
                    f"último {product.last_price or '-'} | {state}"
                )
        return 0

    if args.command == "run":
        return _run_once()

    if args.command == "check":
        with SessionLocal() as session:
            try:
                outcome = _service(session).check_product(args.product_id)
            except LookupError as exc:
                raise SystemExit(str(exc)) from None
            print(json.dumps({
                "status": outcome.check.status,
                "price": str(outcome.check.price) if outcome.check.price is not None else None,
                "error": outcome.check.error,
                "alert_sent": outcome.alert_sent,
            }, ensure_ascii=False))
            return 1 if outcome.check.status == "error" else 0

    interval = args.interval_hours or settings.scheduler_interval_hours
    if interval <= 0:
        raise SystemExit("o intervalo deve ser maior que zero")
    try:
        while True:
            _run_once()
            time.sleep(interval * 3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
