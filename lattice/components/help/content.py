"""Help content: Markdown topics in an app's help/ folder, loaded once at startup.

Folder layout (see the developer documentation, "Writing help"):

    help/
      index.md             the app's help home (required)
      work-queue.md        a topic; its slug is "work-queue"
      jobs/index.md        a section page; topics in jobs/ belong to it
      jobs/retrying.md     slug "jobs/retrying"
      images/…             images and other files linked from topics
      help.toml            optional: [pages] "nav key" = "slug" or "slug#heading"

Every topic starts with front matter:

    ---
    title: Work Queue            (required)
    summary: One sentence.
    order: 10                    (sorting inside its section; default 100)
    keywords: words searched but not shown
    roles: [admin]               (only these roles see the topic; default everyone)
    ---

Problems (no title, broken links between topics, a page map to a missing topic
or a nav key the app does not own) raise HelpError, and the host does not start.
"""

from __future__ import annotations

import html
import posixpath
import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

DEFAULT_ORDER = 100
# GitHub-style callouts: "> [!NOTE]" as the first line of a quote.
CALLOUT_TONES = {"NOTE": "info", "TIP": "success", "IMPORTANT": "accent",
                 "WARNING": "warning", "CAUTION": "danger"}
_CALLOUT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*")


class HelpError(Exception):
    """A help folder breaks a rule. The message names the app and the file."""


@dataclass
class Topic:
    app: str
    slug: str                     # "" for the help home, "jobs/retrying" for a nested topic
    title: str
    summary: str
    order: int
    keywords: str
    roles: tuple[str, ...]
    html: str
    toc: list[tuple[int, str, str]]          # (level, anchor, text) for h2 and h3
    text: str                                # plain text, for search
    updated: datetime

    @property
    def section(self) -> str:
        """The folder the topic is in ("" at the top level)."""
        return posixpath.dirname(self.slug)

    @property
    def url(self) -> str:
        return f"/help/{self.app}/{self.slug}".rstrip("/")

    def visible_to(self, user) -> bool:
        return user.has_any(self.roles)


@dataclass
class AppHelp:
    key: str
    label: str
    root: Path
    topics: dict[str, Topic] = field(default_factory=dict)
    pages: dict[str, str] = field(default_factory=dict)      # nav key -> "slug" or "slug#anchor"

    @property
    def home(self) -> Topic:
        return self.topics[""]

    def visible(self, user) -> list[Topic]:
        return [t for t in self.topics.values() if t.visible_to(user)]

    def children(self, section: str, user) -> list[Topic]:
        """Topics directly in a section, sorted by order then title (the section page excluded)."""
        kids = [t for t in self.visible(user) if t.slug and t.section == section and
                t.slug != section]
        return sorted(kids, key=lambda t: (t.order, t.title.lower()))

    def neighbours(self, topic: Topic, user) -> tuple[Topic | None, Topic | None]:
        """Previous and next topic in reading order (depth-first through the sections)."""
        order = [self.home, *self._walk("", user)]
        i = next((n for n, t in enumerate(order) if t.slug == topic.slug), None)
        if i is None:
            return None, None
        return (order[i - 1] if i > 0 else None), (order[i + 1] if i + 1 < len(order) else None)

    def _walk(self, section: str, user) -> list[Topic]:
        out = []
        for t in self.children(section, user):
            out.append(t)
            out += self._walk(t.slug, user)
        return out


# ── Markdown ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    return re.sub(r"[^\w\s-]", "", text.lower()).strip().replace(" ", "-")


_FORMATTER = HtmlFormatter(nowrap=True)


def _highlight(code: str, lang: str, _attrs) -> str:
    if lang == "mermaid":
        return f'<pre class="mermaid">{html.escape(code)}</pre>'
    try:
        lexer = get_lexer_by_name(lang) if lang else None
    except ClassNotFound:
        lexer = None
    body = highlight(code, lexer, _FORMATTER) if lexer else html.escape(code)
    return f'<pre class="code"><code class="language-{html.escape(lang or "text")}">{body}</code></pre>'


def _markdown() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "typographer": True, "highlight": _highlight})
    md.enable(["table", "strikethrough"])
    md.use(anchors_plugin, min_level=2, max_level=3, slug_func=slugify)
    md.use(tasklists_plugin)
    return md


MD = _markdown()


def parse_front_matter(text: str, where: str) -> tuple[dict, str]:
    """`---` block of `key: value` lines at the top of a topic. Lists use `[a, b]`."""
    if not text.startswith("---\n"):
        raise HelpError(f"{where}: missing front matter (--- title: … ---)")
    end = text.find("\n---", 4)
    if end < 0:
        raise HelpError(f"{where}: front matter is not closed with ---")
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise HelpError(f"{where}: front matter line {line!r} is not 'key: value'")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = tuple(v.strip() for v in value[1:-1].split(",") if v.strip())
        else:
            meta[key.strip()] = value
    return meta, text[end + 4:].lstrip("\n")


def _rewrite_links(tokens, file_rel: str, app: str, slugs: set[str], where: str) -> None:
    """Relative links to .md files become help URLs; relative images become asset URLs.

    file_rel is the topic's path inside the help folder without ".md" ("jobs/index").
    """
    base = posixpath.dirname(file_rel)
    for token in tokens:
        for child in token.children or []:
            attr = "href" if child.type == "link_open" else "src" if child.type == "image" else None
            if not attr:
                continue
            target = child.attrGet(attr) or ""
            if re.match(r"^[a-z][a-z0-9+.-]*:|^/|^#", target):
                continue                                  # absolute URL, site path or anchor
            path, _, anchor = target.partition("#")
            resolved = posixpath.normpath(posixpath.join(base, path))
            if resolved.startswith(".."):
                raise HelpError(f"{where}: link {target!r} leaves the help folder")
            if attr == "src" or not path.endswith(".md"):
                child.attrSet(attr, f"/help/{app}/_assets/{resolved}")
                continue
            slug = resolved[:-3]
            slug = "" if slug in ("index", ".") else slug.removesuffix("/index")
            if slug not in slugs:
                raise HelpError(f"{where}: link to {target!r} points to no topic")
            child.attrSet("href", f"/help/{app}/{slug}".rstrip("/") + (f"#{anchor}" if anchor else ""))


def _callouts(tokens) -> None:
    for i, token in enumerate(tokens):
        if token.type != "blockquote_open" or i + 2 >= len(tokens):
            continue
        inline = tokens[i + 2]
        match = _CALLOUT.match(inline.content) if inline.type == "inline" else None
        if not match:
            continue
        token.attrSet("class", f"callout tone-{CALLOUT_TONES[match.group(1)]}")
        token.attrSet("data-label", match.group(1).title())
        first = inline.children[0]
        first.content = _CALLOUT.sub("", first.content)
        if not first.content and len(inline.children) > 1 and inline.children[1].type == "softbreak":
            inline.children = inline.children[2:]


def _toc_and_text(tokens) -> tuple[list[tuple[int, str, str]], str]:
    toc, words = [], []
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag in ("h2", "h3"):
            toc.append((int(token.tag[1]), token.attrGet("id") or "", tokens[i + 1].content))
        if token.type == "inline":
            words.append("".join(" " if c.type in ("softbreak", "hardbreak") else c.content
                                 for c in token.children or []))
        elif token.type == "fence" and token.info != "mermaid":
            words.append(token.content)
    return toc, "\n".join(words)


# ── Loading ──────────────────────────────────────────────────────────────────

def _slug_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("").as_posix()
    return "" if rel == "index" else rel.removesuffix("/index")


def load_help(key: str, label: str, root: Path, owned_nav_keys: set[str]) -> AppHelp:
    """Read and render every topic under root, and check the page map."""
    if not (root / "index.md").is_file():
        raise HelpError(f"Help for {key!r}: {root} has no index.md (the help home)")
    files = sorted(root.rglob("*.md"))
    slugs = {_slug_for(p, root) for p in files}
    app = AppHelp(key=key, label=label, root=root)
    for path in files:
        where = f"Help for {key!r}, {path.relative_to(root)}"
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"), where)
        if not meta.get("title"):
            raise HelpError(f"{where}: front matter needs a title")
        slug = _slug_for(path, root)
        env: dict = {}
        tokens = MD.parse(body, env)
        _rewrite_links(tokens, path.relative_to(root).with_suffix("").as_posix(), key, slugs, where)
        _callouts(tokens)
        toc, text = _toc_and_text(tokens)
        try:
            order = int(meta.get("order", DEFAULT_ORDER))
        except ValueError as exc:
            raise HelpError(f"{where}: order must be a whole number") from exc
        roles = meta.get("roles", ())
        app.topics[slug] = Topic(
            app=key, slug=slug, title=meta["title"], summary=meta.get("summary", ""),
            order=order, keywords=meta.get("keywords", ""),
            roles=roles if isinstance(roles, tuple) else (roles,),
            html=MD.renderer.render(tokens, MD.options, env), toc=toc, text=text,
            updated=datetime.fromtimestamp(path.stat().st_mtime, UTC).replace(tzinfo=None))
    app.pages = _load_page_map(key, root, app.topics, owned_nav_keys)
    return app


def _load_page_map(key: str, root: Path, topics: dict[str, Topic],
                   owned_nav_keys: set[str]) -> dict[str, str]:
    path = root / "help.toml"
    if not path.is_file():
        return {}
    where = f"Help for {key!r}, help.toml"
    try:
        pages = tomllib.loads(path.read_text(encoding="utf-8")).get("pages", {})
    except tomllib.TOMLDecodeError as exc:
        raise HelpError(f"{where}: {exc}") from exc
    for nav_key, target in pages.items():
        if nav_key not in owned_nav_keys:
            raise HelpError(f"{where}: {nav_key!r} is not a page of this app")
        slug, _, anchor = str(target).partition("#")
        topic = topics.get(slug)
        if topic is None:
            raise HelpError(f"{where}: {nav_key!r} maps to {target!r}, which is no topic")
        if anchor and anchor not in {a for _, a, _ in topic.toc}:
            raise HelpError(f"{where}: {target!r} has no heading #{anchor}")
    return dict(pages)


# ── Registry ─────────────────────────────────────────────────────────────────

# Filled by create_app: Lattice's own help first, then each app with a help folder.
HELP: dict[str, AppHelp] = {}


def reset() -> None:
    HELP.clear()


def register(app_help: AppHelp) -> None:
    HELP[app_help.key] = app_help


def target_for(nav_key: str, app_key: str) -> str:
    """URL of the help for a page: its mapped topic, else its app's help home, else /help."""
    app = HELP.get(app_key)
    if app is None:
        return "/help"
    mapped = app.pages.get(nav_key)
    if mapped is None:
        return app.home.url
    slug, _, anchor = mapped.partition("#")
    return app.topics[slug].url + (f"#{anchor}" if anchor else "")
