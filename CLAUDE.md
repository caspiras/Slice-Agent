# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Slice** is a local-first IDE wrapper for Ollama models. Built entirely in **Python**, it provides a beautiful terminal interface with permission-gated command execution, code editing with diffs, and comprehensive document operations.

## Architecture

**Pure Python** implementation using:
- **Rich** - Terminal UI with panels, spinners, syntax highlighting
- **Ollama Python SDK** - Direct API integration for streaming chat and tool calling
- **prompt-toolkit** - Interactive prompts with command history
- Document libraries - pypdf, python-docx, openpyxl, python-pptx

### Core Components

1. **main.py** - CLI entry point, signal handling (double Ctrl+C to exit), startup banner; constructs `SkillLoader` and initial `ChatSession`
2. **ui.py** - ModelSelector (arrow-key selection) and ChatUI (prompt interface); handles `/model` switching and skill discovery display
3. **chat.py** - ChatSession class, Ollama API integration, the 7 tool definitions and their execution; also dispatches `/skill` commands and auto-loads `SLICE.md` project instructions
4. **executor.py** - CommandExecutor class for sandboxed bash execution with permission prompts
5. **document_reader.py** - Read PDF, Word, Excel, PowerPoint, CSV, text files
6. **document_writer.py** - Write Word, Excel, PowerPoint, PDF, CSV, text files with operations
7. **convert_helpers.py** - Standalone Python conversion scripts (as strings). NOTE: currently **not imported anywhere** — the live conversion logic is duplicated in-process inside `chat.py` (`_convert_*` methods). Treat this file as dead/reference code unless you wire it up.
8. **skills.py** - SkillLoader/Skill: discover and parse folder-based custom slash commands from `skills/`

### Project Structure

```
slice/
├── src/slice/
│   ├── main.py              # Entry point & signal handling (~81 lines)
│   ├── ui.py                # ModelSelector & ChatUI (Rich + prompt-toolkit) (~245 lines)
│   ├── chat.py              # ChatSession with Ollama integration + tools (~1118 lines)
│   ├── executor.py          # CommandExecutor for sandboxed bash (~211 lines)
│   ├── document_reader.py   # Multi-format document reading (~253 lines)
│   ├── document_writer.py   # Multi-format document writing (~567 lines)
│   ├── convert_helpers.py   # File→JSON conversion scripts (~139 lines)
│   └── skills.py            # Skill loader & parser (~130 lines)
├── skills/                  # Optional user-defined slash commands (one folder per skill)
│   └── <skill-name>/skill.md
├── pyproject.toml           # Python package config (v1.6.1)
└── README.md                # User documentation
```

## Development Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run Slice
slice

# Format code (line-length 100, target py39)
black src/

# Lint code (line-length 100, target py39)
ruff check src/

# Note: Tests directory doesn't exist yet - pytest infrastructure is configured but tests not yet written
```

## Key Architecture Principles

### 1. Permission-Gated Actions

**Core principle:** Ask permission only when attempting to escape the sandboxed directory.

- **Chat responses** flow naturally without interruption
- **Commands within the sandbox** execute automatically without prompts
- **Sandbox escape attempts** (accessing outside the working directory) trigger red warnings requiring explicit "yes" confirmation
- **Code edits** (edit_code tool) still show diffs and require approval before applying changes
- User sees full context for any operation that requires permission

### 2. Tool-Based Model Interaction

Slice uses Ollama's function/tool calling feature. Models that support tools receive 7 tool definitions:

**Available Tools:**
1. **bash** - Execute shell commands (file operations, git, search, etc.)
2. **read_document** - Read PDF, Word (.docx), Excel (.xlsx), CSV, text files
3. **write_document** - Write Word, Excel, PowerPoint, PDF, CSV, text with JSON operations
4. **edit_code** - Edit source code files with diff preview and approval
5. **convert_to_json** - Convert Excel/CSV/Word/PDF to JSON (CSV read in `CSV_CHUNK_SIZE`=10k chunks; PDF page-by-page)
6. **convert_to_markdown** - Convert Excel/CSV/Word/PDF to Markdown (tables rendered with `|` syntax via `tabulate`)
7. **fetch_url** - Fetch/read a web page (http/https) via stdlib `urllib`; permission-gated; HTML stripped to text

**Tool-capable models:** the authoritative list is `TOOL_CAPABLE_MODELS` in `chat.py` (llama3/llama3.1/llama3.2/llama3.3, mistral, gemma/gemma2/gemma4, command-r/command-r-plus, qwen/qwen2). Note: llama3.1 8B has weak tool calling in practice — prefer gemma4. (The README also recommends `granite4`, but it is not currently in `TOOL_CAPABLE_MODELS` — add it there if you want it auto-detected.)

**How it works:**
- Model decides when to call tools based on user request
- ChatSession receives tool calls from Ollama API
- Tool handlers execute with user permission
- Results fed back to model for final response

### 3. Directory Sandboxing

All operations are restricted to the directory where `slice` was started.

**CommandExecutor detects sandbox escapes:**
- Absolute paths (`/tmp/file`)
- Home directory (`~/Documents/file`)
- Parent traversal (`../../../file`)
- Directory changes (`cd /tmp`)

**Protection layers:**
- Red warning panel for sandbox escapes
- Requires explicit "yes" confirmation (not just "y")
- Shows all suspicious paths found in command
- 30-second timeout on all commands

### 4. Signal Handling (Ctrl+C)

**Double-press to exit pattern:**
- First Ctrl+C: Warning message, increments `exit_count`
- Second Ctrl+C: Actual exit
- Applies during prompt input and model streaming
- Set up in `main.py`, must not be overridden

### 5. UI/UX Requirements

**Visual identity:**
- **Prompt cursor:** 🍕 (pizza emoji)
- **Thinking indicator:** "baking..." with spinner
- **Streaming responses:** Word-by-word token display
- **Model selection:** Arrow-key navigation with tool support indicators `[tools ✓]`
- **Model switching:** `/model` command preserves conversation history

**Implementation details:**
- Rich Live displays for spinners (use `transient=True` for cleanup)
- Syntax-highlighted diffs for code edits
- Panel displays for commands and outputs
- FileHistory for command history (up/down arrows)

## Tool Execution Flow

### Bash Tool
```python
# In chat.py, ChatSession._execute_command()
1. Model calls bash tool with command string
2. ChatSession passes to CommandExecutor.execute_with_permission()
3. CommandExecutor checks for sandbox escape attempts
4. If trying to escape sandbox: shows red warning and requires explicit "yes" confirmation
5. If staying within safe_directory: executes automatically without prompt
6. Subprocess runs with 30s timeout in safe_directory
7. Result returned to model
```

### Read Document Tool
```python
# In chat.py, ChatSession._read_document()
1. Model calls read_document with file_path
2. Imports from document_reader module
3. read_document() detects file type by extension
4. Appropriate reader (pypdf, python-docx, openpyxl, etc.)
5. Returns formatted text content to model
```

### Write Document Tool
```python
# In chat.py, ChatSession._write_document()
1. Model calls write_document with file_path and operations JSON
2. Operations parsed (single object or array)
3. Imports from document_writer module
4. write_document() applies operations sequentially
5. Returns success/failure count to model
```

### Edit Code Tool
```python
# In chat.py, ChatSession._edit_code()
1. Model calls edit_code with file_path, old_content, new_content, description
2. Read original file content
3. Check if old_content exists exactly
4. Generate unified diff with difflib
5. Show syntax-highlighted diff in panel
6. Ask user for approval
7. If approved: write new content
8. Return result to model
```

### Convert Tools (to JSON / to Markdown)
```python
# In chat.py, ChatSession._convert_to_json() / ._convert_to_markdown()
1. Model calls convert_to_json or convert_to_markdown with input_file, output_file
2. Paths resolved relative to safe_directory; source format detected by extension (.xlsx/.csv/.docx/.pdf)
3. Dispatched to a per-format helper that runs IN-PROCESS (imports pandas / python-docx / pypdf directly,
   NOT via the executor). CSV is read in CSV_CHUNK_SIZE (10k) chunks; PDF is processed page-by-page.
4. Markdown path renders tables with tabulate ("|"-delimited)
5. Writes output_file and returns a success/row/page summary to the model
```

### Fetch URL Tool
```python
# In chat.py, ChatSession._fetch_url()
1. Model calls fetch_url with a url (must be http:// or https://)
2. Permission prompt shows the URL in a panel; user must approve (y/N) BEFORE any network call
3. On approval: urllib.request.urlopen with URL_FETCH_TIMEOUT (30s) and a Slice User-Agent
4. HTML responses run through _html_to_text() (strips <script>/<style>, tags, unescapes entities)
5. Truncated to MAX_DOCUMENT_CHARS, returned to the model
# Note: URLs are network access (outside the filesystem sandbox by design) — the gate is the
# permission prompt, not the sandbox-escape check. Uses stdlib only (no requests dependency).
```

## Project Instructions (SLICE.md)

Slice auto-loads a per-project instructions file so users can give the model persistent,
project-specific guidance (its analogue to this CLAUDE.md, but for the Ollama model at runtime).

- `ChatSession.__init__` calls `refresh_project_instructions()`, which reads `SLICE.md` from the
  sandbox directory (`PROJECT_INSTRUCTIONS_FILE` constant) via `_read_project_instructions()`.
  Missing/unreadable → silently ignored (never blocks startup).
- If present, its contents are injected as a **second `system` message** right after the base
  system prompt (header from `_project_instructions_header()`), and `self.has_project_instructions`
  is set. `main.py` prints a load confirmation, or a hint to create one when absent.
- **Auto-reload:** `refresh_project_instructions()` is called at the start of every `process_stream`
  turn. It compares the file's current text to the last-synced copy (`self._project_instructions_text`)
  and, on change, updates the existing instruction message **in place** (found by header prefix so it
  never duplicates). Handles create / edit / delete of `SLICE.md` mid-session — edits take effect on
  the next prompt, no restart needed.
- **Persistence across `/model`:** `ui._switch_model()` copies the old `conversation_history` into
  the new session, then calls `refresh_project_instructions(force=True)`. The `force` bypasses the
  unchanged-text short-circuit so a stale copy carried over in the history is replaced with the
  current file contents.

## Document Operations

### Supported Read Formats
- **PDF (.pdf)** - Extract text from all pages (pypdf)
- **Word (.docx)** - Read paragraphs and tables (python-docx)
- **Excel (.xlsx)** - Read all sheets with row/column data (openpyxl)
- **CSV (.csv)** - Read all rows with row numbers
- **Text files** - Any text-based file with encoding detection

### Supported Write Formats
- **Word (.docx)** - append_paragraph, replace_text, insert_after
- **Excel (.xlsx)** - set_cell, append_row, set_column
- **PowerPoint (.pptx)** - add_slide
- **PDF (.pdf)** - add_page, add_paragraph, add_text
- **CSV (.csv)** - append_row, set_cell
- **Text files** - replace_content, append_text

### Operation Examples

```python
# Word operations
{"type": "append_paragraph", "text": "New paragraph"}
{"type": "replace_text", "find": "old", "replace": "new"}
{"type": "insert_after", "search": "Header", "text": "Content"}

# Excel operations
{"type": "set_cell", "sheet": "Sheet1", "row": 5, "col": "M", "value": "Data"}
{"type": "append_row", "sheet": "Sheet1", "values": ["A", "B", "C"]}
{"type": "set_column", "sheet": "Sheet1", "col": "M", "start_row": 3, "values": ["X", "Y"]}

# PowerPoint operations
{"type": "add_slide", "title": "Title", "content": "Content"}

# PDF operations
{"type": "add_page", "title": "Page Title", "content": "Page content"}
{"type": "add_paragraph", "text": "Paragraph text", "font_size": 12}
{"type": "add_text", "text": "Text content", "font_size": 14}

# CSV operations
{"type": "append_row", "values": ["col1", "col2", "col3"]}
{"type": "set_cell", "row": 2, "col": 1, "value": "Value"}

# Text file operations
{"type": "replace_content", "text": "Entirely new content"}
{"type": "append_text", "text": "\nAppended text"}
```

## Model Switching with /model

**How it works:**
1. User types `/model` at the 🍕 prompt
2. ModelSelector displays available models with arrow-key navigation
3. User selects new model
4. New ChatSession created with selected model
5. **Conversation history preserved** via `session.conversation_history`
6. Sandbox directory remains the same

**Implementation:**
- ChatUI holds reference to `safe_directory`
- On model switch: `new_session = ChatSession(new_model, safe_directory)`
- Copy history: `new_session.conversation_history = old_session.conversation_history`
- Lazy import of ChatSession in `ui.py._switch_model()` avoids circular dependencies
- **The `skill_loader` must be passed through on switch** (`ChatSession(..., skill_loader=self.session.skill_loader)`) — otherwise skills silently stop working after `/model` (this was the v1.5.1 bug fix)

## Skills System (custom `/slash` commands)

Skills let users define reusable instruction sets invoked as `/skill-name`.

**Discovery & format (`skills.py`):**
- `SkillLoader(working_directory)` scans `<safe_dir>/skills/` at startup (in `main.py`)
- **Folder-per-skill layout:** each skill is a subdirectory containing a `skill.md`; the *folder name* is the canonical invocation name. A `name:` field in frontmatter is **ignored** (only the folder name counts).
- `skill.md` requires YAML-ish frontmatter (`---` delimited) with a required `description:` and non-empty instructions below the closing `---`. Any other frontmatter key lands in `metadata`.
- A malformed skill logs a warning and is skipped — it never aborts startup.

**Invocation flow (`chat.py` `process_stream`):**
1. Input starting with `/` (and `skill_loader` present) is parsed for the first word as the skill name
2. If it matches a loaded skill, the skill's instructions are injected as a **system message**, followed by a synthetic user message telling the model to execute the skill
3. If it doesn't match a loaded skill, the input is treated as normal chat (so `/model` is handled separately, in `ui.py`, before reaching here)

**Where skills surface in the UI:** `ChatUI.run()` prints the available `/skill` names on startup when `skill_loader.has_skills()`.

> Note: the top-level `skills/README.md` still documents the older flat `my-skill.md` layout; the code (and repo's example skills) use the folder-per-skill layout. Prefer the code's behavior.

## System Message Guidelines

The system message in `chat.py` guides model behavior:

**Tool usage rules:**
- Use bash for file/system operations, NOT for echoing knowledge answers
- Use read_document directly without ls/find verification first
- Use edit_code for source code with diff workflow
- Use write_document for ALL document types (Word, Excel, PowerPoint, PDF, CSV, text)

**Spreadsheet editing workflow (CRITICAL for model success):**
1. **Always read first** - Use read_document to see current structure
2. **Identify changes** - Determine which rows, columns, cells need updating
3. **Use JSON operations** - Pass structured operations to write_document
4. **Common patterns:**
   - Set cell: `{"type": "set_cell", "sheet": "Sheet1", "row": 2, "col": "A", "value": "Data"}`
   - Add row: `{"type": "append_row", "sheet": "Sheet1", "values": ["col1", "col2"]}`
   - Fill column: `{"type": "set_column", "sheet": "Sheet1", "col": "B", "start_row": 2, "values": [10, 20]}`
5. **CSV files** - Same operations but omit "sheet" parameter
6. **Multiple operations** - Combine in array: `[{...}, {...}]`
7. **Column references** - Use letters ("A", "M") or numbers (1, 13)
8. **Row indexing** - 1-indexed (row 1 is first row)

**PDF editing workflow:**
- PDFs can be created and edited with write_document tool
- Common operations: add_page, add_paragraph, add_text
- Use read_document to read existing PDFs
- PDFs are built sequentially - operations applied in order
- Example: `{"type": "add_page", "title": "Report", "content": "Summary text"}`

**Git operation rules:**
- Read-only: safe to suggest (status, log, diff, show, branch)
- Local: safe to suggest (add, commit, checkout -b, merge)
- Remote: **NEVER suggest push/pull unless user explicitly asks**
- After commits, remind user they can push when ready

**File operation rules:**
- When user mentions filename, read directly - don't verify existence first
- Use bash `touch filename` for empty text files only
- **Never** use touch for document files (Excel, Word, PowerPoint, PDF) - they need proper structure
- To create new document files, use write_document with operations (it will create the file)
- Multi-file search: bash with grep -r or find

## Testing Local Ollama Models

Ensure Ollama is running:
```bash
ollama list  # Should show downloaded models
```

Download models:
```bash
# Recommended for balanced chat/action behavior
ollama pull gemma4
ollama pull mistral
ollama pull qwen2

# Good for code-heavy tasks
ollama pull llama3.1
```

## Common Pitfalls

1. **Don't break signal handling**
   - The double-Ctrl+C pattern in `main.py` must work everywhere
   - Don't override the signal handler in other modules

2. **Don't suppress chat flow**
   - Permission prompts ONLY appear when trying to **escape the sandbox**
   - Commands within the safe directory execute automatically without prompts
   - Code edits (edit_code) still show diffs and require approval
   - Chat responses and read_document operations flow without interruption

3. **Conversation history**
   - Maintained in `ChatSession.conversation_history`
   - Don't duplicate in UI layer
   - Preserved when switching models

4. **Spinner cleanup**
   - Use Rich `Live` with `transient=True`
   - Spinners must disappear after response completes
   - "baking..." spinner shows during model thinking

5. **Sandbox escapes**
   - Always use `safe_directory` for command execution
   - Never bypass sandbox checks
   - Show red warnings for attempts to escape

6. **Model behavior differences**
   - llama3.x models may try to use bash for knowledge questions
   - gemma4, mistral, qwen2 better at distinguishing chat vs. actions
   - Tool support auto-detected, but some models hallucinate unsupported tools

7. **Spreadsheet operation confusion (common with smaller models)**
   - Models struggle if they don't read the file first
   - JSON operations must be valid and properly escaped
   - Column references can be letters OR numbers - both work
   - For CSV, omit the "sheet" parameter entirely
   - The tool description now includes concrete examples to guide models
   - System message includes step-by-step workflow for spreadsheet editing

## Key Dependencies

```toml
# Core dependencies (from pyproject.toml)
rich>=13.0.0              # Terminal UI
ollama>=0.1.0             # Ollama API client
prompt-toolkit>=3.0.0     # Interactive prompts
pypdf>=4.0.0              # PDF reading
reportlab>=4.0.0          # PDF writing
python-docx>=1.0.0        # Word documents
openpyxl>=3.0.0           # Excel spreadsheets
python-pptx>=0.6.0        # PowerPoint presentations
pandas>=2.0.0             # File format conversion (Excel/CSV to JSON)
tabulate>=0.9.0           # Markdown table rendering (convert_to_markdown)
certifi>=2023.0.0         # CA bundle for HTTPS fetch_url (SSL verification)

# Dev dependencies
pytest>=7.0.0
pytest-asyncio>=0.21.0
black>=23.0.0             # Formatter (line-length 100)
ruff>=0.1.0               # Linter (line-length 100)
```

## Version History

- **v1.6.1** - Current version, streamlined skills & sandbox permissions
  - Skills directory renamed from `slice-skills/` to `skills/` (so other harnesses can discover it); folder-per-skill layout unchanged
  - Sandbox permissions relaxed: commands that stay within the working directory now execute without a prompt; the permission prompt appears **only** on sandbox-escape attempts (absolute paths, `~`, parent traversal, `cd` outside). `edit_code` still shows a diff for approval
  - Fixed stale `__version__` in `src/slice/__init__.py` (was `1.3.0`)

- **v1.6.0** - Project instructions & web access
  - `SLICE.md` auto-loaded per-project instructions (injected as a system message on session start; persists across `/model`)
  - New `fetch_url` tool: permission-gated web page fetching via stdlib `urllib` (HTTPS uses `certifi` CA bundle; HTML stripped to text)
  - Added `certifi` dependency (fixes macOS python.org `CERTIFICATE_VERIFY_FAILED` on HTTPS)
  - Startup hint to create a `SLICE.md` when none is present

- **v1.5.1** - Folder-based skills structure
  - Skills moved from flat `skills/<name>.md` to folder-per-skill `skills/<name>/skill.md`
  - Folder name is the canonical invocation name (frontmatter `name:` ignored)
  - Bug fix: skills now persist across `/model` switches (skill_loader passed to new ChatSession)

- **v1.5.0** - Skills system
  - Custom `/slash` commands defined in `skills/` (SkillLoader in `skills.py`)
  - Example skills: `/hello`, `/test`, `/git-status`

- **v1.4.0** - Enhanced model behavior for tool calling
  - System-message fixes so models create Python apps with bash (not write_document)
  - Better sequential tool execution (create file → run file); guidance for executable files
  - Better behavior for gemma4 and others; llama3.1 8B noted as weak for tools

- **v1.3.2** - Markdown conversion
  - Added `convert_to_markdown` tool (Excel/CSV/Word/PDF → Markdown, tables via `tabulate`)

- **v1.3.1** - Large-file conversion & Word tables
  - Word table extraction alongside paragraphs
  - Dedicated `convert_to_json` tool (replaces error-prone bash one-liners; chunked for large files)

- **v1.3.0** - Universal file-to-JSON conversion and UI fixes
  - Added universal file-to-JSON conversion support (Excel, CSV, Word, PDF)
  - Excel/CSV use pandas for tabular data conversion
  - Word documents use python-docx to extract paragraphs
  - PDF files use pypdf to extract pages
  - All conversions via direct bash commands (no read step required)
  - Fixed `<tool_call>` tags appearing in model output
  - Fixed models not responding after read_document tool calls
  - Improved error messages for failed write operations
  - Optimized system message to prevent unnecessary file reads during conversion
  - Fixed all spinners to properly clean up (transient=True)
  - Updated banner with improved tips (Ctrl+C behavior, Ctrl+Z info)

- **v1.2.0** - Full document editing support
  - Added PDF writing capability (reportlab)
  - ALL document types now editable (PDF, Word, Excel, PowerPoint, CSV, text)
  - Enhanced spreadsheet operation guidance for better model success
  - Removed read-only PDF restriction
  
- **v1.1.0** - Pure Python architecture
  - Removed Go hybrid architecture
  - Added code editing with diffs (edit_code tool)
  - Improved model switching with history preservation
  - Enhanced terminal UI with Rich
  
- **v1.0.x** - Initial release with Go + Python hybrid
  - Removed in commit 047c7a6
