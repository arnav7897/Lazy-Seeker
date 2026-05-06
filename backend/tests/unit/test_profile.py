"""Unit tests for profile CRUD: profile fields, projects, skills, education, experience."""
import pytest
from httpx import AsyncClient


async def _register_and_token(client: AsyncClient, email="profile@test.com") -> str:
    resp = await client.post("/auth/register", json={
        "email": email, "name": "Tester", "password": "testpass1"
    })
    return resp.json()["access_token"]


class TestProfile:
    async def test_get_profile_returns_empty_defaults(self, client: AsyncClient):
        token = await _register_and_token(client, "p1@test.com")
        resp = await client.get("/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data

    async def test_update_profile_fields(self, client: AsyncClient):
        token = await _register_and_token(client, "p2@test.com")
        resp = await client.put("/profile", headers={"Authorization": f"Bearer {token}"}, json={
            "city": "San Francisco",
            "country": "USA",
            "remote_preference": "remote",
            "salary_min": 120000,
            "salary_max": 160000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["city"] == "San Francisco"
        assert data["salary_min"] == 120000

    async def test_profile_update_is_idempotent(self, client: AsyncClient):
        token = await _register_and_token(client, "p3@test.com")
        for _ in range(3):
            await client.put("/profile", headers={"Authorization": f"Bearer {token}"}, json={
                "city": "Austin"
            })
        resp = await client.get("/profile", headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["city"] == "Austin"


class TestProjects:
    async def test_add_project(self, client: AsyncClient):
        token = await _register_and_token(client, "proj1@test.com")
        resp = await client.post("/profile/projects", headers={"Authorization": f"Bearer {token}"}, json={
            "title": "LazySeeker",
            "summary": "AI job autofill tool",
            "tech_stack": ["Python", "FastAPI"],
            "tags": ["ai", "automation"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "LazySeeker"
        assert "Python" in data["tech_stack"]

    async def test_project_do_not_use_flag(self, client: AsyncClient):
        token = await _register_and_token(client, "proj2@test.com")
        resp = await client.post("/profile/projects", headers={"Authorization": f"Bearer {token}"}, json={
            "title": "Secret Project",
            "do_not_use": True,
        })
        assert resp.status_code == 201
        assert resp.json()["do_not_use"] is True

    async def test_list_and_delete_project(self, client: AsyncClient):
        token = await _register_and_token(client, "proj3@test.com")
        headers = {"Authorization": f"Bearer {token}"}
        create = await client.post("/profile/projects", headers=headers, json={"title": "ToDelete"})
        project_id = create.json()["id"]

        # List — should contain the project
        listed = await client.get("/profile/projects", headers=headers)
        assert any(p["id"] == project_id for p in listed.json())

        # Delete
        del_resp = await client.delete(f"/profile/projects/{project_id}", headers=headers)
        assert del_resp.status_code == 204

        # No longer listed
        listed_after = await client.get("/profile/projects", headers=headers)
        assert not any(p["id"] == project_id for p in listed_after.json())

    async def test_update_project(self, client: AsyncClient):
        token = await _register_and_token(client, "proj4@test.com")
        headers = {"Authorization": f"Bearer {token}"}
        create = await client.post("/profile/projects", headers=headers, json={"title": "Old Title"})
        pid = create.json()["id"]
        update = await client.put(f"/profile/projects/{pid}", headers=headers, json={"title": "New Title"})
        assert update.status_code == 200
        assert update.json()["title"] == "New Title"


class TestSkills:
    async def test_add_skill(self, client: AsyncClient):
        token = await _register_and_token(client, "skill1@test.com")
        resp = await client.post("/profile/skills", headers={"Authorization": f"Bearer {token}"}, json={
            "name": "Python",
            "category": "language",
            "proficiency": "expert",
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "Python"

    async def test_list_skills(self, client: AsyncClient):
        token = await _register_and_token(client, "skill2@test.com")
        headers = {"Authorization": f"Bearer {token}"}
        for skill in ["Go", "Rust", "TypeScript"]:
            await client.post("/profile/skills", headers=headers, json={"name": skill})
        listed = await client.get("/profile/skills", headers=headers)
        names = [s["name"] for s in listed.json()]
        assert set(["Go", "Rust", "TypeScript"]).issubset(set(names))


class TestEducation:
    async def test_add_education(self, client: AsyncClient):
        token = await _register_and_token(client, "edu1@test.com")
        resp = await client.post("/profile/education", headers={"Authorization": f"Bearer {token}"}, json={
            "degree": "B.S.",
            "field": "Computer Science",
            "institution": "MIT",
            "graduation_year": 2022,
            "gpa": 3.8,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["institution"] == "MIT"
        assert data["gpa"] == 3.8
