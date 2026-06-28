import argparse
import json
import logging
import time
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from price_monitor.config import get_settings
from price_monitor.db import SessionLocal, migrate_db
from price_monitor.models import Offer, Product
from price_monitor.notifications import build_notifier
from price_monitor.scrapers import PriceScraper
from price_monitor.scrapers.parser import parse_price
from price_monitor.search import ProductSearch
from price_monitor.search.base import SearchError
from price_monitor.search.setup import setup_browser_provider
from price_monitor.services import MonitorService
from price_monitor.services.settings import get_default_location, set_default_location


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor de preços de produtos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="cadastra um produto")
    add.add_argument("--name", required=True)
    add.add_argument("--query", help="termo de busca; por padrão usa o nome")
    add.add_argument("--url", help="opcional: monitora apenas esta URL")
    add.add_argument("--target-price", required=True)
    add.add_argument("--city", help="sobrescreve a cidade padrão")
    add.add_argument("--state", help="UF da cidade, por exemplo SC")

    subparsers.add_parser("list", help="lista produtos")
    subparsers.add_parser("run", help="verifica todos os produtos ativos uma vez")

    check = subparsers.add_parser("check", help="verifica um produto")
    check.add_argument("product_id", type=int)

    daemon = subparsers.add_parser("daemon", help="executa continuamente no intervalo configurado")
    daemon.add_argument("--interval-hours", type=float)

    offers = subparsers.add_parser("offers", help="lista ofertas atuais de um produto")
    offers.add_argument("product_id", type=int)

    config = subparsers.add_parser("config", help="altera configurações")
    config_subparsers = config.add_subparsers(dest="config_command", required=True)
    location = config_subparsers.add_parser("location", help="define a localização padrão")
    location.add_argument("--city", required=True)
    location.add_argument("--state", required=True)

    auth = subparsers.add_parser("auth", help="configura autenticação de lojas")
    auth_subparsers = auth.add_subparsers(dest="auth_command", required=True)
    setup = auth_subparsers.add_parser("setup", help="abre o login guiado")
    setup.add_argument("provider", choices=["olx", "amazon", "kabum"])
    return parser


def _service(session) -> MonitorService:
    settings = get_settings()
    return MonitorService(
        session,
        PriceScraper(settings),
        build_notifier(settings),
        ProductSearch(settings),
        settings,
    )


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
    migrate_db()

    if args.command == "add":
        target_price = parse_price(args.target_price)
        if target_price is None:
            raise SystemExit("preço inválido; use 2500 ou 2500,00")
        search_query = args.query or (None if args.url else args.name)
        with SessionLocal() as session:
            product = Product(
                name=args.name,
                search_query=search_query,
                url=args.url,
                target_price=target_price,
                city=args.city,
                state=args.state.upper() if args.state else None,
            )
            session.add(product)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                raise SystemExit("esta URL já está cadastrada") from None
            print(f"produto {product.id} cadastrado")
        return 0

    if args.command == "config":
        with SessionLocal() as session:
            location = set_default_location(session, args.city, args.state)
        print(f"localização padrão: {location.city}/{location.state}")
        return 0

    if args.command == "auth":
        try:
            names = {"olx": "OLX", "amazon": "Amazon", "kabum": "KaBuM"}
            setup_browser_provider(settings, names[args.provider])
        except SearchError as exc:
            raise SystemExit(str(exc)) from None
        return 0

    if args.command == "list":
        with SessionLocal() as session:
            default_location = get_default_location(session, settings)
            products = list(session.scalars(select(Product).order_by(Product.id)))
            for product in products:
                state = "ativo" if product.active else "inativo"
                source = (
                    f'busca "{product.search_query}"'
                    if product.search_query
                    else f"URL {product.url}"
                )
                print(
                    f"{product.id}: {product.name} | meta R$ {product.target_price:.2f} | "
                    f"último {product.last_price or '-'} | {source} | "
                    f"{product.city or default_location.city}/"
                    f"{product.state or default_location.state} | {state}"
                )
        return 0

    if args.command == "offers":
        with SessionLocal() as session:
            product = session.get(Product, args.product_id)
            if product is None:
                raise SystemExit(f"produto {args.product_id} não encontrado")
            offers = list(
                session.scalars(
                    select(Offer)
                    .where(Offer.product_id == product.id, Offer.active.is_(True))
                    .order_by(Offer.current_price)
                )
            )
            for offer in offers:
                print(
                    f"{offer.store}: R$ {offer.current_price:.2f} | {offer.condition} | "
                    f"{offer.title} | {offer.url}"
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
            print(
                json.dumps(
                    {
                        "status": outcome.check.status,
                        "price": str(outcome.check.price)
                        if outcome.check.price is not None
                        else None,
                        "error": outcome.check.error,
                        "alerts_sent": outcome.alerts_sent,
                    },
                    ensure_ascii=False,
                )
            )
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
