"""The resume editor: every line of a resume can be changed, removed or have a
line added under it, and the page must look exactly as it did everywhere else.
"""

from pathlib import Path

import pymupdf
import pytest

from backend.modules.resume_editor import pdf as engine
from backend.modules.resume_editor.pdf import AddLine, ChangeText, RemoveLine
from backend.modules.tailoring.pdf.section import read_lines

RESUMES = Path(__file__).parent / "fixtures" / "resumes"


def pdf(name: str) -> bytes:
    return (RESUMES / f"{name}.pdf").read_bytes()


def layout_of(data: bytes) -> engine.Layout:
    with pymupdf.open(stream=data) as doc:
        return engine.read_layout(doc)


def line_id(data: bytes, text: str) -> str:
    """The id of the line whose words start with `text`."""
    return next(
        item.id
        for section in layout_of(data).sections
        for item in section.lines
        if item.text.startswith(text)
    )


def lines_of(data: bytes) -> dict[str, tuple[float, float, float]]:
    """Each line's text -> (x0, x1, baseline)."""
    with pymupdf.open(stream=data) as doc:
        return {line.text: (line.x0, line.x1, line.baseline) for line in read_lines(doc[0])}


def drawn_bullets(data: bytes) -> int:
    with pymupdf.open(stream=data) as doc:
        return sum(1 for d in doc[0].get_drawings() if d["rect"].width < 8 and d["rect"].height < 8)


def test_lines_are_grouped_under_their_headings() -> None:
    sections = layout_of(pdf("jake")).sections
    assert [section.title for section in sections] == [
        "Header",
        "Education",
        "Experience",
        "Projects",
        "Technical Skills",
    ]
    experience = sections[2]
    assert experience.lines[0].heading
    # A bullet is kept apart from the words, so it cannot be typed over.
    bullet = next(item for item in experience.lines if item.prefix)
    assert bullet.prefix == "•"
    assert bullet.text.startswith("Developed a payment")
    # A date at the right margin grows to the left.
    assert next(item for item in experience.lines if "Present" in item.text).right_aligned


def test_columns_keep_their_own_sections() -> None:
    layout = layout_of(pdf("twocol"))
    titles = {section.title: section for section in layout.sections}
    assert "Django" in [item.text for item in titles["SKILLS"].lines]
    assert "Infosys Limited" in [item.text for item in titles["WORK EXPERIENCE"].lines]
    assert layout.multi_column == {0}


def test_changing_words_leaves_every_other_line_where_it_was() -> None:
    original = pdf("jake")
    edited, outcomes = engine.apply_edits(
        original, [ChangeText(line_id(original, "Mentored"), "Mentored three interns")]
    )
    assert outcomes[0].applied
    before, after = lines_of(original), lines_of(edited)
    assert "• Mentored three interns" in after
    assert "• Mentored two interns and led the migration of 14 cron jobs to Temporal workflows" in (
        before
    )
    for text, place in before.items():
        if not text.startswith("• Mentored"):
            assert after[text] == pytest.approx(place, abs=0.01)


def test_a_right_aligned_date_grows_to_the_left() -> None:
    original = pdf("jake")
    edited, outcomes = engine.apply_edits(
        original, [ChangeText(line_id(original, "July 2023"), "September 2023 – Present")]
    )
    assert outcomes[0].applied
    old, new = (
        lines_of(original)["July 2023 – Present"],
        lines_of(edited)["September 2023 – Present"],
    )
    assert new[1] == pytest.approx(old[1], abs=0.5)
    assert new[0] < old[0]


def test_removing_a_line_closes_the_gap() -> None:
    original = pdf("jake")
    edited, outcomes = engine.apply_edits(original, [RemoveLine(line_id(original, "Reduced p99"))])
    assert outcomes[0].applied
    before, after = lines_of(original), lines_of(edited)
    assert not any("Reduced p99" in text for text in after)
    gap = before["Microsoft"][2] - after["Microsoft"][2]
    assert gap == pytest.approx(
        before[
            "• Mentored two interns and led the migration of 14 cron jobs to Temporal workflows"
        ][2]
        - before[
            "• Reduced p99 latency of the refunds API from 900ms to 210ms by adding Redis "
            "caching and tuning PostgreSQL indexes"
        ][2],
        abs=0.1,
    )
    # Above the removed line nothing moves.
    assert after["Razorpay"] == pytest.approx(before["Razorpay"], abs=0.01)


def test_an_added_line_copies_the_bullet_and_style_above_it() -> None:
    original = pdf("jake")
    anchor = line_id(original, "Mentored")
    edited, outcomes = engine.apply_edits(original, [AddLine(anchor, "Ran the oncall rota")])
    assert outcomes[0].applied
    with pymupdf.open(stream=edited) as doc:
        new = next(line for line in read_lines(doc[0]) if "oncall" in line.text)
        above = next(line for line in read_lines(doc[0]) if "Mentored" in line.text)
    assert new.text == "• Ran the oncall rota"
    assert new.x0 == pytest.approx(above.x0, abs=0.5)
    assert new.style == above.style
    # What was below moved down to make room.
    assert lines_of(edited)["Microsoft"][2] > lines_of(original)["Microsoft"][2]


def test_a_long_new_line_wraps_under_its_own_words() -> None:
    original = pdf("jake")
    words = "Designed an idempotent payouts API used by three teams " * 3
    edited, outcomes = engine.apply_edits(
        original, [AddLine(line_id(original, "Mentored"), words.strip())]
    )
    assert outcomes[0].applied
    with pymupdf.open(stream=edited) as doc:
        added = [
            line for line in read_lines(doc[0]) if "payouts" in line.text or "teams" in line.text
        ]
    assert len(added) >= 2
    # The wrapped line starts where the words start, not under the bullet.
    assert added[1].x0 > added[0].x0


def test_drawn_bullets_are_copied_and_removed_with_their_line() -> None:
    original = pdf("classic")
    dots = drawn_bullets(original)
    added, outcomes = engine.apply_edits(
        original, [AddLine(line_id(original, "Built the seller"), "Added Playwright tests")]
    )
    assert outcomes[0].applied
    assert drawn_bullets(added) == dots + 1
    removed, outcomes = engine.apply_edits(
        original, [RemoveLine(line_id(original, "Shipped a REST API"))]
    )
    assert outcomes[0].applied
    assert drawn_bullets(removed) == dots - 1


def test_several_edits_at_once() -> None:
    original = pdf("jake")
    ids = {text: line_id(original, text) for text in ("Razorpay", "Reduced", "Mentored", "Class")}
    edited, outcomes = engine.apply_edits(
        original,
        [
            ChangeText(ids["Razorpay"], "Razorpay Software"),
            RemoveLine(ids["Reduced"]),
            AddLine(ids["Mentored"], "Ran the oncall rota"),
            RemoveLine(ids["Class"]),
        ],
    )
    assert all(outcome.applied for outcome in outcomes)
    text = "\n".join(lines_of(edited))
    assert "Razorpay Software" in text
    assert "Reduced p99" not in text
    assert "Class XII" not in text
    assert "• Ran the oncall rota" in text


def test_edits_that_cannot_be_made_say_why() -> None:
    original = pdf("jake")
    # The date sits at the right end of this line, so the title cannot grow into it.
    too_long = "Software Development Engineer II, Platform Lead for Payments and Refunds " * 2
    _, outcomes = engine.apply_edits(
        original,
        [
            ChangeText(line_id(original, "Software Development"), too_long),
            # "Languages" is bold and the list after it is not.
            ChangeText(line_id(original, "Languages"), "Langs and Go, Java"),
            ChangeText("9-9", "No such line"),
        ],
    )
    assert [outcome.reason for outcome in outcomes] == ["no_room", "mixed_style", "not_found"]


def test_lines_are_not_added_on_a_page_in_columns() -> None:
    original = pdf("twocol")
    edited, outcomes = engine.apply_edits(
        original,
        [
            AddLine(line_id(original, "Django"), "Flask"),
            RemoveLine(line_id(original, "Redis")),
        ],
    )
    assert outcomes[0].reason == "two_columns"
    assert outcomes[1].applied
    before, after = lines_of(original), lines_of(edited)
    assert "Redis" not in after
    # Neither column moved.
    assert after["Infosys Limited"] == pytest.approx(before["Infosys Limited"], abs=0.01)
    assert after["PostgreSQL"] == pytest.approx(before["PostgreSQL"], abs=0.01)


def test_a_changed_resume_can_be_edited_again() -> None:
    original = pdf("jake")
    once, _ = engine.apply_edits(original, [AddLine(line_id(original, "Mentored"), "Ran oncall")])
    twice, outcomes = engine.apply_edits(
        once, [ChangeText(line_id(once, "Ran oncall"), "Led oncall")]
    )
    assert outcomes[0].applied
    assert "• Led oncall" in lines_of(twice)


def test_new_lines_keep_their_order_and_can_replace_a_removed_line() -> None:
    original = pdf("jake")
    anchor = line_id(original, "Reduced p99")
    edited, outcomes = engine.apply_edits(
        original,
        [
            AddLine(anchor, "First new point"),
            AddLine(anchor, "Second new point"),
            RemoveLine(anchor),
        ],
    )
    assert all(outcome.applied for outcome in outcomes)
    order = [text for text in lines_of(edited) if text.startswith("• ")]
    first, second = order.index("• First new point"), order.index("• Second new point")
    mentored = next(i for i, text in enumerate(order) if text.startswith("• Mentored"))
    assert first + 1 == second and second + 1 == mentored
    # The first new line sits where the removed one was.
    removed = lines_of(original)[next(t for t in lines_of(original) if "Reduced p99" in t)]
    assert lines_of(edited)["• First new point"][2] == pytest.approx(removed[2], abs=0.1)


def test_body_text_in_the_headings_font_is_not_a_heading() -> None:
    # Every line of this resume is in one font, headings too.
    titles = [section.title for section in layout_of(pdf("plain")).sections]
    assert titles == ["Header", "WORK EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS"]


def test_a_new_line_can_copy_a_line_of_several_styles() -> None:
    original = pdf("jake")
    last_bullet = line_id(original, "Developed a Minecraft")
    title = line_id(original, "Simple Paintball")
    edited, outcomes = engine.apply_edits(
        original,
        [
            # A new project: its title looks like the other titles, its point like a bullet.
            AddLine(last_bullet, "Rolesetu | Next.js, FastAPI", style_id=title),
            AddLine(last_bullet, "Built a job matching app", style_id=last_bullet),
            AddLine(line_id(original, "Developer Tools"), "Cloud: AWS, GCP"),
        ],
    )
    assert all(outcome.applied for outcome in outcomes)
    with pymupdf.open(stream=edited) as doc:
        found = {line.text.replace("\xa0", " "): line for line in read_lines(doc[0])}
    fonts = [span.font for span in found["Rolesetu | Next.js, FastAPI"].spans]
    assert "Bold" in fonts[0] and "Italic" in fonts[-1]
    assert "Bold" in found["Cloud: AWS, GCP"].spans[0].font
    assert found["• Built a job matching app"].x0 == pytest.approx(
        found[
            "• Developed a Minecraft server plugin to entertain kids during free time for a "
            "previous job"
        ].x0,
        abs=0.5,
    )


def links_of(data: bytes) -> dict[str, str]:
    """Each link's address -> the words under it."""
    with pymupdf.open(stream=data) as doc:
        page = doc[0]
        return {
            str(link["uri"]): page.get_textbox(link["from"]).replace("\xad", "-").strip()
            for link in page.get_links()
        }


def test_links_are_read_with_the_words_they_cover() -> None:
    contact = next(item for s in layout_of(pdf("jake")).sections for item in s.lines if item.links)
    assert [(link.text, link.uri) for link in contact.links] == [
        ("linkedin.com/in/karanmehta", "https://linkedin.com/in/karanmehta"),
        ("github.com/karanm", "https://github.com/karanm"),
    ]


def test_a_link_follows_its_words_when_they_change() -> None:
    original = pdf("jake")
    contact = line_id(original, "+91")
    new = (
        "+91-9988776655 | karan.mehta@example.com | linkedin.com/in/karanmehta | "
        "github.com/karan-dev"
    )
    edited, outcomes = engine.apply_edits(original, [ChangeText(contact, new)])
    assert outcomes[0].applied
    # The address spelled out the old words, so it now spells the new ones; the
    # centred line moved, so the other link moved over its words with it.
    assert links_of(edited) == {
        "https://linkedin.com/in/karanmehta": "linkedin.com/in/karanmehta",
        "https://github.com/karan-dev": "github.com/karan-dev",
    }


def test_a_link_can_be_given_a_new_address() -> None:
    original = pdf("jake")
    linkedin = next(
        link.id for s in layout_of(original).sections for i in s.lines for link in i.links
    )
    edited, _ = engine.apply_edits(original, [], {linkedin: "https://linkedin.com/in/karan-m"})
    assert links_of(edited)["https://linkedin.com/in/karan-m"] == "linkedin.com/in/karanmehta"


def test_addresses_in_new_lines_become_links() -> None:
    original = pdf("jake")
    edited, outcomes = engine.apply_edits(
        original,
        [
            AddLine(
                line_id(original, "Developed a Minecraft"),
                "Rolesetu | github.com/karanm/rolesetu",
                style_id=line_id(original, "Simple Paintball"),
            )
        ],
    )
    assert outcomes[0].applied
    assert links_of(edited)["https://github.com/karanm/rolesetu"] == "github.com/karanm/rolesetu"


def test_removing_linked_words_removes_the_link() -> None:
    original = pdf("jake")
    contact = line_id(original, "+91")
    new = "+91-9988776655 | karan.mehta@example.com | linkedin.com/in/karanmehta"
    edited, _ = engine.apply_edits(original, [ChangeText(contact, new)])
    assert list(links_of(edited)) == ["https://linkedin.com/in/karanmehta"]
