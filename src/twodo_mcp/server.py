#!/usr/bin/env python3
"""
MCP Server for 2Do Task Management App.

Provides tools to interact with the 2Do macOS app through URL schemes
(x-callback-url) for creating tasks and navigating the app.

Note: 2Do does not expose a read API. All operations are write-only via URL schemes.
Requires macOS with 2Do app installed.
"""

import asyncio
import json
from enum import Enum
from urllib.parse import quote

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# Initialize the MCP server
mcp = FastMCP("twodo_mcp")

# Constants
TWODO_BASE_URL = "twodo://x-callback-url"
CLIPBOARD_WAIT_SECONDS = 0.5
BATCH_DELAY_SECONDS = 0.3
URL_TIMEOUT_SECONDS = 10
CLIPBOARD_TIMEOUT_SECONDS = 5
TASK_UID_LENGTH = 32


# ============================================================================
# ENUMS
# ============================================================================

class TaskType(str, Enum):
    """Type of task in 2Do."""
    TASK = "0"
    PROJECT = "1"
    CHECKLIST = "2"


class Priority(str, Enum):
    """Priority level for tasks."""
    NONE = "0"
    LOW = "1"
    MEDIUM = "2"
    HIGH = "3"


class RepeatInterval(str, Enum):
    """Repeat interval for recurring tasks."""
    DAILY = "1"
    WEEKLY = "2"
    BI_WEEKLY = "3"
    MONTHLY = "4"


# ============================================================================
# ASYNC HELPERS
# ============================================================================

async def _run_command(*args: str, timeout: float = URL_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    """Run a subprocess asynchronously and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()


async def _open_url(url: str) -> tuple[bool, str]:
    """Open a URL scheme on macOS via the 'open' command.

    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        returncode, _, stderr = await _run_command("open", url)
        if returncode == 0:
            return True, "OK"
        return False, f"'open' command failed: {stderr}"
    except asyncio.TimeoutError:
        return False, "Timed out waiting for 2Do to respond. Is the app installed?"
    except FileNotFoundError:
        return False, "macOS 'open' command not found. This server only runs on macOS."
    except OSError as e:
        return False, f"OS error: {e}"


async def _get_clipboard() -> str:
    """Read clipboard content on macOS via 'pbpaste'."""
    try:
        _, stdout, _ = await _run_command("pbpaste", timeout=CLIPBOARD_TIMEOUT_SECONDS)
        return stdout
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return ""


async def _read_task_uid() -> str | None:
    """Wait for 2Do to write a task UID to the clipboard, then read it.

    Returns:
        The 32-character UID string, or None if not found.
    """
    await asyncio.sleep(CLIPBOARD_WAIT_SECONDS)
    clip = await _get_clipboard()
    if clip and len(clip) == TASK_UID_LENGTH:
        return clip
    return None


def _error_response(message: str) -> str:
    """Format a consistent error JSON response."""
    return json.dumps({"success": False, "error": message}, indent=2)


def _success_response(**fields: object) -> str:
    """Format a consistent success JSON response."""
    return json.dumps({"success": True, **fields}, indent=2)


# ============================================================================
# INPUT MODELS
# ============================================================================

class AddTaskInput(BaseModel):
    """Input for adding a single task to 2Do."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    task: str = Field(
        ...,
        description="Title of the task",
        min_length=1,
        max_length=500,
    )
    task_type: TaskType = Field(
        default=TaskType.TASK,
        description="Type: '0'=Task (default), '1'=Project, '2'=Checklist",
    )
    for_list: str | None = Field(
        default=None,
        description="Name of the 2Do list to add to (case-insensitive). Omit for default list.",
    )
    note: str | None = Field(
        default=None,
        description="Notes/description for the task",
    )
    subtasks: str | None = Field(
        default=None,
        description="Newline-separated subtask titles. Converts parent to Checklist automatically.",
    )
    priority: Priority = Field(
        default=Priority.NONE,
        description="Priority: '0'=None (default), '1'=Low, '2'=Medium, '3'=High",
    )
    starred: bool = Field(
        default=False,
        description="Star/flag the task",
    )
    tags: str | None = Field(
        default=None,
        description="Comma-separated tag names (e.g. 'work,urgent')",
    )
    due: str | None = Field(
        default=None,
        description="Due date as 'YYYY-MM-DD' or integer days from today (0=today, 1=tomorrow)",
    )
    due_time: str | None = Field(
        default=None,
        description="Due time in 24-hour format 'HH:MM' (e.g. '14:30'). Requires 'due' to be set.",
    )
    start: str | None = Field(
        default=None,
        description="Start date/time as 'YYYY-MM-DD HH:MM' or integer days from today",
    )
    repeat: RepeatInterval | None = Field(
        default=None,
        description="Repeat: '1'=Daily, '2'=Weekly, '3'=Bi-weekly, '4'=Monthly",
    )
    action: str | None = Field(
        default=None,
        description="Action URL (e.g. 'url:https://...', 'call:+1234', 'mail:user@email.com')",
    )
    for_parent_name: str | None = Field(
        default=None,
        description="Name of the parent project to nest under. Requires 'for_list'.",
    )
    for_parent_task: str | None = Field(
        default=None,
        description="Parent task UID (32-char string) to nest under",
    )
    ignore_defaults: bool = Field(
        default=False,
        description="Ignore 2Do's default due date/time settings for new tasks",
    )
    save_in_clipboard: bool = Field(
        default=True,
        description="Save the new task's UID to clipboard after creation",
    )


class AddMultipleTasksInput(BaseModel):
    """Input for adding multiple tasks with shared settings."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    tasks: list[str] = Field(
        ...,
        description="List of task titles to create",
        min_length=1,
        max_length=50,
    )
    for_list: str | None = Field(
        default=None,
        description="List to add all tasks to",
    )
    priority: Priority = Field(
        default=Priority.NONE,
        description="Priority for all tasks: '0'=None, '1'=Low, '2'=Medium, '3'=High",
    )
    tags: str | None = Field(
        default=None,
        description="Comma-separated tags for all tasks",
    )
    due: str | None = Field(
        default=None,
        description="Due date for all tasks ('YYYY-MM-DD' or days from today)",
    )


class PasteTasksInput(BaseModel):
    """Input for pasting multiline text as subtasks into a project."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(
        ...,
        description="Multiline text where each line becomes a subtask",
        min_length=1,
    )
    in_project: str = Field(
        ...,
        description="Title of the project to paste subtasks into",
    )
    for_list: str = Field(
        ...,
        description="Name of the list containing the project",
    )


class GetTaskIDInput(BaseModel):
    """Input for retrieving a task's UID."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    task: str = Field(
        ...,
        description="Exact task title (must match exactly)",
        min_length=1,
    )
    for_list: str = Field(
        ...,
        description="Name of the list containing the task",
    )


class ShowListInput(BaseModel):
    """Input for navigating to a specific list."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(
        ...,
        description="Name of the list to show",
        min_length=1,
    )


class SearchInput(BaseModel):
    """Input for searching in 2Do."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(
        ...,
        description=(
            "Search query. Supports special syntax: "
            "'type:overdue' for overdue tasks, "
            "'tags:work' for tagged tasks, "
            "'(clipboard)' to search clipboard contents"
        ),
        min_length=1,
    )


# ============================================================================
# URL BUILDER
# ============================================================================

def _build_add_url(params: AddTaskInput) -> str:
    """Build the 2Do URL scheme for adding a task."""
    parts: list[str] = [f"task={quote(params.task)}"]

    field_map: list[tuple[str, object, str]] = [
        ("type", params.task_type if params.task_type != TaskType.TASK else None, "value"),
        ("forlist", params.for_list, "quote"),
        ("note", params.note, "quote"),
        ("subtasks", params.subtasks, "quote"),
        ("priority", params.priority if params.priority != Priority.NONE else None, "value"),
        ("starred", "1" if params.starred else None, "raw"),
        ("tags", params.tags, "quote"),
        ("due", params.due, "quote"),
        ("dueTime", params.due_time, "quote"),
        ("start", params.start, "quote"),
        ("repeat", params.repeat, "value"),
        ("action", params.action, "quote"),
        ("forParentName", params.for_parent_name, "quote"),
        ("forParentTask", params.for_parent_task, "quote"),
        ("ignoreDefaults", "1" if params.ignore_defaults else None, "raw"),
        ("saveInClipboard", "1" if params.save_in_clipboard else None, "raw"),
    ]

    for key, val, mode in field_map:
        if val is None:
            continue
        if mode == "value":
            parts.append(f"{key}={val.value}")
        elif mode == "quote":
            parts.append(f"{key}={quote(str(val))}")
        else:
            parts.append(f"{key}={val}")

    return f"{TWODO_BASE_URL}/add?{'&'.join(parts)}"


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool(
    name="twodo_add_task",
    annotations={
        "title": "Add Task to 2Do",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def twodo_add_task(params: AddTaskInput) -> str:
    """Create a new task in the 2Do app.

    Creates a task, project, or checklist via macOS URL scheme. The new task's
    UID is saved to the clipboard by default for later reference.

    Args:
        params (AddTaskInput): Validated input containing:
            - task (str): Task title (required)
            - task_type (TaskType): '0'=Task, '1'=Project, '2'=Checklist
            - for_list (str|None): Target list name
            - note (str|None): Notes/description
            - subtasks (str|None): Newline-separated subtask titles
            - priority (Priority): '0'=None, '1'=Low, '2'=Medium, '3'=High
            - starred (bool): Star/flag the task
            - tags (str|None): Comma-separated tags
            - due (str|None): Due date ('YYYY-MM-DD' or days from today)
            - due_time (str|None): Due time ('HH:MM' 24h format)
            - start (str|None): Start date/time
            - repeat (RepeatInterval|None): Recurrence interval
            - action (str|None): Action URL
            - for_parent_name (str|None): Parent project name
            - for_parent_task (str|None): Parent task UID
            - ignore_defaults (bool): Skip 2Do default date settings
            - save_in_clipboard (bool): Save UID to clipboard

    Returns:
        str: JSON with {success, task, list, uid} on success,
             or {success: false, error} on failure.
    """
    url = _build_add_url(params)
    success, message = await _open_url(url)

    if not success:
        return _error_response(message)

    uid = await _read_task_uid() if params.save_in_clipboard else None
    return _success_response(
        task=params.task,
        list=params.for_list or "(default)",
        uid=uid,
    )


@mcp.tool(
    name="twodo_add_multiple_tasks",
    annotations={
        "title": "Add Multiple Tasks to 2Do",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def twodo_add_multiple_tasks(params: AddMultipleTasksInput) -> str:
    """Create multiple tasks in 2Do with shared settings.

    Each task is created sequentially with a short delay between them
    to avoid overwhelming the app.

    Args:
        params (AddMultipleTasksInput): Validated input containing:
            - tasks (list[str]): Task titles (1-50 items)
            - for_list (str|None): Target list for all tasks
            - priority (Priority): Shared priority level
            - tags (str|None): Shared comma-separated tags
            - due (str|None): Shared due date

    Returns:
        str: JSON with {success, total, successful, failed, results[]}.
             Each result has {task, success, error}.
    """
    results = []

    for task_title in params.tasks:
        task_input = AddTaskInput(
            task=task_title,
            for_list=params.for_list,
            priority=params.priority,
            tags=params.tags,
            due=params.due,
            save_in_clipboard=False,
        )
        url = _build_add_url(task_input)
        ok, msg = await _open_url(url)
        results.append({"task": task_title, "success": ok, "error": None if ok else msg})
        await asyncio.sleep(BATCH_DELAY_SECONDS)

    successful = sum(1 for r in results if r["success"])
    return json.dumps(
        {
            "success": successful == len(params.tasks),
            "total": len(params.tasks),
            "successful": successful,
            "failed": len(params.tasks) - successful,
            "results": results,
        },
        indent=2,
    )


@mcp.tool(
    name="twodo_paste_tasks",
    annotations={
        "title": "Paste Text as Subtasks",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def twodo_paste_tasks(params: PasteTasksInput) -> str:
    """Paste multiline text as subtasks into an existing project.

    Each non-empty line in the text becomes a separate subtask
    under the specified project.

    Args:
        params (PasteTasksInput): Validated input containing:
            - text (str): Multiline text (one subtask per line)
            - in_project (str): Target project title
            - for_list (str): List containing the project

    Returns:
        str: JSON with {success, project, list, tasks_added}
             or {success: false, error}.
    """
    url = (
        f"{TWODO_BASE_URL}/paste?"
        f"text={quote(params.text)}"
        f"&inProject={quote(params.in_project)}"
        f"&forList={quote(params.for_list)}"
    )
    ok, msg = await _open_url(url)

    if not ok:
        return _error_response(msg)

    task_count = len([line for line in params.text.split("\n") if line.strip()])
    return _success_response(
        project=params.in_project,
        list=params.for_list,
        tasks_added=task_count,
    )


@mcp.tool(
    name="twodo_get_task_id",
    annotations={
        "title": "Get Task UID",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_get_task_id(params: GetTaskIDInput) -> str:
    """Get the unique identifier (UID) of an existing task.

    Looks up the task by exact title and list name. The 32-character UID
    is saved to the clipboard. Use this UID with for_parent_task when
    adding subtasks.

    Args:
        params (GetTaskIDInput): Validated input containing:
            - task (str): Exact task title (must match exactly)
            - for_list (str): List containing the task

    Returns:
        str: JSON with {success, task, list, uid} where uid is 32 chars,
             or {success: false, error}.
    """
    url = (
        f"{TWODO_BASE_URL}/getTaskID?"
        f"task={quote(params.task)}"
        f"&forList={quote(params.for_list)}"
        f"&saveInClipboard=1"
    )
    ok, msg = await _open_url(url)

    if not ok:
        return _error_response(msg)

    uid = await _read_task_uid()
    if not uid:
        return _error_response(
            f"Task '{params.task}' not found in list '{params.for_list}'. "
            "Check that the title matches exactly (case-sensitive)."
        )
    return _success_response(task=params.task, list=params.for_list, uid=uid)


@mcp.tool(
    name="twodo_show_list",
    annotations={
        "title": "Show List",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_show_list(params: ShowListInput) -> str:
    """Navigate to a specific list in the 2Do app.

    Opens the 2Do app and switches to the named list.

    Args:
        params (ShowListInput): Validated input containing:
            - name (str): List name to navigate to

    Returns:
        str: JSON with {success, list} or {success: false, error}.
    """
    url = f"{TWODO_BASE_URL}/showList?name={quote(params.name)}"
    ok, msg = await _open_url(url)
    if not ok:
        return _error_response(msg)
    return _success_response(list=params.name)


@mcp.tool(
    name="twodo_show_today",
    annotations={
        "title": "Show Today View",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_show_today() -> str:
    """Navigate to the Today view in the 2Do app.

    Returns:
        str: JSON with {success, view: "Today"} or {success: false, error}.
    """
    ok, msg = await _open_url(f"{TWODO_BASE_URL}/showToday")
    if not ok:
        return _error_response(msg)
    return _success_response(view="Today")


@mcp.tool(
    name="twodo_show_starred",
    annotations={
        "title": "Show Starred View",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_show_starred() -> str:
    """Navigate to the Starred view in the 2Do app.

    Returns:
        str: JSON with {success, view: "Starred"} or {success: false, error}.
    """
    ok, msg = await _open_url(f"{TWODO_BASE_URL}/showStarred")
    if not ok:
        return _error_response(msg)
    return _success_response(view="Starred")


@mcp.tool(
    name="twodo_show_scheduled",
    annotations={
        "title": "Show Scheduled View",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_show_scheduled() -> str:
    """Navigate to the Scheduled view in the 2Do app.

    Returns:
        str: JSON with {success, view: "Scheduled"} or {success: false, error}.
    """
    ok, msg = await _open_url(f"{TWODO_BASE_URL}/showScheduled")
    if not ok:
        return _error_response(msg)
    return _success_response(view="Scheduled")


@mcp.tool(
    name="twodo_show_all",
    annotations={
        "title": "Show All Tasks View",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_show_all() -> str:
    """Navigate to the All Tasks view in the 2Do app.

    Returns:
        str: JSON with {success, view: "All"} or {success: false, error}.
    """
    ok, msg = await _open_url(f"{TWODO_BASE_URL}/showAll")
    if not ok:
        return _error_response(msg)
    return _success_response(view="All")


@mcp.tool(
    name="twodo_search",
    annotations={
        "title": "Search in 2Do",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def twodo_search(params: SearchInput) -> str:
    """Open 2Do with a search query.

    Results are displayed in the 2Do app window. Supports special search
    syntax for filtering.

    Args:
        params (SearchInput): Validated input containing:
            - text (str): Search query. Supports: plain text, 'type:overdue',
              'tags:tagname', '(clipboard)' to search clipboard contents.

    Returns:
        str: JSON with {success, query, note} or {success: false, error}.
             Note: results are shown in the 2Do app, not returned here.
    """
    url = f"{TWODO_BASE_URL}/search?text={quote(params.text)}"
    ok, msg = await _open_url(url)

    if not ok:
        return _error_response(msg)
    return _success_response(
        query=params.text,
        note="Results displayed in 2Do app",
    )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
