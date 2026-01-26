# 2Do MCP Server

An MCP (Model Context Protocol) server for the [2Do](https://www.2doapp.com) task management app. Provides **write-only** access to 2Do via URL schemes (x-callback-url).

## Features

| Tool | Description |
|------|-------------|
| `twodo_add_task` | Create a task with full options (priority, due date, tags, etc.) |
| `twodo_add_multiple_tasks` | Create multiple tasks at once |
| `twodo_paste_tasks` | Paste text as subtasks into a project |
| `twodo_get_task_id` | Get a task's UID (requires knowing title + list) |
| `twodo_show_list` | Navigate to a specific list |
| `twodo_show_today` | Show Today view |
| `twodo_show_starred` | Show Starred view |
| `twodo_show_scheduled` | Show Scheduled view |
| `twodo_show_all` | Show All Tasks view |
| `twodo_search` | Open search in 2Do app |

## Requirements

- **macOS** (uses `open` command for URL schemes)
- **2Do app** installed
- **Python 3.10+**

## Installation

```bash
cd ~/Claude/2do-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "twodo": {
      "command": "/Users/YOUR_USER/Claude/2do-mcp/.venv/bin/python",
      "args": ["-m", "twodo_mcp.server"],
      "cwd": "/Users/YOUR_USER/Claude/2do-mcp"
    }
  }
}
```

Replace `YOUR_USER` with your macOS username.

## Usage Examples

**Create a task:**
```
"Add a task to buy milk tomorrow in the Shopping list"
→ twodo_add_task(task="Buy milk", for_list="Shopping", due="1")
```

**Create multiple tasks:**
```
"Add to Shopping: milk, bread, eggs"
→ twodo_add_multiple_tasks(tasks=["Milk", "Bread", "Eggs"], for_list="Shopping")
```

**High priority task:**
```
"Add urgent task: call client"
→ twodo_add_task(task="Call client", priority="3", starred=True)
```

**Show today's tasks:**
```
"Show my tasks for today"
→ twodo_show_today()
```

## Limitations

- **Write-only**: No read API available. Cannot list or query existing tasks.
- **macOS only**: Requires `open` command for URL schemes.
- **No delete/update**: 2Do URL schemes only support creating tasks.

## Development

```bash
source .venv/bin/activate
python -m twodo_mcp.server          # Run server
python -m py_compile src/twodo_mcp/server.py  # Verify syntax
pip install -e ".[dev]"             # Install with dev dependencies
```

## Resources

- [2Do App](https://www.2doapp.com)
- [2Do URL Schemes](https://www.2doapp.com/kb/article/url-schemes.html)
- [Model Context Protocol](https://modelcontextprotocol.io)

## License

MIT License - see [LICENSE](LICENSE) for details.
