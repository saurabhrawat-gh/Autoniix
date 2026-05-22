"""Minimal Markdown -> Atlassian Document Format (ADF) converter.

Handles the markdown patterns that appear in Autoniix GitHub issues:
  - Headings (h1-h6)
  - Paragraphs with inline marks: bold, italic, inline code, links, strike
  - Fenced code blocks (with language)
  - Bullet + ordered lists (nested)
  - Task lists ("- [ ] x" / "- [x] x")
  - Block quotes
  - Horizontal rules
  - Tables (simple grid)

Output: a valid ADF document dict ready to put in Jira's `description` field.
"""
from __future__ import annotations

import re
from typing import Any

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "breaks": False}).enable(
    ["table", "strikethrough"]
)

TASK_RE = re.compile(r"^\s*\[([ xX])\]\s+(.*)$")


def _text(t: str, marks: list[dict] | None = None) -> dict:
    node: dict[str, Any] = {"type": "text", "text": t}
    if marks:
        # ADF rule: 'code' mark cannot combine with other marks.
        # If code is present, drop all other marks.
        types = {m.get("type") for m in marks}
        if "code" in types and len(types) > 1:
            marks = [m for m in marks if m.get("type") in ("code", "link")]
            # Also drop link if 'code' demands purity. Keep code+link OK actually? Spec: code allows link.
        # Deduplicate
        seen = set()
        clean: list[dict] = []
        for m in marks:
            key = (m.get("type"), str(m.get("attrs")))
            if key in seen:
                continue
            seen.add(key)
            clean.append(m)
        if clean:
            node["marks"] = clean
    return node


def _inline_to_adf(tokens: list) -> list[dict]:
    """Convert markdown-it inline tokens into ADF inline nodes."""
    out: list[dict] = []
    mark_stack: list[dict] = []

    def add_text(text: str) -> None:
        if not text:
            return
        out.append(_text(text, list(mark_stack) if mark_stack else None))

    for tok in tokens:
        t = tok.type
        if t == "text":
            add_text(tok.content)
        elif t == "softbreak":
            add_text(" ")
        elif t == "hardbreak":
            out.append({"type": "hardBreak"})
        elif t == "code_inline":
            out.append(_text(tok.content, [*mark_stack, {"type": "code"}]))
        elif t == "strong_open":
            mark_stack.append({"type": "strong"})
        elif t == "strong_close":
            if mark_stack and mark_stack[-1].get("type") == "strong":
                mark_stack.pop()
        elif t == "em_open":
            mark_stack.append({"type": "em"})
        elif t == "em_close":
            if mark_stack and mark_stack[-1].get("type") == "em":
                mark_stack.pop()
        elif t == "s_open":
            mark_stack.append({"type": "strike"})
        elif t == "s_close":
            if mark_stack and mark_stack[-1].get("type") == "strike":
                mark_stack.pop()
        elif t == "link_open":
            href = tok.attrGet("href") or ""
            mark_stack.append({"type": "link", "attrs": {"href": href}})
        elif t == "link_close":
            if mark_stack and mark_stack[-1].get("type") == "link":
                mark_stack.pop()
        elif t == "image":
            alt = tok.attrGet("alt") or tok.content or "image"
            href = tok.attrGet("src") or ""
            out.append(_text(f"[{alt}]({href})"))
        elif t == "html_inline":
            # strip raw HTML tags; keep text-ish
            txt = re.sub(r"<[^>]+>", "", tok.content)
            add_text(txt)
        # ignore other inline types
    if not out:
        out = [_text("")]
    return out


def _para_from_inline(inline_token) -> list[dict]:
    """Return list of one paragraph node containing inline content."""
    return [{"type": "paragraph", "content": _inline_to_adf(inline_token.children or [])}]


def _list_items(tokens: list, start: int, end_type: str) -> tuple[list[dict], int]:
    """Walk tokens from start until matching `end_type`. Return (items, next_index)."""
    items: list[dict] = []
    i = start
    while i < len(tokens) and tokens[i].type != end_type:
        if tokens[i].type == "list_item_open":
            depth = 1
            j = i + 1
            while j < len(tokens) and depth > 0:
                if tokens[j].type == "list_item_open":
                    depth += 1
                elif tokens[j].type == "list_item_close":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = tokens[i + 1 : j]
            items.append({"type": "listItem", "content": _block_tokens_to_adf(inner)})
            i = j + 1
        else:
            i += 1
    return items, i


def _table(tokens: list, start: int) -> tuple[dict, int]:
    """Convert table tokens to ADF table node."""
    rows: list[dict] = []
    i = start + 1  # skip table_open
    while i < len(tokens) and tokens[i].type != "table_close":
        if tokens[i].type in ("thead_open", "tbody_open", "tr_open"):
            if tokens[i].type == "tr_open":
                cells: list[dict] = []
                j = i + 1
                while j < len(tokens) and tokens[j].type != "tr_close":
                    if tokens[j].type in ("th_open", "td_open"):
                        cell_kind = "tableHeader" if tokens[j].type == "th_open" else "tableCell"
                        close_type = tokens[j].type.replace("_open", "_close")
                        # next token is inline content
                        inline = tokens[j + 1] if j + 1 < len(tokens) else None
                        content_nodes = (
                            _inline_to_adf(inline.children or []) if inline and inline.type == "inline" else [_text("")]
                        )
                        cells.append({
                            "type": cell_kind,
                            "content": [{"type": "paragraph", "content": content_nodes}],
                        })
                        # advance to closing tag
                        while j < len(tokens) and tokens[j].type != close_type:
                            j += 1
                    j += 1
                rows.append({"type": "tableRow", "content": cells})
                i = j + 1
                continue
        i += 1
    # find table_close
    while i < len(tokens) and tokens[i].type != "table_close":
        i += 1
    return {"type": "table", "attrs": {"isNumberColumnEnabled": False, "layout": "default"}, "content": rows}, i + 1


def _block_tokens_to_adf(tokens: list) -> list[dict]:
    """Walk a flat list of block tokens and emit ADF blocks."""
    out: list[dict] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        t = tok.type
        if t == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[i + 1]
            out.append({
                "type": "heading",
                "attrs": {"level": min(level, 6)},
                "content": _inline_to_adf(inline.children or []),
            })
            # skip heading_close
            i += 3
            continue
        if t == "paragraph_open":
            inline = tokens[i + 1]
            inline_adf = _inline_to_adf(inline.children or [])
            if inline_adf:
                out.append({"type": "paragraph", "content": inline_adf})
            i += 3
            continue
        if t == "fence" or t == "code_block":
            attrs: dict[str, Any] = {}
            if tok.info:
                attrs["language"] = tok.info.strip().split()[0]
            out.append({
                "type": "codeBlock",
                "attrs": attrs,
                "content": [_text(tok.content.rstrip("\n"))] if tok.content else [],
            })
            i += 1
            continue
        if t == "hr":
            out.append({"type": "rule"})
            i += 1
            continue
        if t == "blockquote_open":
            j = i + 1
            depth = 1
            while j < n and depth > 0:
                if tokens[j].type == "blockquote_open":
                    depth += 1
                elif tokens[j].type == "blockquote_close":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = tokens[i + 1 : j]
            inner_adf = _block_tokens_to_adf(inner)

            # Tables and panels can't live inside a panel/blockquote — lift them out.
            ALLOWED_IN_PANEL = {"paragraph", "heading", "bulletList", "orderedList", "codeBlock", "blockquote"}
            ALLOWED_IN_BLOCKQUOTE = {"paragraph"}

            unwrapped: list[dict] = []         # emitted at top level
            container_content: list[dict] = []  # stays inside the blockquote/panel
            for b in inner_adf:
                btype = b.get("type")
                if btype in ALLOWED_IN_PANEL:
                    container_content.append(b)
                else:
                    unwrapped.append(b)

            non_para = [b for b in container_content if b.get("type") != "paragraph"]
            if container_content:
                if non_para:
                    out.append({
                        "type": "panel",
                        "attrs": {"panelType": "note"},
                        "content": container_content,
                    })
                else:
                    out.append({"type": "blockquote", "content": container_content})

            # Append unwrapped (tables, etc.) at top level so they still render.
            out.extend(unwrapped)

            i = j + 1
            continue
        if t == "bullet_list_open":
            # Detect task list: first list item starts with [ ] / [x]
            is_task = False
            preview_inline = None
            for k in range(i + 1, n):
                if tokens[k].type == "inline":
                    preview_inline = tokens[k]
                    break
                if tokens[k].type == "bullet_list_close":
                    break
            if preview_inline and TASK_RE.match(preview_inline.content or ""):
                is_task = True
            items_block, next_i = _list_items(tokens, i + 1, "bullet_list_close")
            if is_task:
                # Convert listItem -> taskItem, preserving inline formatting
                task_items: list[dict] = []
                for li in items_block:
                    p = next((c for c in li["content"] if c["type"] == "paragraph"), None)
                    state = "TODO"
                    item_content: list[dict] = []
                    if p and p.get("content"):
                        # Strip the leading "[ ] " or "[x] " from the first text node only
                        item_content = [dict(seg) for seg in p["content"]]  # shallow copy
                        if item_content and item_content[0].get("type") == "text":
                            first_text = item_content[0].get("text", "")
                            m = TASK_RE.match(first_text)
                            if m:
                                state = "DONE" if m.group(1).lower() == "x" else "TODO"
                                item_content[0]["text"] = m.group(2)
                                # If stripping leaves it empty, drop the empty text node
                                if not item_content[0]["text"]:
                                    item_content.pop(0)
                    if not item_content:
                        item_content = [_text("")]
                    task_items.append({
                        "type": "taskItem",
                        "attrs": {"localId": f"ti-{i}-{len(task_items)}", "state": state},
                        "content": item_content,
                    })
                out.append({
                    "type": "taskList",
                    "attrs": {"localId": f"tl-{i}"},
                    "content": task_items,
                })
            else:
                out.append({"type": "bulletList", "content": items_block})
            i = next_i + 1
            continue
        if t == "ordered_list_open":
            items_block, next_i = _list_items(tokens, i + 1, "ordered_list_close")
            out.append({"type": "orderedList", "content": items_block})
            i = next_i + 1
            continue
        if t == "table_open":
            tbl, next_i = _table(tokens, i)
            out.append(tbl)
            i = next_i
            continue
        if t == "html_block":
            # Strip HTML tags, keep text
            cleaned = re.sub(r"<[^>]+>", "", tok.content).strip()
            if cleaned:
                out.append({"type": "paragraph", "content": [_text(cleaned)]})
            i += 1
            continue
        # Unknown / closing token — skip
        i += 1
    return out


def _ensure_listitem_content(items: list[dict]) -> None:
    """Jira requires every listItem to have at least one paragraph child."""
    for it in items:
        if it.get("type") == "listItem" and not it.get("content"):
            it["content"] = [{"type": "paragraph", "content": [_text("")]}]
        elif "content" in it:
            _ensure_listitem_content(it["content"])


def _strip_emoji_for_heading(adf: dict) -> dict:
    """Headings can't contain certain ADF nodes — pass through. (No-op for now.)"""
    return adf


def md_to_adf(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [_text("(no content)")]}],
        }
    tokens = _md.parse(text)
    blocks = _block_tokens_to_adf(tokens)
    if not blocks:
        blocks = [{"type": "paragraph", "content": [_text("")]}]
    _ensure_listitem_content(blocks)
    return {"type": "doc", "version": 1, "content": blocks}
