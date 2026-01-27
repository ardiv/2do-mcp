#!/usr/bin/env python3
"""
MCP Server for 2Do Task Management App.

This server provides tools to interact with the 2Do app through URL schemes
(x-callback-url) for creating tasks and navigating the app.

Note: 2Do does not expose a readable database or read API.
All operations are write-only via URL schemes.

Supported operations:
- Add tasks, projects, and checklists
- Add multiple tasks at once
- Paste text as tasks into a project
- Get task UID by title
- Navigate to views (Today, Starred, etc.)
- Search in app
"""

import json
import subprocess
import time
from enum import Enum
from typing import Optional
from urllib.parse import quote

from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("twodo")


# ============================================================================
# ENUMS
# ============================================================================

class TaskType(str, Enum):
    """Type of task in 2Do."""
    TASK = "0"       # Regular task
    PROJECT = "1"    # Project (can contain subtasks)
    CHECKLIST = "2"  # Checklist (items can be checked off)


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
# URL SCHEME HELPERS
# ============================================================================

def _open_url(url: str) -> tuple[bool, str]:
    """Open a URL scheme on macOS. Returns (success, message)."""
    try:
        result = subprocess.run(
            ["open", url],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "OK"
        else:
            return False, f"Failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except FileNotFoundError:
        return False, "macOS 'open' command not available"
    except Exception as e:
        return False, str(e)


def _get_clipboard() -> str:
    """Get clipboard content on macOS."""
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ============================================================================
# INPUT MODELS
# ============================================================================

class AddTaskInput(BaseModel):
    """Input model for adding a new task to 2Do."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    task: str = Field(
        ...,
        description="Title of the task (required)",
        min_length=1,
        max_length=500
    )
    task_type: TaskType = Field(
        default=TaskType.TASK,
        description="Type: '0'=Task (default), '1'=Project, '2'=Checklist"
    )
    for_list: Optional[str] = Field(
        default=None,
        description="Name of the list to add to (case-insensitive)"
    )
    note: Optional[str] = Field(
        default=None,
        description="Notes for the task"
    )
    subtasks: Optional[str] = Field(
        default=None,
        description="Newline-separated subtasks (converts parent to Checklist)"
    )
    priority: Priority = Field(
        default=Priority.NONE,
        description="Priority: '0'=None, '1'=Low, '2'=Medium, '3'=High"
    )
    starred: bool = Field(
        default=False,
        description="Star/flag the task"
    )
    tags: Optional[str] = Field(
        default=None,
        description="Comma-separated tags"
    )
    due: Optional[str] = Field(
        default=None,
        description="Due date: 'YYYY-MM-DD' or days from today (0=today)"
    )
    due_time: Optional[str] = Field(
        default=None,
        description="Due time: 'HH:MM' 24-hour format"
    )
    start: Optional[str] = Field(
        default=None,
        description="Start date/time: 'YYYY-MM-DD HH:MM' or days from today"
    )
    repeat: Optional[RepeatInterval] = Field(
        default=None,
        description="Repeat: '1'=Daily, '2'=Weekly, '3'=Bi-weekly, '4'=Monthly"
    )
    action: Optional[str] = Field(
        default=None,
        description="Action URL (call:, message:, mail:, url:, visit:, google:)"
    )
    for_parent_name: Optional[str] = Field(
        default=None,
        description="Parent project name (requires for_list)"
    )
    for_parent_task: Optional[str] = Field(
        default=None,
        description="Parent task UID"
    )
    locations: Optional[str] = Field(
        default=None,
        description="Comma-separated location names"
    )
    ignore_defaults: bool = Field(
        default=False,
        description="Ignore default due date/time settings"
    )
    save_in_clipboard: bool = Field(
        default=True,
        description="Save new task's UID to clipboard"
    )
    edit: bool = Field(
        default=False,
        description="Show edit screen after creating"
    )


class AddMultipleTasksInput(BaseModel):
    """Input for adding multiple tasks."""
    model_config = ConfigDict(str_strip_whitespace=True)

    tasks: list[str] = Field(
        ...,
        description="List of task titles",
        min_length=1,
        max_length=50
    )
    for_list: Optional[str] = Field(
        default=None,
        description="List to add all tasks to"
    )
    priority: Priority = Field(
        default=Priority.NONE,
        description="Priority for all tasks"
    )
    tags: Optional[str] = Field(
        default=None,
        description="Tags for all tasks"
    )
    due: Optional[str] = Field(
        default=None,
        description="Due date for all tasks"
    )


class PasteTasksInput(BaseModel):
    """Input for pasting text as tasks."""
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Text to convert (each line = one task)",
        min_length=1
    )
    in_project: str = Field(
        ...,
        description="Project title to paste into"
    )
    for_list: str = Field(
        ...,
        description="List containing the project"
    )


class GetTaskIDInput(BaseModel):
    """Input for getting a task's UID."""
    model_config = ConfigDict(str_strip_whitespace=True)

    task: str = Field(
        ...,
        description="Task title",
        min_length=1
    )
    for_list: str = Field(
        ...,
        description="List containing the task"
    )
    save_in_clipboard: bool = Field(
        default=True,
        description="Save UID to clipboard"
    )


class ShowListInput(BaseModel):
    """Input for showing a specific list."""
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        description="List name",
        min_length=1
    )


class SearchInput(BaseModel):
    """Input for searching in 2Do."""
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(
        ...,
        description="Search query (use 'type:overdue', 'tags:name', etc.)",
        min_length=1
    )


# ============================================================================
# URL BUILDERS
# ============================================================================

def _build_add_url(params: AddTaskInput) -> str:
    """Build URL scheme for adding a task."""
    url_params = [f"task={quote(params.task)}"]

    if params.task_type != TaskType.TASK:
        url_params.append(f"type={params.task_type.value}")

    if params.for_list:
        url_params.append(f"forlist={quote(params.for_list)}")

    if params.note:
        url_params.append(f"note={quote(params.note)}")

    if params.subtasks:
        url_params.append(f"subtasks={quote(params.subtasks)}")

    if params.priority != Priority.NONE:
        url_params.append(f"priority={params.priority.value}")

    if params.starred:
        url_params.append("starred=1")

    if params.tags:
        url_params.append(f"tags={quote(params.tags)}")

    if params.locations:
        url_params.append(f"locations={quote(params.locations)}")

    if params.due:
        url_params.append(f"due={quote(params.due)}")

    if params.due_time:
        url_params.append(f"dueTime={quote(params.due_time)}")

    if params.start:
        url_params.append(f"start={quote(params.start)}")

    if params.repeat:
        url_params.append(f"repeat={params.repeat.value}")

    if params.action:
        url_params.append(f"action={quote(params.action)}")

    if params.for_parent_name:
        url_params.append(f"forParentName={quote(params.for_parent_name)}")

    if params.for_parent_task:
        url_params.append(f"forParentTask={quote(params.for_parent_task)}")

    if params.ignore_defaults:
        url_params.append("ignoreDefaults=1")

    if params.save_in_clipboard:
        url_params.append("saveInClipboard=1")

    if params.edit:
        url_params.append("edit=1")

    return "twodo://x-callback-url/add?" + "&".join(url_params)


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool(name="twodo_add_task")
async def twodo_add_task(params: AddTaskInput) -> str:
    """
    Add a new task to 2Do.

    Creates a task via URL scheme. The task's UID is saved to clipboard
    by default for reference.

    Examples:
        - Simple: task="Buy milk"
        - With due: task="Meeting", due="2025-01-25", due_time="14:00"
        - High priority: task="Urgent", priority="3", starred=True
        - To list: task="Call mom", for_list="Personal"
        - As subtask: task="Item", for_parent_name="Shopping", for_list="Home"
    """
    url = _build_add_url(params)
    success, message = _open_url(url)

    if success:
        time.sleep(0.5)
        task_uid = _get_clipboard() if params.save_in_clipboard else None

        return json.dumps({
            "success": True,
            "task": params.task,
            "list": params.for_list or "(default)",
            "uid": task_uid if task_uid and len(task_uid) == 32 else None
        }, indent=2)
    else:
        return json.dumps({"success": False, "error": message}, indent=2)


@mcp.tool(name="twodo_add_multiple_tasks")
async def twodo_add_multiple_tasks(params: AddMultipleTasksInput) -> str:
    """
    Add multiple tasks to 2Do.

    Creates multiple tasks with shared settings.

    Example:
        tasks=["Milk", "Bread", "Eggs"], for_list="Shopping"
    """
    results = []

    for task_title in params.tasks:
        task_params = AddTaskInput(
            task=task_title,
            for_list=params.for_list,
            priority=params.priority,
            tags=params.tags,
            due=params.due,
            save_in_clipboard=False
        )
        url = _build_add_url(task_params)
        success, message = _open_url(url)
        results.append({
            "task": task_title,
            "success": success,
            "error": None if success else message
        })
        time.sleep(0.3)

    successful = sum(1 for r in results if r["success"])

    return json.dumps({
        "total": len(params.tasks),
        "successful": successful,
        "failed": len(params.tasks) - successful,
        "results": results
    }, indent=2)


@mcp.tool(name="twodo_paste_tasks")
async def twodo_paste_tasks(params: PasteTasksInput) -> str:
    """
    Paste text as tasks into a project.

    Each line becomes a separate subtask.

    Example:
        text="Item 1\\nItem 2\\nItem 3", in_project="Shopping", for_list="Home"
    """
    url = f"twodo://x-callback-url/paste?text={quote(params.text)}&inProject={quote(params.in_project)}&forList={quote(params.for_list)}"
    success, message = _open_url(url)

    task_count = len([line for line in params.text.split('\n') if line.strip()])

    return json.dumps({
        "success": success,
        "project": params.in_project,
        "list": params.for_list,
        "tasks_added": task_count if success else 0,
        "error": None if success else message
    }, indent=2)


@mcp.tool(name="twodo_get_task_id")
async def twodo_get_task_id(params: GetTaskIDInput) -> str:
    """
    Get a task's unique identifier (UID).

    Requires knowing the exact task title and list name.
    The UID is saved to clipboard.
    """
    save_param = "1" if params.save_in_clipboard else "0"
    url = f"twodo://x-callback-url/getTaskID?task={quote(params.task)}&forList={quote(params.for_list)}&saveInClipboard={save_param}"
    success, message = _open_url(url)

    if success:
        time.sleep(0.5)
        uid = _get_clipboard() if params.save_in_clipboard else None

        return json.dumps({
            "success": True,
            "task": params.task,
            "list": params.for_list,
            "uid": uid if uid and len(uid) == 32 else None
        }, indent=2)
    else:
        return json.dumps({"success": False, "error": message}, indent=2)


@mcp.tool(name="twodo_show_list")
async def twodo_show_list(params: ShowListInput) -> str:
    """Navigate to a specific list in 2Do."""
    url = f"twodo://x-callback-url/showList?name={quote(params.name)}"
    success, message = _open_url(url)

    return json.dumps({
        "success": success,
        "list": params.name,
        "error": None if success else message
    }, indent=2)


@mcp.tool(name="twodo_show_today")
async def twodo_show_today() -> str:
    """Show Today view in 2Do."""
    success, message = _open_url("twodo://x-callback-url/showToday")
    return json.dumps({"success": success, "view": "Today"}, indent=2)


@mcp.tool(name="twodo_show_starred")
async def twodo_show_starred() -> str:
    """Show Starred view in 2Do."""
    success, message = _open_url("twodo://x-callback-url/showStarred")
    return json.dumps({"success": success, "view": "Starred"}, indent=2)


@mcp.tool(name="twodo_show_scheduled")
async def twodo_show_scheduled() -> str:
    """Show Scheduled view in 2Do."""
    success, message = _open_url("twodo://x-callback-url/showScheduled")
    return json.dumps({"success": success, "view": "Scheduled"}, indent=2)


@mcp.tool(name="twodo_show_all")
async def twodo_show_all() -> str:
    """Show All Tasks view in 2Do."""
    success, message = _open_url("twodo://x-callback-url/showAll")
    return json.dumps({"success": success, "view": "All"}, indent=2)


@mcp.tool(name="twodo_search")
async def twodo_search(params: SearchInput) -> str:
    """
    Search in 2Do app.

    Opens 2Do with search pre-filled. Results shown in app.

    Search syntax examples:
        - "John" - search for text
        - type:overdue - overdue tasks
        - tags:call - tasks with tag
        - (clipboard) - search clipboard contents
    """
    url = f"twodo://x-callback-url/search?text={quote(params.text)}"
    success, message = _open_url(url)

    return json.dumps({
        "success": success,
        "query": params.text,
        "note": "Results shown in 2Do app" if success else None,
        "error": None if success else message
    }, indent=2)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
