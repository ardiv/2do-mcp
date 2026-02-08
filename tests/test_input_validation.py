"""Tests for Pydantic input model validation — no 2Do app required."""

import pytest
from pydantic import ValidationError

from twodo_mcp.server import (
    AddMultipleTasksInput,
    AddTaskInput,
    GetTaskIDInput,
    PasteTasksInput,
    Priority,
    SearchInput,
    ShowListInput,
    TaskType,
)


class TestAddTaskInput:
    """Validation tests for AddTaskInput."""

    def test_minimal_valid(self) -> None:
        params = AddTaskInput(task="Buy milk")
        assert params.task == "Buy milk"
        assert params.task_type == TaskType.TASK
        assert params.priority == Priority.NONE
        assert params.save_in_clipboard is True

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            AddTaskInput(task="")

    def test_whitespace_only_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddTaskInput(task="   ")

    def test_title_stripped(self) -> None:
        params = AddTaskInput(task="  Buy milk  ")
        assert params.task == "Buy milk"

    def test_long_title_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at most 500"):
            AddTaskInput(task="x" * 501)

    def test_max_length_title_accepted(self) -> None:
        params = AddTaskInput(task="x" * 500)
        assert len(params.task) == 500

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            AddTaskInput(task="Test", unknown_field="value")

    def test_valid_task_types(self) -> None:
        for tt in TaskType:
            params = AddTaskInput(task="Test", task_type=tt)
            assert params.task_type == tt

    def test_invalid_task_type(self) -> None:
        with pytest.raises(ValidationError):
            AddTaskInput(task="Test", task_type="5")

    def test_valid_priorities(self) -> None:
        for p in Priority:
            params = AddTaskInput(task="Test", priority=p)
            assert params.priority == p

    def test_invalid_priority(self) -> None:
        with pytest.raises(ValidationError):
            AddTaskInput(task="Test", priority="9")


class TestAddMultipleTasksInput:
    """Validation tests for AddMultipleTasksInput."""

    def test_valid_batch(self) -> None:
        params = AddMultipleTasksInput(tasks=["A", "B", "C"])
        assert len(params.tasks) == 3

    def test_empty_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddMultipleTasksInput(tasks=[])

    def test_too_many_tasks_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AddMultipleTasksInput(tasks=["t"] * 51)

    def test_max_tasks_accepted(self) -> None:
        params = AddMultipleTasksInput(tasks=["t"] * 50)
        assert len(params.tasks) == 50

    def test_shared_settings(self) -> None:
        params = AddMultipleTasksInput(
            tasks=["A", "B"],
            for_list="Work",
            priority=Priority.HIGH,
            tags="urgent",
            due="2026-03-01",
        )
        assert params.for_list == "Work"
        assert params.priority == Priority.HIGH


class TestPasteTasksInput:
    """Validation tests for PasteTasksInput."""

    def test_valid(self) -> None:
        params = PasteTasksInput(text="Line 1\nLine 2", in_project="Shopping", for_list="Home")
        assert params.text == "Line 1\nLine 2"

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PasteTasksInput(text="", in_project="P", for_list="L")

    def test_missing_project_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PasteTasksInput(text="Line 1", for_list="L")  # type: ignore[call-arg]

    def test_missing_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PasteTasksInput(text="Line 1", in_project="P")  # type: ignore[call-arg]


class TestGetTaskIDInput:
    """Validation tests for GetTaskIDInput."""

    def test_valid(self) -> None:
        params = GetTaskIDInput(task="My Task", for_list="Work")
        assert params.task == "My Task"

    def test_empty_task_rejected(self) -> None:
        with pytest.raises(ValidationError):
            GetTaskIDInput(task="", for_list="Work")


class TestShowListInput:
    """Validation tests for ShowListInput."""

    def test_valid(self) -> None:
        params = ShowListInput(name="Personal")
        assert params.name == "Personal"

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ShowListInput(name="")


class TestSearchInput:
    """Validation tests for SearchInput."""

    def test_valid(self) -> None:
        params = SearchInput(text="type:overdue")
        assert params.text == "type:overdue"

    def test_empty_text_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchInput(text="")
