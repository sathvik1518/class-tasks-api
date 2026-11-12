import pytest

from app.domain.errors import DuplicateTitle, InvalidTitle, TaskError, TaskNotFound
from app.domain.task import Task
from app.domain.titles import check_title, normalize_title, title_key
from datetime import datetime, timezone

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_normalize_trims_and_collapses_spaces():
    assert normalize_title("  Math   homework \t") == "Math homework"


def test_normalize_turns_newlines_into_one_space():
    assert normalize_title("Read\n\nchapter\r\n4") == "Read chapter 4"


def test_normalize_joins_split_accents():
    assert normalize_title("Café") == normalize_title("Café") == "Café"


def test_title_key_uses_full_case_folding():
    assert title_key("Straße") == title_key("STRASSE")  # lower() would keep these apart; casefold() does not


def test_title_key_ignores_case():
    assert title_key("Homework") == title_key("HOMEWORK") == title_key("homework")


@pytest.mark.parametrize("raw", ["", "   ", "\n\t", "​", " ​​ ", " "])
def test_blank_or_invisible_titles_are_refused(raw):
    with pytest.raises(InvalidTitle, match="empty"):
        check_title(raw, 100)


@pytest.mark.parametrize("raw", ["bad\x00name", "esc\x1b[31m", "bell\x07"])
def test_control_characters_are_refused(raw):
    with pytest.raises(InvalidTitle, match="control"):
        check_title(raw, 100)


@pytest.mark.parametrize("raw", [None, 5, 1.5, ["a"], {"a": 1}, b"abc"])
def test_non_text_is_refused(raw):
    with pytest.raises(InvalidTitle, match="text"):
        check_title(raw, 100)


def test_length_limit_is_inclusive():
    assert check_title("a" * 100, 100) == "a" * 100
    with pytest.raises(InvalidTitle, match="at most 100"):
        check_title("a" * 101, 100)


def test_length_is_counted_after_cleaning():
    assert check_title("  " + "a" * 100 + "  ", 100) == "a" * 100
    assert check_title("a  b", 3) == "a b"  # two spaces count as one


def test_length_limit_comes_from_the_argument():
    with pytest.raises(InvalidTitle):
        check_title("abcdef", 5)
    assert check_title("abcdef", 6) == "abcdef"


def test_telugu_and_emoji_titles_are_fine():
    assert check_title("గృహపాఠం 📚", 100) == "గృహపాఠం 📚"


def test_zero_width_joiner_inside_a_word_is_kept():
    assert check_title("క‍ష", 100) == "క‍ష"  # invisible marks are allowed next to visible letters


def test_complete_sets_the_time_and_does_not_touch_the_old_object():
    task = Task(1, "a", False, NOW)
    later = datetime(2026, 1, 2, tzinfo=timezone.utc)
    done = task.completed(later)
    assert done.done and done.completed_at == later
    assert not task.done and task.completed_at is None


def test_completing_a_done_task_returns_the_same_object():
    done = Task(1, "a", True, NOW, NOW)
    assert done.completed(datetime(2030, 1, 1, tzinfo=timezone.utc)) is done


def test_reopen_clears_the_time_and_is_a_noop_when_open():
    done = Task(1, "a", True, NOW, NOW)
    open_ = done.reopened()
    assert not open_.done and open_.completed_at is None
    assert open_.reopened() is open_


def test_task_is_frozen():
    with pytest.raises(Exception):
        Task(1, "a", False, NOW).title = "b"  # type: ignore[misc]


def test_every_error_is_a_task_error_with_a_code():
    codes = set()
    for cls in (InvalidTitle, DuplicateTitle, TaskNotFound):
        assert issubclass(cls, TaskError)
        codes.add(cls.code)
    assert len(codes) == 3 and "task_error" not in codes
    assert InvalidTitle("x").message == "x"
