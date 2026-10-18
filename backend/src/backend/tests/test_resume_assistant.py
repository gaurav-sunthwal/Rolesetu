"""The resume assistant's checks around the model: what it is shown, and which of
its edits are kept, applied, or held back for the user to approve.
"""

import uuid
from pathlib import Path

import pymupdf
import pytest

from backend.ai import resume_assistant
from backend.ai.resume_assistant import AssistantAnswer, ProposedEdit
from backend.core import storage
from backend.core.exceptions import RateLimitedError
from backend.modules.resume_editor import assistant
from backend.modules.resume_editor import pdf as engine
from backend.modules.resume_editor.schemas import AssistRequest, DraftLine, DraftNewLine
from backend.tests.conftest import ClientFactory

JAKE = (Path(__file__).parent / "fixtures" / "resumes" / "jake.pdf").read_bytes()
PROFILE = "Project: Rolesetu. Tech: Next.js, FastAPI. Built a job hunting assistant."


def layout() -> engine.Layout:
    with pymupdf.open(stream=JAKE) as doc:
        return engine.read_layout(doc)


def line_id(text: str) -> str:
    return next(
        item.id
        for section in layout().sections
        for item in section.lines
        if item.text.startswith(text)
    )


def context(message: str = "help", **draft: object) -> assistant.Context:
    request = AssistRequest(resume_id=uuid.uuid4(), message=message, **draft)  # type: ignore[arg-type]
    return assistant.build_context(layout(), ["Languages"], request, PROFILE)


def answer(*edits: ProposedEdit) -> AssistantAnswer:
    return AssistantAnswer(reply="Done.", edits=list(edits))


def test_the_model_sees_every_line_with_its_id_and_the_users_edits() -> None:
    mentored = line_id("Mentored")
    ctx = context(
        lines=[
            DraftLine(
                line_id=mentored,
                text="Mentored three interns",
                added=[DraftNewLine(key="k1", text="Ran the oncall rota")],
            ),
            DraftLine(line_id=line_id("Reduced p99"), removed=True),
        ]
    )
    assert f"{mentored} [bullet, max" in ctx.prompt
    assert "Mentored three interns" in ctx.prompt
    assert f"N1 [new line under {mentored}] Ran the oncall rota" in ctx.prompt
    assert "removed" in ctx.prompt
    assert "PROFILE:\n<<<\n" + PROFILE in ctx.prompt
    assert ctx.prompt.rstrip().endswith("REQUEST:\nhelp")


def test_edits_to_lines_that_do_not_exist_are_dropped() -> None:
    removed = line_id("Reduced p99")
    ctx = context(lines=[DraftLine(line_id=removed, removed=True)])
    kept = assistant.check_answer(
        answer(
            ProposedEdit(action="change", line="9-99", text="Invented"),
            ProposedEdit(action="change", line=removed, text="Back from the dead"),
            ProposedEdit(action="add_below", line=line_id("Mentored"), text=""),
            ProposedEdit(action="remove", line=line_id("Mentored")),
        ),
        ctx,
    )
    assert [(edit.kind, edit.line_id) for edit in kept] == [("remove", line_id("Mentored"))]


def test_a_new_project_from_the_profile_is_not_flagged() -> None:
    last_bullet, title = line_id("Developed a Minecraft"), line_id("Simple Paintball")
    kept = assistant.check_answer(
        answer(
            ProposedEdit(
                action="add_below", line=last_bullet, style_like=title, text="Rolesetu | Next.js"
            ),
            ProposedEdit(action="add_below", line=last_bullet, text="Built a job hunting app"),
        ),
        context("Add my Rolesetu project"),
    )
    assert [edit.style_line_id for edit in kept] == [title, None]
    assert all(edit.unsupported == [] for edit in kept)


def test_skills_and_numbers_nobody_gave_are_flagged() -> None:
    kept = assistant.check_answer(
        answer(
            ProposedEdit(
                action="change",
                line=line_id("Mentored"),
                text="Mentored 6 interns and led a migration to Kubernetes, cutting costs by 40%",
            ),
            ProposedEdit(action="add_skill", text="Rust"),
            ProposedEdit(action="add_skill", text="Terraform"),
        ),
        context("Add Terraform to my skills"),
    )
    # "14" and "two" were in the line; 6, 40% and Rust came from nowhere.
    assert kept[0].unsupported == ["6", "40%"]
    assert kept[1].unsupported == ["Rust"]
    assert kept[2].unsupported == []


def test_numbers_and_skills_the_user_typed_are_fine() -> None:
    kept = assistant.check_answer(
        answer(
            ProposedEdit(
                action="change",
                line=line_id("Mentored"),
                text="Mentored 6 interns and moved 14 cron jobs to Rust",
            )
        ),
        context("I mentored 6 interns, and the jobs were rewritten in Rust"),
    )
    assert kept[0].unsupported == []


def test_edits_to_lines_the_user_added_point_at_them() -> None:
    mentored = line_id("Mentored")
    ctx = context(
        lines=[DraftLine(line_id=mentored, added=[DraftNewLine(key="k1", text="Ran oncall")])]
    )
    kept = assistant.check_answer(
        answer(
            ProposedEdit(action="change", line="N1", text="Ran the oncall rota"),
            ProposedEdit(action="add_below", line="N1", text="Wrote the runbook"),
        ),
        ctx,
    )
    assert [(edit.kind, edit.line_id, edit.new_key) for edit in kept] == [
        ("change", mentored, "k1"),
        ("add_below", mentored, "k1"),
    ]


def test_too_many_messages_are_slowed_down() -> None:
    key = uuid.uuid4().hex
    for _ in range(assistant.MAX_MESSAGES):
        assistant.check_rate(key)
    with pytest.raises(RateLimitedError):
        assistant.check_rate(key)


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    async def put_file(key: str, data: bytes, *, content_type: str) -> None:
        files[key] = data

    async def get_file(key: str) -> bytes:
        return files[key]

    async def delete_file(key: str) -> None:
        files.pop(key, None)

    monkeypatch.setattr(storage, "put_file", put_file)
    monkeypatch.setattr(storage, "get_file", get_file)
    monkeypatch.setattr(storage, "delete_file", delete_file)
    return files


async def test_the_endpoint_answers_with_checked_edits(
    make_client: ClientFactory, bucket: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    shown: list[str] = []

    async def fake_model(prompt: str, *, user_api_key: str | None) -> AssistantAnswer:
        shown.append(prompt)
        return answer(
            ProposedEdit(action="change", line=line_id("Razorpay"), text="Razorpay Inc"),
            ProposedEdit(action="change", line="7-7", text="Nowhere"),
        )

    monkeypatch.setattr(resume_assistant, "propose_edits", fake_model)
    first, second = make_client(), make_client()
    uploaded = await first.post(
        "/api/v1/resume", files={"file": ("resume.pdf", JAKE, "application/pdf")}
    )
    body = {"resume_id": uploaded.json()["id"], "message": "Call it Razorpay Inc"}

    response = await first.post("/api/v1/resume-editor/assist", json=body)
    assert response.status_code == 200, response.text
    reply = response.json()
    assert reply["reply"] == "Done."
    assert [(edit["kind"], edit["text"]) for edit in reply["edits"]] == [("change", "Razorpay Inc")]
    assert reply["edits"][0]["before"] == "Razorpay"
    assert "Call it Razorpay Inc" in shown[0]

    # Another user cannot ask about this resume.
    assert (await second.post("/api/v1/resume-editor/assist", json=body)).status_code == 404


def test_the_model_sees_links_and_can_readdress_them() -> None:
    ctx = context("My LinkedIn is linkedin.com/in/karan-m now")
    assert '0-L1 [link] "linkedin.com/in/karanmehta" opens https://linkedin.com/in/karanmehta' in (
        ctx.prompt
    )
    kept = assistant.check_answer(
        answer(
            ProposedEdit(action="set_link", line="0-L1", text="linkedin.com/in/karan-m"),
            # A guessed address, an unknown link, and a script are not links.
            ProposedEdit(action="set_link", line="0-L2", text="https://github.com/guess"),
            ProposedEdit(action="set_link", line="0-L9", text="https://example.com"),
            ProposedEdit(action="set_link", line="0-L1", text="javascript:alert(1)"),
        ),
        ctx,
    )
    assert [(edit.link_id, edit.text, edit.unsupported) for edit in kept] == [
        ("0-L1", "https://linkedin.com/in/karan-m", []),
        ("0-L2", "https://github.com/guess", ["https://github.com/guess"]),
    ]
    assert kept[0].line_id == line_id("+91")


def test_an_address_nobody_gave_is_flagged_in_new_lines() -> None:
    kept = assistant.check_answer(
        answer(
            ProposedEdit(
                action="add_below",
                line=line_id("Developed a Minecraft"),
                text="Rolesetu | github.com/karanm/rolesetu",
            )
        ),
        context("Add my Rolesetu project"),
    )
    assert kept[0].unsupported == ["github.com/karanm/rolesetu"]
