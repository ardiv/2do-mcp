"""Tests for URL building logic — no 2Do app required."""

from twodo_mcp.server import (
    AddTaskInput,
    Priority,
    RepeatInterval,
    TaskType,
    _build_add_url,
)

TWODO_BASE = "twodo://x-callback-url/add?"


class TestBuildAddUrl:
    """Tests for _build_add_url()."""

    def test_minimal_task(self) -> None:
        params = AddTaskInput(task="Buy milk", save_in_clipboard=False)
        url = _build_add_url(params)
        assert url.startswith(TWODO_BASE)
        assert "task=Buy%20milk" in url
        assert "type=" not in url  # default TASK type omitted
        assert "priority=" not in url  # default NONE omitted

    def test_task_with_list(self) -> None:
        params = AddTaskInput(task="Call mom", for_list="Personal", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "forlist=Personal" in url

    def test_task_with_priority(self) -> None:
        params = AddTaskInput(task="Urgent", priority=Priority.HIGH, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "priority=3" in url

    def test_task_with_due_date(self) -> None:
        params = AddTaskInput(task="Meeting", due="2026-03-01", due_time="14:30", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "due=2026-03-01" in url
        assert "dueTime=14%3A30" in url

    def test_project_type(self) -> None:
        params = AddTaskInput(task="Q1 Goals", task_type=TaskType.PROJECT, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "type=1" in url

    def test_checklist_type(self) -> None:
        params = AddTaskInput(task="Shopping", task_type=TaskType.CHECKLIST, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "type=2" in url

    def test_starred(self) -> None:
        params = AddTaskInput(task="Important", starred=True, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "starred=1" in url

    def test_not_starred_omitted(self) -> None:
        params = AddTaskInput(task="Normal", starred=False, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "starred" not in url

    def test_tags(self) -> None:
        params = AddTaskInput(task="Tagged", tags="work,urgent", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "tags=work%2Curgent" in url

    def test_subtasks(self) -> None:
        params = AddTaskInput(task="Shopping", subtasks="Milk\nBread\nEggs", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "subtasks=Milk%0ABread%0AEggs" in url

    def test_note(self) -> None:
        params = AddTaskInput(task="Review", note="Check the docs", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "note=Check%20the%20docs" in url

    def test_repeat_weekly(self) -> None:
        params = AddTaskInput(task="Standup", repeat=RepeatInterval.WEEKLY, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "repeat=2" in url

    def test_action_url(self) -> None:
        params = AddTaskInput(task="Visit site", action="url:https://example.com", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "action=url%3Ahttps%3A//example.com" in url

    def test_parent_name(self) -> None:
        params = AddTaskInput(task="Subtask", for_parent_name="Project X", for_list="Work", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "forParentName=Project%20X" in url
        assert "forlist=Work" in url

    def test_parent_task_uid(self) -> None:
        uid = "A" * 32
        params = AddTaskInput(task="Subtask", for_parent_task=uid, save_in_clipboard=False)
        url = _build_add_url(params)
        assert f"forParentTask={uid}" in url

    def test_locations(self) -> None:
        params = AddTaskInput(task="Pick up", locations="Home,Office", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "locations=Home%2COffice" in url

    def test_ignore_defaults(self) -> None:
        params = AddTaskInput(task="No defaults", ignore_defaults=True, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "ignoreDefaults=1" in url

    def test_save_in_clipboard(self) -> None:
        params = AddTaskInput(task="With UID", save_in_clipboard=True)
        url = _build_add_url(params)
        assert "saveInClipboard=1" in url

    def test_edit_mode(self) -> None:
        params = AddTaskInput(task="Edit me", edit=True, save_in_clipboard=False)
        url = _build_add_url(params)
        assert "edit=1" in url

    def test_start_date(self) -> None:
        params = AddTaskInput(task="Future", start="2026-04-01 09:00", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "start=2026-04-01%2009%3A00" in url

    def test_full_task(self) -> None:
        """Test a task with all parameters set."""
        params = AddTaskInput(
            task="Full task",
            task_type=TaskType.CHECKLIST,
            for_list="Work",
            note="Important notes",
            subtasks="Step 1\nStep 2",
            priority=Priority.HIGH,
            starred=True,
            tags="urgent,review",
            due="2026-03-15",
            due_time="10:00",
            start="2026-03-14 09:00",
            repeat=RepeatInterval.DAILY,
            action="url:https://example.com",
            for_parent_name="Big Project",
            locations="Office",
            ignore_defaults=True,
            save_in_clipboard=True,
            edit=True,
        )
        url = _build_add_url(params)
        assert "task=Full%20task" in url
        assert "type=2" in url
        assert "forlist=Work" in url
        assert "note=Important%20notes" in url
        assert "priority=3" in url
        assert "starred=1" in url
        assert "tags=urgent%2Creview" in url
        assert "due=2026-03-15" in url
        assert "repeat=1" in url
        assert "locations=Office" in url
        assert "ignoreDefaults=1" in url
        assert "saveInClipboard=1" in url
        assert "edit=1" in url

    def test_special_characters_in_title(self) -> None:
        params = AddTaskInput(task="Task with & and = signs", save_in_clipboard=False)
        url = _build_add_url(params)
        assert "task=Task%20with%20%26%20and%20%3D%20signs" in url
