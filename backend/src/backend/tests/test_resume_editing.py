"""Adding skills to a resume PDF in place: the page must stay as it was
everywhere except where the new text goes.
"""

from pathlib import Path

import pymupdf
import pytest

from backend.modules.resumes.extraction.pdf_lines import extract_lines
from backend.modules.tailoring import placement
from backend.modules.tailoring.pdf import editor
from backend.modules.tailoring.pdf.section import find_skills_section
from backend.modules.tailoring.pdf.shift import Cut, shift_down

RESUMES = Path(__file__).parent / "fixtures" / "resumes"


def pdf(name: str) -> bytes:
    return (RESUMES / f"{name}.pdf").read_bytes()


def changed_band(before: bytes, after: bytes) -> tuple[float, float]:
    """The top and bottom (in points) of the part of page one that looks different."""
    with pymupdf.open(stream=before) as a, pymupdf.open(stream=after) as b:
        first, second = a[0].get_pixmap(dpi=72), b[0].get_pixmap(dpi=72)
    width = first.stride
    rows = [
        y
        for y in range(first.height)
        if first.samples[y * width : (y + 1) * width] != second.samples[y * width : (y + 1) * width]
    ]
    return (rows[0], rows[-1])


def text_of(data: bytes) -> str:
    return "\n".join(line.text for line in extract_lines(data))


def test_finds_labelled_rows() -> None:
    with pymupdf.open(stream=pdf("jake")) as doc:
        section = find_skills_section(doc)
    assert [entry.label for entry in section.entries] == [
        "Languages",
        "Frameworks",
        "Developer Tools",
    ]
    assert section.separator == ", "
    assert section.can_grow


def test_skill_goes_in_the_row_it_belongs_to() -> None:
    result = editor.add_skills(pdf("jake"), ["Kotlin", "GraphQL", "Terraform"])
    assert {item.skill: item.row for item in result.added} == {
        "Kotlin": "Languages",
        "GraphQL": "Frameworks",
        "Terraform": "Developer Tools",
    }
    assert result.skipped == []


def test_only_the_skills_rows_change_when_everything_fits() -> None:
    original = pdf("jake")
    result = editor.add_skills(original, ["Kotlin", "Terraform"])
    with pymupdf.open(stream=original) as doc:
        section = find_skills_section(doc)
    top, bottom = changed_band(original, result.pdf)
    assert top >= section.entries[0].lines[0].y0 - 2
    assert bottom <= section.entries[-1].last.y1 + 2


def test_a_text_reader_finds_the_new_skills_and_nothing_twice() -> None:
    original = pdf("plain")
    result = editor.add_skills(original, ["GraphQL", "Kotlin", "Kubernetes", "Terraform"])
    before, after = text_of(original), text_of(result.pdf)
    assert all(editor.contains_skill(after, item.skill) for item in result.added)
    # The new line pushed the rest down; it must not have left a second copy of the page.
    assert len(after.split()) == len(before.split()) + 4
    assert after.count("Travel Buddy") == 1


def test_a_full_line_wraps_and_moves_what_is_below() -> None:
    original = pdf("plain")
    result = editor.add_skills(original, ["GraphQL", "Kotlin", "Kubernetes", "Terraform"])

    def top_of(data: bytes, words: str) -> float:
        with pymupdf.open(stream=data) as doc:
            return float(doc[0].search_for(words)[0].y0)

    with pymupdf.open(stream=original) as doc:
        leading = find_skills_section(doc).leading
    moved = top_of(result.pdf, "Travel Buddy") - top_of(original, "Travel Buddy")
    assert moved == pytest.approx(leading, abs=0.1)
    # Above the Skills section nothing moves.
    assert top_of(result.pdf, "EDUCATION") == pytest.approx(top_of(original, "EDUCATION"), abs=0.01)


def test_links_survive_and_follow_the_text() -> None:
    original = pdf("jake")
    long_list = ["Kotlin", "Rust", "Scala", "Ruby", "PHP", "Bash", "MATLAB", "Dart", "Elixir"]
    result = editor.add_skills(original, long_list)
    with pymupdf.open(stream=original) as a, pymupdf.open(stream=result.pdf) as b:
        assert len(b[0].get_links()) == len(a[0].get_links())


def test_a_skill_already_listed_is_not_added_again() -> None:
    result = editor.add_skills(pdf("jake"), ["Docker", "golang", "Kotlin"])
    assert [(item.skill, item.reason) for item in result.skipped] == [
        ("Docker", "already_listed"),
        ("golang", "already_listed"),
    ]
    assert [item.skill for item in result.added] == ["Kotlin"]


def test_the_user_can_choose_the_row() -> None:
    result = editor.add_skills(pdf("jake"), ["Kotlin"], {"Kotlin": "Developer Tools"})
    assert result.added[0].row == "Developer Tools"


def test_a_column_beside_the_skills_is_never_pushed_down() -> None:
    with pytest.raises(editor.ResumeEditError) as error:
        editor.add_skills(pdf("twocol"), ["Celery"])
    assert error.value.reason == "unsupported_layout"


def test_a_file_that_is_not_a_pdf_is_refused() -> None:
    with pytest.raises(editor.ResumeEditError) as error:
        editor.add_skills(b"not a pdf", ["Kotlin"])
    assert error.value.reason == "unreadable"


def test_ranking_prefers_the_matching_row() -> None:
    rows = [("Languages", "Python, Go"), ("Databases", "PostgreSQL, Redis"), ("Tools", "Git")]
    assert placement.rank_rows("MongoDB", rows)[0][0] == 1
    assert placement.rank_rows("Kotlin", rows)[0][0] == 0


def test_shift_moves_only_what_is_below_the_cut() -> None:
    content = (
        b"BT /F1 10 Tf 12 TL 1 0 0 1 40 700 Tm (above) Tj T* (also above) Tj ET "
        b"BT /F1 10 Tf 1 0 0 1 40 500 Tm (below) Tj 0 -12 Td (lower) Tj ET "
        b"40 690 100 1 re f 40 490 100 1 re f"
    )
    moved = shift_down(content, [Cut(y=600, distance=15)]).decode()
    assert "1 0 0 1 40 700 Tm" in moved
    assert "1 0 0 1 40 485 Tm" in moved
    # A relative move between two lines that both moved stays as it was.
    assert "0 -12 Td" in moved
    assert "40 690 100 1 re" in moved
    assert "40 475 100 1 re" in moved


def test_shift_inside_one_text_block_and_a_flipped_page() -> None:
    # Lines written one after another in a single block, crossing the cut.
    block = b"BT 12 TL 1 0 0 1 40 610 Tm (one) Tj T* (two) Tj T* (three) Tj ET"
    moved = shift_down(block, [Cut(y=600, distance=15)]).decode()
    assert moved.count("T*") == 1  # the first line break became an explicit, longer move
    assert "0 -27 Td" in moved

    # Chrome draws with the page flipped (y grows downwards inside the flip).
    flipped = b"q 1 0 0 -1 0 800 cm BT 1 0 0 -1 40 300 Tm (x) Tj ET Q"
    assert "40 315 Tm" in shift_down(flipped, [Cut(y=600, distance=15)]).decode()


# --- rewording existing text


def lines_of(data: bytes) -> list[str]:
    return [line.text for line in extract_lines(data)]


def test_headline_is_reworded_and_nothing_else_moves() -> None:
    original = pdf("classic")
    result = editor.tailor(original, skills=[], headline="Frontend Developer")
    assert [(c.kind, c.before, c.after, c.applied) for c in result.changes] == [
        ("headline", "Frontend Engineer", "Frontend Developer", True)
    ]
    before, after = lines_of(original), lines_of(result.pdf)
    assert "Frontend Developer" in after and "Frontend Engineer" not in after
    # Every other line reads exactly as it did.
    assert [line for line in after if line != "Frontend Developer"] == [
        line for line in before if line != "Frontend Engineer"
    ]
    top, bottom = changed_band(original, result.pdf)
    assert bottom - top < 14  # one line of the page, no more


def test_a_skill_is_respelled_the_way_the_job_writes_it() -> None:
    original = pdf("jake")
    result = editor.tailor(original, skills=[], respell=[("Node.js", "NodeJS")])
    assert result.changes[0].applied
    text = text_of(result.pdf)
    assert "NodeJS" in text and "Node.js, Flask" not in text
    with pymupdf.open(stream=original) as a, pymupdf.open(stream=result.pdf) as b:
        assert len(b[0].get_links()) == len(a[0].get_links())


def test_rewording_and_adding_work_together() -> None:
    result = editor.tailor(
        pdf("classic"), skills=["GraphQL"], headline="Frontend Developer", respell=[]
    )
    assert result.changes[0].applied
    assert [item.skill for item in result.added] == ["GraphQL"]
    text = text_of(result.pdf)
    assert "Frontend Developer" in text and editor.contains_skill(text, "GraphQL")


def test_changes_that_cannot_be_made_say_why() -> None:
    # jake.pdf has no role line under the name.
    no_headline = editor.tailor(pdf("jake"), skills=[], headline="Backend Engineer")
    assert (no_headline.changes[0].applied, no_headline.changes[0].reason) == (False, "not_found")
    assert no_headline.pdf == pdf("jake")

    too_long = editor.tailor(pdf("classic"), skills=[], headline="Frontend Developer " * 8)
    assert (too_long.changes[0].applied, too_long.changes[0].reason) == (False, "no_room")

    absent = editor.tailor(pdf("jake"), skills=[], respell=[("Laravel", "Laravel 10")])
    assert absent.changes[0].applied is False


def test_headline_suggestions_stay_honest() -> None:
    from backend.modules.tailoring.keywords import clean_title, suggest_headline

    assert suggest_headline("REACT NATIVE DEVELOPER", "React Native Engineer (Remote)") == (
        "REACT NATIVE ENGINEER"
    )
    # Rank the resume does not claim is never added.
    assert suggest_headline("Frontend Engineer", "Sr. Frontend Developer | Bengaluru") == (
        "Frontend Developer"
    )
    assert suggest_headline("Senior Systems Engineer", "Senior Backend Engineer") == (
        "Senior Backend Engineer"
    )
    # A different kind of work is not offered at all.
    assert suggest_headline("Backend Developer", "Product Designer") is None
    assert suggest_headline("Frontend Engineer", "frontend engineer") is None
    assert clean_title("Software Engineer II - Payments (Remote)") == "Software Engineer II"


def test_titles_are_cleaned_of_job_site_wording() -> None:
    from backend.modules.tailoring.keywords import clean_title, is_a_title, suggest_headline

    listing = "react native developer jobs in Pune, Maharashtra"
    assert clean_title(listing) == "react native developer"
    assert suggest_headline("FULL STACK DEVELOPER", listing) == "REACT NATIVE DEVELOPER"
    assert clean_title("Walk-in || Acquisition Manager - CC/PL/BL") == "Acquisition Manager"
    assert clean_title("Hiring for Backend Engineer") == "Backend Engineer"
    # A page heading mistaken for the title is not offered as a headline at all.
    assert not is_a_title("Full job description")
    assert is_a_title("Senior Software Engineer (Mobile)")


def test_keyword_check_tells_spelling_from_absence() -> None:
    from backend.modules.tailoring.keywords import check_skill

    text = "Languages: JavaScript, TypeScript. Frameworks: React Native, Next.js. Data: Postgres"
    assert check_skill("TypeScript", text).status == "present"
    found = check_skill("PostgreSQL", text)
    assert (found.status, found.written_as) == ("different_spelling", "Postgres")
    assert check_skill("Kotlin", text).status == "missing"


def test_an_edited_resume_can_be_edited_again() -> None:
    first = editor.add_skills(pdf("jake"), ["Kotlin"])
    # The skill added last time is seen as part of the row...
    again = editor.add_skills(first.pdf, ["Kotlin", "Rust"])
    assert [(item.skill, item.reason) for item in again.skipped] == [("Kotlin", "already_listed")]
    assert [item.skill for item in again.added] == ["Rust"]
    # ...and the next one goes after it, not on top of it.
    row = next(line for line in lines_of(again.pdf) if line.startswith("Languages"))
    assert row.endswith("Kotlin, Rust")


def test_a_server_with_no_fonts_installed_can_still_add_any_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fonts shipped with the backend cover what the resume's own font lacks.
    Without them, a skill needing a new letter was refused on a bare server.
    """
    from backend.modules.tailoring.pdf import fonts

    monkeypatch.setattr(fonts, "_SYSTEM_FONT_DIRS", ())
    fonts._font_files.cache_clear()
    try:
        assert fonts._BUNDLED_FONT_DIR.is_dir()
        # classic.pdf is set in Helvetica and carries only the letters it uses.
        result = editor.add_skills(pdf("classic"), ["Kubernetes", "Zig", "Qwik"])
        assert [(item.skill, item.reason) for item in result.skipped] == []
        assert {item.skill for item in result.added} == {"Kubernetes", "Zig", "Qwik"}
        text = text_of(result.pdf)
        assert all(editor.contains_skill(text, name) for name in ("Kubernetes", "Zig", "Qwik"))
        # The same for a serif resume.
        serif = editor.add_skills(pdf("jake"), ["Zig", "Qwik & XState"])
        assert serif.skipped == []
    finally:
        fonts._font_files.cache_clear()
