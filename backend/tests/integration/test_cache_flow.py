"""Integration tests: answer cache end-to-end flow across multiple applications."""
import pytest
from httpx import AsyncClient


async def _register_and_token(client: AsyncClient, email: str) -> str:
    resp = await client.post("/auth/register", json={
        "email": email, "name": "Integration Tester", "password": "integrationpass"
    })
    return resp.json()["access_token"]


class TestCacheFlow:
    async def test_store_then_match_exact(self, client: AsyncClient):
        """Store an answer, then retrieve it via the match endpoint."""
        token = await _register_and_token(client, "flow1@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        # Store
        store_resp = await client.post("/cache/answers", headers=headers, json={
            "question_text": "Why do you want to work at this company?",
            "answer_text": "I admire the mission and culture deeply.",
            "question_type": "why_company",
        })
        assert store_resp.status_code == 201

        # Match the exact same question
        match_resp = await client.get(
            "/cache/answers/match",
            headers=headers,
            params={"question": "Why do you want to work at this company?"},
        )
        assert match_resp.status_code == 200
        data = match_resp.json()
        assert data["hit"] is True
        assert data["answer"]["answer_text"] == "I admire the mission and culture deeply."

    async def test_second_application_reuses_cached_answer(self, client: AsyncClient):
        """Simulates second application with same type of question."""
        token = await _register_and_token(client, "flow2@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        # First application: store answer
        await client.post("/cache/answers", headers=headers, json={
            "question_text": "What are your top technical skills?",
            "answer_text": "Python, FastAPI, PostgreSQL, and ML experience.",
        })

        # Second application: similar question
        match = await client.get(
            "/cache/answers/match",
            headers=headers,
            params={"question": "What technical skills do you bring to this role?"},
        )
        assert match.status_code == 200
        # Should get hit or suggestion (score > REVIEW_THRESHOLD)
        assert match.json()["score"] > 0.5

    async def test_pinned_answer_always_returned(self, client: AsyncClient):
        """Pin an answer and verify it can be listed and pinned status persists."""
        token = await _register_and_token(client, "flow3@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        store = await client.post("/cache/answers", headers=headers, json={
            "question_text": "Tell me about yourself.",
            "answer_text": "I'm a software engineer with 5 years of experience.",
        })
        cache_id = store.json()["id"]

        # Pin it
        pin_resp = await client.put(
            f"/cache/answers/{cache_id}/pin",
            headers=headers,
            params={"pinned": True},
        )
        assert pin_resp.status_code == 200
        assert pin_resp.json()["is_pinned"] is True

        # List and verify pin persisted
        listed = await client.get("/cache/answers", headers=headers)
        pinned_entries = [a for a in listed.json() if a["is_pinned"]]
        assert any(a["id"] == cache_id for a in pinned_entries)

    async def test_edit_cached_answer(self, client: AsyncClient):
        token = await _register_and_token(client, "flow4@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        store = await client.post("/cache/answers", headers=headers, json={
            "question_text": "What is your weakness?",
            "answer_text": "Original answer.",
        })
        cache_id = store.json()["id"]

        edit = await client.put(f"/cache/answers/{cache_id}", headers=headers, json={
            "answer_text": "Updated: I sometimes focus too much on details."
        })
        assert edit.status_code == 200
        assert "Updated" in edit.json()["answer_text"]

    async def test_delete_cached_answer(self, client: AsyncClient):
        token = await _register_and_token(client, "flow5@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        store = await client.post("/cache/answers", headers=headers, json={
            "question_text": "What is your salary expectation?",
            "answer_text": "$120,000 - $150,000.",
        })
        cache_id = store.json()["id"]

        del_resp = await client.delete(f"/cache/answers/{cache_id}", headers=headers)
        assert del_resp.status_code == 204

        # Verify gone
        listed = await client.get("/cache/answers", headers=headers)
        assert not any(a["id"] == cache_id for a in listed.json())
