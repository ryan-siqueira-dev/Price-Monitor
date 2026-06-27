from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from price_monitor.config import get_settings
from price_monitor.db import get_session, migrate_db
from price_monitor.models import Offer, OfferCheck, PriceCheck, Product, ProviderStatus
from price_monitor.notifications import build_notifier
from price_monitor.schemas import (
    LocationRead,
    LocationUpdate,
    OfferCheckRead,
    OfferRead,
    PriceCheckRead,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ProviderStatusRead,
    RunSummary,
)
from price_monitor.scrapers import PriceScraper
from price_monitor.scrapers.stores import supported_stores
from price_monitor.search import ProductSearch, search_provider_names
from price_monitor.services import MonitorService
from price_monitor.services.settings import get_default_location, set_default_location


@asynccontextmanager
async def lifespan(_app: FastAPI):
    migrate_db()
    yield


app = FastAPI(
    title="Product Price Monitor",
    version="0.1.0",
    description="Monitor de preços de qualquer produto em várias lojas.",
    lifespan=lifespan,
)

SessionDep = Annotated[Session, Depends(get_session)]
ActiveQuery = Annotated[bool | None, Query()]
LimitQuery = Annotated[int, Query(ge=1, le=1000)]


def monitor_service(session: Session) -> MonitorService:
    settings = get_settings()
    return MonitorService(
        session,
        PriceScraper(settings),
        build_notifier(settings),
        ProductSearch(settings),
        settings,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stores")
async def stores() -> dict[str, list[str]]:
    return {
        "search_providers": search_provider_names(),
        "direct_url_profiles": supported_stores(),
        "generic_support": ["qualquer URL HTTP/HTTPS"],
    }


@app.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, session: SessionDep) -> Product:
    url = str(payload.url) if payload.url is not None else None
    search_query = payload.search_query.strip() if payload.search_query else None
    if url is None and search_query is None:
        search_query = payload.name.strip()
    product = Product(
        name=payload.name,
        search_query=search_query,
        url=url,
        target_price=payload.target_price,
        currency=payload.currency.upper(),
        city=payload.city.strip() if payload.city else None,
        state=payload.state.upper() if payload.state else None,
    )
    session.add(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="esta URL já está cadastrada") from exc
    session.refresh(product)
    return product


@app.get("/products", response_model=list[ProductRead])
async def list_products(session: SessionDep, active: ActiveQuery = None) -> list[Product]:
    statement = select(Product).order_by(Product.id)
    if active is not None:
        statement = statement.where(Product.active.is_(active))
    return list(session.scalars(statement))


@app.get("/products/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, session: SessionDep) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    return product


@app.patch("/products/{product_id}", response_model=ProductRead)
async def update_product(product_id: int, payload: ProductUpdate, session: SessionDep) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if "url" in changes and changes["url"] is not None:
        changes["url"] = str(changes["url"])
    if changes.get("state"):
        changes["state"] = changes["state"].upper()
    if changes.get("city"):
        changes["city"] = changes["city"].strip()
    for field, value in changes.items():
        setattr(product, field, value)
    if product.search_query is None and product.url is None:
        raise HTTPException(status_code=422, detail="informe um termo de busca ou uma URL")
    session.commit()
    session.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, session: SessionDep) -> Response:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    session.delete(product)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/products/{product_id}/check", response_model=PriceCheckRead)
async def check_product(product_id: int, session: SessionDep) -> PriceCheck:
    try:
        return monitor_service(session).check_product(product_id).check
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/products/{product_id}/history", response_model=list[PriceCheckRead])
async def product_history(
    product_id: int,
    session: SessionDep,
    limit: LimitQuery = 100,
) -> list[PriceCheck]:
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    statement = (
        select(PriceCheck)
        .where(PriceCheck.product_id == product_id)
        .order_by(PriceCheck.checked_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


@app.get("/products/{product_id}/offers", response_model=list[OfferRead])
async def product_offers(product_id: int, session: SessionDep) -> list[Offer]:
    if session.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="produto não encontrado")
    statement = (
        select(Offer)
        .where(Offer.product_id == product_id, Offer.active.is_(True))
        .order_by(Offer.current_price, Offer.store)
    )
    return list(session.scalars(statement))


@app.get(
    "/products/{product_id}/offers/{offer_id}/history",
    response_model=list[OfferCheckRead],
)
async def offer_history(
    product_id: int,
    offer_id: int,
    session: SessionDep,
    limit: LimitQuery = 100,
) -> list[OfferCheck]:
    offer = session.get(Offer, offer_id)
    if offer is None or offer.product_id != product_id:
        raise HTTPException(status_code=404, detail="oferta não encontrada")
    statement = (
        select(OfferCheck)
        .where(OfferCheck.offer_id == offer_id)
        .order_by(OfferCheck.checked_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


@app.get("/settings/location", response_model=LocationRead)
async def read_location(session: SessionDep) -> LocationRead:
    location = get_default_location(session, get_settings())
    return LocationRead(city=location.city, state=location.state)


@app.patch("/settings/location", response_model=LocationRead)
async def update_location(payload: LocationUpdate, session: SessionDep) -> LocationRead:
    location = set_default_location(session, payload.city, payload.state)
    return LocationRead(city=location.city, state=location.state)


@app.get("/providers/status", response_model=list[ProviderStatusRead])
async def provider_statuses(session: SessionDep) -> list[ProviderStatusRead]:
    stored = {
        item.provider: item
        for item in session.scalars(select(ProviderStatus).order_by(ProviderStatus.provider))
    }
    return [
        ProviderStatusRead.model_validate(
            stored.get(name)
            or {
                "provider": name,
                "last_success_at": None,
                "last_error_at": None,
                "last_error": None,
            }
        )
        for name in search_provider_names()
    ]


@app.post("/checks/run", response_model=RunSummary)
async def run_checks(session: SessionDep) -> RunSummary:
    stats = monitor_service(session).run_all()
    return RunSummary(
        checked=stats.checked,
        successful=stats.successful,
        failed=stats.failed,
        alerts_sent=stats.alerts_sent,
    )
