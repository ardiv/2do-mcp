"""Tests for MCP tool functions with mocked macOS commands."""

from unittest.mock import AsyncMock, patch

import pytest

from twodo_mcp.server import (
    AddTaskInput,
    GetTaskIDInput,
    PasteTasksInput,
    SearchInput,
    ShowListInput,
    twodo_add_task,
    twodo_get_task_id,
    twodo_paste_tasks,
    twodo_search,
    twodo_show_all,
    twodo_show_list,
    twodo_show_scheduled,
    twodo_show_starred,
    twodo_show_today,
)


@pytest.fixture
def mock_open_url_success():
    """Mock _open_url to always succeed."""
    with patch("twodo_mcp.server._open_url", new_callable=AsyncMock, return_value=(True, "OK")) as m:
        yield m


@pytest.fixture
def mock_open_url_failure():
    """Mock _open_url to always fail."""
    with patch(
        "twodo_mcp.server._open_url",
        new_callable=AsyncMock,
        return_value=(False, "Timed out waiting for 2Do to respond. Is the app installed?"),
    ) as m:
        yield m


@pytest.fixture
def mock_clipboard_uid():
    """Mock _read_task_uid to return a fake UID."""
    uid = "A" * 32
    with patch("twodo_mcp.server._read_task_uid", new_callable=AsyncMock, return_value=uid) as m:
        yield m, uid


@pytest.fixture
def mock_clipboard_empty():
    """Mock _read_task_uid to return None."""
    with patch("twodo_mcp.server._read_task_uid", new_callable=AsyncMock, return_value=None) as m:
        yield m


class TestAddTask:
    @pytest.mark.asyncio
    async def test_success(self, mock_open_url_success, mock_clipboard_uid) -> None:
        _, uid = mock_clipboard_uid
        params = AddTaskInput(task="Test task", for_list="Work")
        result = await twodo_add_task(params)

        assert result["success"] is True
        assert result["task"] == "Test task"
        assert result["list"] == "Work"
        assert result["uid"] == uid

    @pytest.mark.asyncio
    async def test_success_default_list(self, mock_open_url_success, mock_clipboard_uid) -> None:
        params = AddTaskInput(task="Test task")
        result = await twodo_add_task(params)
        assert result["list"] == "(default)"

    @pytest.mark.asyncio
    async def test_failure(self, mock_open_url_failure) -> None:
        params = AddTaskInput(task="Test task")
        result = await twodo_add_task(params)

        assert result["success"] is False
        assert "error" in result
        assert "Timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_no_clipboard(self, mock_open_url_success) -> None:
        params = AddTaskInput(task="Test", save_in_clipboard=False)
        result = await twodo_add_task(params)

        assert result["success"] is True
        assert result["uid"] is None


class TestGetTaskID:
    @pytest.mark.asyncio
    async def test_success(self, mock_open_url_success, mock_clipboard_uid) -> None:
        _, uid = mock_clipboard_uid
        params = GetTaskIDInput(task="My Task", for_list="Work")
        result = await twodo_get_task_id(params)

        assert result["success"] is True
        assert result["uid"] == uid

    @pytest.mark.asyncio
    async def test_not_found(self, mock_open_url_success, mock_clipboard_empty) -> None:
        params = GetTaskIDInput(task="Missing Task", for_list="Work")
        result = await twodo_get_task_id(params)

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_open_failure(self, mock_open_url_failure) -> None:
        params = GetTaskIDInput(task="Task", for_list="Work")
        result = await twodo_get_task_id(params)

        assert result["success"] is False


class TestPasteTasks:
    @pytest.mark.asyncio
    async def test_success(self, mock_open_url_success) -> None:
        params = PasteTasksInput(text="Line 1\nLine 2\nLine 3", in_project="Shopping", for_list="Home")
        result = await twodo_paste_tasks(params)

        assert result["success"] is True
        assert result["tasks_added"] == 3
        assert result["project"] == "Shopping"

    @pytest.mark.asyncio
    async def test_counts_only_nonempty_lines(self, mock_open_url_success) -> None:
        params = PasteTasksInput(text="A\n\nB\n  \nC", in_project="P", for_list="L")
        result = await twodo_paste_tasks(params)
        assert result["tasks_added"] == 3

    @pytest.mark.asyncio
    async def test_failure(self, mock_open_url_failure) -> None:
        params = PasteTasksInput(text="Line 1", in_project="P", for_list="L")
        result = await twodo_paste_tasks(params)
        assert result["success"] is False


class TestNavigationTools:
    @pytest.mark.asyncio
    async def test_show_today(self, mock_open_url_success) -> None:
        result = await twodo_show_today()
        assert result["success"] is True
        assert result["view"] == "Today"

    @pytest.mark.asyncio
    async def test_show_starred(self, mock_open_url_success) -> None:
        result = await twodo_show_starred()
        assert result["success"] is True
        assert result["view"] == "Starred"

    @pytest.mark.asyncio
    async def test_show_scheduled(self, mock_open_url_success) -> None:
        result = await twodo_show_scheduled()
        assert result["success"] is True
        assert result["view"] == "Scheduled"

    @pytest.mark.asyncio
    async def test_show_all(self, mock_open_url_success) -> None:
        result = await twodo_show_all()
        assert result["success"] is True
        assert result["view"] == "All"

    @pytest.mark.asyncio
    async def test_show_list(self, mock_open_url_success) -> None:
        params = ShowListInput(name="Personal")
        result = await twodo_show_list(params)
        assert result["success"] is True
        assert result["list"] == "Personal"

    @pytest.mark.asyncio
    async def test_show_today_failure(self, mock_open_url_failure) -> None:
        result = await twodo_show_today()
        assert result["success"] is False
        assert "error" in result


class TestSearch:
    @pytest.mark.asyncio
    async def test_success(self, mock_open_url_success) -> None:
        params = SearchInput(text="type:overdue")
        result = await twodo_search(params)

        assert result["success"] is True
        assert result["query"] == "type:overdue"
        assert "displayed" in result["note"]

    @pytest.mark.asyncio
    async def test_failure(self, mock_open_url_failure) -> None:
        params = SearchInput(text="search term")
        result = await twodo_search(params)
        assert result["success"] is False
