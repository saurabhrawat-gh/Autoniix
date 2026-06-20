# Token Efficiency Protocol

Applied automatically to every session. Goal: 40-55% token reduction with zero quality loss.

## File Reading

- **Targeted reads first**: Use `grep_search` or `code_search` to locate relevant lines before reading entire files.
- **Offset/limit for large files**: When reading files >300 lines, use offset+limit to read only the relevant section. Never read an entire 1000+ line file unless architecturally necessary.
- **Cache in working memory**: Once a file is read, reference it from memory. Do not re-read the same file in the same session unless it was modified.
- **Batch parallel reads**: When you need multiple files, read them in parallel in a single tool call batch.

## Git & Diffs

- **Stat before full diff**: Run `git diff --stat` first. Only expand files that are relevant to the current task.
- **Targeted diffs**: Use `git diff -- <specific-file>` instead of full repo diffs.
- **Avoid re-reading diffs**: Once a diff is shown, analyze it immediately. Don't re-run the same diff command.

## Command Output

- **Summarize, don't re-read**: After running a command, analyze the output immediately. Don't re-run the same command to "check again."
- **Use `--quiet` or `-q` flags** where available to reduce output verbosity.
- **Pipe through `tail` or `head`** for large outputs: `command 2>&1 | tail -50` instead of full output.

## Conversation

- **Be concise**: Short responses save context window space. Prefer bullet points over paragraphs.
- **Batch independent actions**: Make parallel tool calls when there are no dependencies.
- **Avoid repetition**: Don't restate what's already in the conversation. Reference previous turns implicitly.

## Code Generation

- **Targeted edits**: Use `edit` or `multi_edit` for surgical changes. Never rewrite entire files for small fixes.
- **Minimal diffs**: The smaller the change, the fewer tokens consumed in review and application.
