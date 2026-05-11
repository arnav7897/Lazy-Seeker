"""Unit tests for auth endpoints: register, login, JWT, /me."""
import pytest
from httpx import AsyncClient


class TestRegister:
    async def test_register_creates_user(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "alice@example.com",
            "name": "Alice",
            "password": "securepass",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_duplicate_email_returns_409(self, client: AsyncClient):
        payload = {"email": "bob@example.com", "name": "Bob", "password": "securepass"}
        await client.post("/auth/register", json=payload)
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_short_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "c@c.com", "name": "C", "password": "short"
        })
        assert resp.status_code == 422

    async def test_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/auth/register", json={
            "email": "not-an-email", "name": "D", "password": "longpassword"
        })
        assert resp.status_code == 422


class TestLogin:
    async def test_login_returns_jwt(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "email": "dave@example.com", "name": "Dave", "password": "mypassword"
        })
        resp = await client.post("/auth/login", json={
            "email": "dave@example.com", "password": "mypassword"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_invalid_password_returns_401(self, client: AsyncClient):
        await client.post("/auth/register", json={
            "email": "eve@example.com", "name": "Eve", "password": "correctpassword"
        })
        resp = await client.post("/auth/login", json={
            "email": "eve@example.com", "password": "wrongpassword"
        })
        assert resp.status_code == 401

    async def test_unknown_email_returns_401(self, client: AsyncClient):
        resp = await client.post("/auth/login", json={
            "email": "nobody@example.com", "password": "anypassword"
        })
        assert resp.status_code == 401


class TestMe:
    async def test_me_returns_user(self, client: AsyncClient):
        reg = await client.post("/auth/register", json={
            "email": "frank@example.com", "name": "Frank", "password": "password1"
        })
        token = reg.json()["access_token"]
        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "frank@example.com"
        assert data["name"] == "Frank"

    async def test_me_without_token_returns_403(self, client: AsyncClient):
        resp = await client.get("/auth/me")
        assert resp.status_code in (401, 403)

    async def test_me_with_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
