"""Invite a friend, pay ₹149: codes, who can claim them, when a friend counts, and
the cheaper month, through the API and database. Razorpay is the fake from the
billing tests.

Skipped until migration a2c4e6f8b0d1 has been applied to the database the tests use.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from backend.db.session import get_sessionmaker
from backend.modules.referrals import service as referrals
from backend.tests.conftest import ClientFactory
from backend.tests.test_billing import API, FakeRazorpay, install_fake_razorpay, sign


@pytest.fixture(autouse=True)
async def _needs_tables() -> None:
    async with get_sessionmaker()() as db:
        found = await db.execute(text("select to_regclass('public.referrals')"))
        if found.scalar_one() is None:
            pytest.skip("Apply migration a2c4e6f8b0d1 to run these tests.")


@pytest.fixture
def fake_razorpay(monkeypatch: pytest.MonkeyPatch) -> FakeRazorpay:
    return install_fake_razorpay(monkeypatch)


async def user_id_of(client: AsyncClient) -> uuid.UUID:
    return uuid.UUID((await client.get(f"{API}/users/me")).json()["id"])


async def summary(client: AsyncClient) -> dict[str, Any]:
    response = await client.get(f"{API}/referrals/me")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def claim(client: AsyncClient, code: str) -> int:
    response = await client.post(f"{API}/referrals/claim", json={"code": code})
    return response.status_code


async def use_rolesetu(client: AsyncClient, checks: int = referrals.CHECKS_NEEDED) -> None:
    """What a friend who really uses Rolesetu leaves behind: a resume and job checks."""
    user_id = await user_id_of(client)
    async with get_sessionmaker()() as db:
        await db.execute(
            text(
                "INSERT INTO resume_files (id, user_id, storage_key, filename, size_bytes, status)"
                " VALUES (:id, :u, 'test/none.pdf', 'resume.pdf', 1, 'parsed')"
            ),
            {"id": uuid.uuid4(), "u": user_id},
        )
        for _ in range(checks):
            job_id = uuid.uuid4()
            await db.execute(
                text(
                    "INSERT INTO jobs (id, user_id, jd_text, content_hash)"
                    " VALUES (:id, :u, 'A job.', :h)"
                ),
                {"id": job_id, "u": user_id, "h": uuid.uuid4().hex},
            )
            await db.execute(
                text(
                    "INSERT INTO matches (id, user_id, job_id, profile_version, status,"
                    " skill_results, gaps) VALUES (:id, :u, :j, 1, 'completed', '[]', '[]')"
                ),
                {"id": uuid.uuid4(), "u": user_id, "j": job_id},
            )
        await db.commit()


async def test_a_user_gets_one_code_that_stays_the_same(client: AsyncClient) -> None:
    first = await summary(client)
    second = await summary(client)
    assert first["code"] == second["code"]
    assert len(first["code"]) == 8 and first["code"].isalnum()
    assert first["friends"] == [] and first["rewards_available"] == 0
    assert first["referral_amount"] == 14900 and first["checks_needed"] == 3


async def test_who_can_claim_a_code(make_client: ClientFactory) -> None:
    owner, friend, other_owner = make_client(), make_client(), make_client()
    code = (await summary(owner))["code"]
    other_code = (await summary(other_owner))["code"]

    assert await claim(owner, code) == 422  # not your own
    assert await claim(friend, "NOSUCH99") == 404
    assert await claim(friend, code.lower()) == 204  # typed in lower case still works
    assert await claim(friend, code) == 204  # asking again is fine
    assert await claim(friend, other_code) == 409  # but not switching who invited you
    assert [f["status"] for f in (await summary(owner))["friends"]] == ["joined"]
    assert (await summary(other_owner))["friends"] == []


async def test_an_old_account_cannot_be_claimed(make_client: ClientFactory) -> None:
    owner, old = make_client(), make_client()
    code = (await summary(owner))["code"]
    old_id = await user_id_of(old)
    async with get_sessionmaker()() as db:
        await db.execute(
            text("UPDATE users SET created_at = :at WHERE id = :id"),
            {"at": datetime.now(UTC) - timedelta(days=30), "id": old_id},
        )
        await db.commit()
    assert await claim(old, code) == 422


async def test_a_friend_counts_only_after_really_using_rolesetu(
    make_client: ClientFactory,
) -> None:
    owner, friend = make_client(), make_client()
    code = (await summary(owner))["code"]
    assert await claim(friend, code) == 204

    await use_rolesetu(friend, checks=2)
    assert (await summary(owner))["rewards_available"] == 0

    await use_rolesetu(friend, checks=1)
    found = await summary(owner)
    assert [f["status"] for f in found["friends"]] == ["unlocked"]
    assert found["rewards_available"] == 1
    # Only how far the friend got: nothing that says who they are.
    assert set(found["friends"][0]) == {"joined_at", "status"}


async def invited_and_active(make_client: ClientFactory) -> AsyncClient:
    owner, friend = make_client(), make_client()
    assert await claim(friend, (await summary(owner))["code"]) == 204
    await use_rolesetu(friend)
    return owner


async def test_a_reward_makes_one_month_cost_149(
    make_client: ClientFactory, fake_razorpay: FakeRazorpay
) -> None:
    owner = await invited_and_active(make_client)
    plan = (await owner.get(f"{API}/billing/me")).json()
    assert plan["referral_price"] is True and plan["price"]["amount"] == 14900

    order = (await owner.post(f"{API}/billing/orders", json={"plan": "pro_month"})).json()
    assert order["amount"] == 14900
    assert fake_razorpay.orders[order["order_id"]]["amount"] == 14900

    payment_id = fake_razorpay.pay(order["order_id"])
    paid = await owner.post(
        f"{API}/billing/orders/verify",
        json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": payment_id,
            "razorpay_signature": sign(order["order_id"], payment_id),
        },
    )
    assert paid.status_code == 200, paid.text
    after = paid.json()
    assert after["plan"] == "pro"
    assert after["payments"][0]["amount"] == 14900
    # The reward is spent: the next month is full price again.
    assert after["referral_price"] is False and after["price"]["amount"] == 19900
    found = await summary(owner)
    assert found["rewards_available"] == 0
    assert [f["status"] for f in found["friends"]] == ["used"]


async def test_an_unpaid_order_does_not_use_up_the_reward(
    make_client: ClientFactory, fake_razorpay: FakeRazorpay
) -> None:
    owner = await invited_and_active(make_client)
    first = (await owner.post(f"{API}/billing/orders", json={"plan": "pro_month"})).json()
    assert first["amount"] == 14900
    # Checkout closed without paying: the reward is still there for the next try.
    assert (await summary(owner))["rewards_available"] == 1
    second = (await owner.post(f"{API}/billing/orders", json={"plan": "pro_month"})).json()
    assert second["amount"] == 14900


async def test_without_a_reward_the_price_is_the_full_one(
    client: AsyncClient, fake_razorpay: FakeRazorpay
) -> None:
    plan = (await client.get(f"{API}/billing/me")).json()
    assert plan["referral_price"] is False and plan["price"]["amount"] == 19900
    order = (await client.post(f"{API}/billing/orders", json={"plan": "pro_month"})).json()
    assert order["amount"] == 19900
