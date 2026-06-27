import asyncio

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from price_monitor.api import app
from price_monitor.db import Base, get_session


def test_create_and_list_product():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    async def override_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    async def exercise_api():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            response = await client.post(
                "/products",
                json={
                    "name": "Notebook Teste",
                    "url": "https://example.com/notebook",
                    "target_price": "2500.00",
                },
            )
            assert response.status_code == 201
            assert response.json()["name"] == "Notebook Teste"
            product_id = response.json()["id"]

            response = await client.post(
                "/products",
                json={
                    "name": "Notebook duplicado",
                    "url": "https://example.com/notebook",
                    "target_price": "2000.00",
                },
            )
            assert response.status_code == 409

            response = await client.post(
                "/products",
                json={
                    "name": "ThinkPad T14",
                    "target_price": "3000.00",
                },
            )
            assert response.status_code == 201
            assert response.json()["search_query"] == "ThinkPad T14"
            assert response.json()["url"] is None
            search_product_id = response.json()["id"]

            response = await client.get(f"/products/{search_product_id}/offers")
            assert response.status_code == 200
            assert response.json() == []

            response = await client.get("/settings/location")
            assert response.status_code == 200
            assert response.json() == {"city": "Itajaí", "state": "SC"}

            response = await client.patch(
                "/settings/location", json={"city": "Balneário Camboriú", "state": "sc"}
            )
            assert response.status_code == 200
            assert response.json() == {"city": "Balneário Camboriú", "state": "SC"}

            response = await client.get("/providers/status")
            assert response.status_code == 200
            assert len(response.json()) == 6

            response = await client.get("/products")
            assert response.status_code == 200
            assert len(response.json()) == 2

            response = await client.patch(
                f"/products/{product_id}",
                json={"target_price": "2300.00", "active": False},
            )
            assert response.status_code == 200
            assert response.json()["target_price"] == "2300.00"
            assert response.json()["active"] is False

            response = await client.get(f"/products/{product_id}/history")
            assert response.status_code == 200
            assert response.json() == []

            response = await client.delete(f"/products/{product_id}")
            assert response.status_code == 204

            response = await client.get(f"/products/{product_id}")
            assert response.status_code == 404

    try:
        asyncio.run(exercise_api())
    finally:
        app.dependency_overrides.clear()
