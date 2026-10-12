import time
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from backend.core.encryption import encrypt_text
from backend.modules.inbox import gmail
from backend.tests.conftest import ClientFactory

BASE = "/api/v1/inbox"
NOW = datetime.now(UTC)
# A day that is still ahead when the interview mail (3 days old) was sent.
INTERVIEW_DAY = (NOW + timedelta(days=4)).date()


def mail(
    number: int, subject: str, sender: str, address: str, body: str, days_ago: int
) -> gmail.RawMail:
    return gmail.RawMail(
        id=f"m{number}",
        sender_name=sender,
        sender_email=address,
        subject=subject,
        received_at=NOW - timedelta(days=days_ago),
        body=body,
    )


MAILS = [
    mail(1, "Thank you for applying to Razorpay", "Razorpay Careers", "jobs@razorpay.com",
         "We received your application for the Backend Engineer role.", 6),
    mail(2, "Update on your application at Acme", "Acme Recruiting", "talent@acme.com",
         "Unfortunately we have decided to move forward with other candidates.", 2),
    mail(3, "Next steps", "Greenhouse", "no-reply@greenhouse.io",
         "Please see the attached document about the position.", 1),
    mail(4, "12 new jobs for you", "LinkedIn", "alerts@linkedin.com", "Apply now", 1),
    mail(5, "Interview invitation - Backend Engineer", "Razorpay Careers", "jobs@razorpay.com",
         f"Your interview is scheduled on {INTERVIEW_DAY:%d %B %Y} at 3:00 PM IST. "
         "Join: https://meet.google.com/abc-defg-hij", 3),
]  # fmt: skip


class FakeMailbox:
    """Stands in for Gmail. Records what it was asked, to prove bodies are only read."""

    queries: list[str] = []

    def __init__(self, access_token: str) -> None:
        assert access_token == "access"

    async def address(self) -> str:
        return "me@example.com"

    async def list_ids(self, query: str, limit: int) -> list[str]:
        FakeMailbox.queries.append(query)
        return [item.id for item in MAILS]

    async def read(self, message_id: str) -> gmail.RawMail:
        return next(item for item in MAILS if item.id == message_id)


@pytest.fixture(autouse=True)
def google(monkeypatch: pytest.MonkeyPatch) -> None:
    async def exchange_code(code: str) -> tuple[str, str]:
        return "refresh", "access"

    async def access_token_for(refresh_token: str) -> str:
        assert refresh_token == "refresh"
        return "access"

    async def revoke(refresh_token: str) -> None:
        return None

    FakeMailbox.queries = []
    monkeypatch.setattr(gmail, "exchange_code", exchange_code)
    monkeypatch.setattr(gmail, "access_token_for", access_token_for)
    monkeypatch.setattr(gmail, "revoke", revoke)
    monkeypatch.setattr(gmail, "GmailMailbox", FakeMailbox)


async def connect(client: AsyncClient) -> None:
    """Does what Google's redirect does after the consent screen."""
    user_id = (await client.get("/api/v1/users/me")).json()["id"]
    state = encrypt_text(f"{user_id}|{int(time.time())}")
    response = await client.get(f"{BASE}/gmail/callback", params={"code": "c", "state": state})
    assert response.status_code == 307
    assert response.headers["location"].endswith("gmail=connected")


async def test_connecting_reads_recent_mail_and_updates_the_tracker(client: AsyncClient) -> None:
    tracked = await client.post(
        "/api/v1/applications",
        json={
            "role": "React Native Developer",
            "company": "Acme Technologies",
            "status": "applied",
        },
    )
    assert tracked.status_code == 201, tracked.text

    before = (await client.get(f"{BASE}/status")).json()
    assert (before["connected"], before["lookback_days"]) == (False, 15)

    await connect(client)  # the first sync runs straight after connecting

    status = (await client.get(f"{BASE}/status")).json()
    assert (status["connected"], status["account_email"]) == (True, "me@example.com")
    assert (status["sync_status"], status["last_error"]) == ("idle", None)
    assert status["review_count"] == 1
    assert FakeMailbox.queries[0].startswith("newer_than:15d ")

    messages = (await client.get(f"{BASE}/messages")).json()["items"]
    # The job alert was never kept. Newest first.
    assert [(m["subject"], m["kind"], m["state"]) for m in messages] == [
        ("Next steps", "unclear", "review"),
        ("Update on your application at Acme", "rejected", "linked"),
        ("Interview invitation - Backend Engineer", "interview", "linked"),
        ("Thank you for applying to Razorpay", "applied", "created"),
    ]
    assert "body" not in messages[0]
    # Each mail can be opened in the user's own Gmail, in the right account.
    assert messages[1]["gmail_url"] == (
        "https://mail.google.com/mail/?authuser=me%40example.com#all/m2"
    )

    applications = (await client.get("/api/v1/applications")).json()["items"]
    by_company = {item["company"]: item for item in applications}
    # The tracked application was rejected; a new one was found and has moved to interview.
    assert by_company["Acme Technologies"]["status"] == "rejected"
    assert by_company["Razorpay"]["status"] == "interview"
    assert by_company["Razorpay"]["role"] == "Backend Engineer"
    # Each row links to the newest mail about it (the interview, not the first mail).
    assert by_company["Razorpay"]["gmail_url"].endswith("#all/m5")
    assert by_company["Acme Technologies"]["gmail_url"].endswith("#all/m2")

    detail = (await client.get(f"/api/v1/applications/{by_company['Razorpay']['id']}")).json()
    assert {(event["type"], event["source"]) for event in detail["events"]} == {
        ("applied", "gmail"),
        ("interview", "gmail"),
    }

    # The mails about one application can be listed on their own, oldest news last.
    about = await client.get(
        f"{BASE}/messages", params={"application_id": by_company["Razorpay"]["id"]}
    )
    assert [m["kind"] for m in about.json()["items"]] == ["interview", "applied"]

    # Reading the inbox again adds nothing twice.
    again = await client.post(f"{BASE}/sync")
    assert again.status_code == 202, again.text
    assert len((await client.get(f"{BASE}/messages")).json()["items"]) == 4
    assert len((await client.get("/api/v1/applications")).json()["items"]) == 2

    insights = (await client.get(f"{BASE}/insights")).json()
    assert insights["totals"] == {
        "applied": 2, "waiting": 0, "rejected": 1, "interviews": 1, "offers": 0,
    }  # fmt: skip
    assert insights["findings"][0]["title"] == "Some rejections cannot be explained yet"


async def test_review_list_lets_the_user_decide(client: AsyncClient) -> None:
    await connect(client)
    review = (await client.get(f"{BASE}/messages", params={"state": "review"})).json()["items"]
    assert [item["subject"] for item in review] == ["Next steps"]
    applications = (await client.get("/api/v1/applications")).json()["items"]
    razorpay = next(item for item in applications if item["company"] == "Razorpay")

    linked = await client.patch(
        f"{BASE}/messages/{review[0]['id']}",
        json={"action": "link", "application_id": razorpay["id"]},
    )
    assert linked.status_code == 200, linked.text
    assert (linked.json()["state"], linked.json()["application_id"]) == ("linked", razorpay["id"])
    assert (await client.get(f"{BASE}/status")).json()["review_count"] == 0

    missing = await client.patch(f"{BASE}/messages/{review[0]['id']}", json={"action": "link"})
    assert missing.status_code == 422


async def test_mail_records_belong_to_one_user_and_go_when_disconnected(
    make_client: ClientFactory,
) -> None:
    owner, stranger = make_client(), make_client()
    await connect(owner)
    mine = (await owner.get(f"{BASE}/messages")).json()["items"]
    assert len(mine) == 4

    assert (await stranger.get(f"{BASE}/messages")).json()["items"] == []
    assert (await stranger.get(f"{BASE}/status")).json()["connected"] is False
    blocked = await stranger.patch(f"{BASE}/messages/{mine[0]['id']}", json={"action": "dismiss"})
    assert blocked.status_code == 404
    assert (await stranger.post(f"{BASE}/sync")).status_code == 404

    assert (await owner.delete(f"{BASE}/gmail")).status_code == 204
    assert (await owner.get(f"{BASE}/status")).json()["connected"] is False
    assert (await owner.get(f"{BASE}/messages")).json()["items"] == []
    # The tracker is the user's own record and stays.
    assert len((await owner.get("/api/v1/applications")).json()["items"]) == 2


async def test_the_callback_never_trusts_a_forged_or_old_state(client: AsyncClient) -> None:
    user_id = (await client.get("/api/v1/users/me")).json()["id"]
    old = encrypt_text(f"{user_id}|{int(time.time()) - 3600}")

    for params, outcome in [
        ({"code": "c", "state": "not-a-real-state"}, "expired"),
        ({"code": "c", "state": old}, "expired"),
        ({"error": "access_denied", "state": old}, "denied"),
    ]:
        response = await client.get(f"{BASE}/gmail/callback", params=params)
        assert response.headers["location"].endswith(f"gmail={outcome}")
    assert (await client.get(f"{BASE}/status")).json()["connected"] is False


async def test_an_interview_mail_becomes_a_scheduled_interview(make_client: ClientFactory) -> None:
    owner, stranger = make_client(), make_client()
    await connect(owner)

    interviews = (await owner.get(f"{BASE}/interviews")).json()
    assert len(interviews) == 1
    found = interviews[0]
    assert (found["company"], found["role"]) == ("Razorpay", "Backend Engineer")
    # 3:00 PM in India is 09:30 UTC.
    assert found["starts_at"].startswith(f"{INTERVIEW_DAY.isoformat()}T09:30")
    assert (found["has_time"], found["link"]) == (True, "https://meet.google.com/abc-defg-hij")
    assert found["mail_subject"] == "Interview invitation - Backend Engineer"
    assert found["gmail_url"].endswith("#all/m5")
    assert found["application_id"] is not None

    # The user can correct it, and a later sync leaves their time alone.
    moved = f"{INTERVIEW_DAY.isoformat()}T11:00:00+00:00"
    changed = await owner.patch(
        f"{BASE}/interviews/{found['id']}", json={"starts_at": moved, "location": "Office"}
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["location"], changed.json()["link"]) == ("Office", found["link"])
    await owner.post(f"{BASE}/sync")
    again = (await owner.get(f"{BASE}/interviews")).json()
    assert len(again) == 1 and again[0]["starts_at"].startswith(
        f"{INTERVIEW_DAY.isoformat()}T11:00"
    )

    bad = await owner.patch(
        f"{BASE}/interviews/{found['id']}", json={"starts_at": moved, "ends_at": moved}
    )
    assert bad.status_code == 422

    # Another user cannot see, change or remove it.
    assert (await stranger.get(f"{BASE}/interviews")).json() == []
    path = f"{BASE}/interviews/{found['id']}"
    assert (await stranger.patch(path, json={"location": "x"})).status_code == 404
    assert (await stranger.delete(path)).status_code == 404

    assert (await owner.delete(path)).status_code == 204
    assert (await owner.get(f"{BASE}/interviews")).json() == []
