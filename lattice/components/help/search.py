"""Help search: an in-memory inverted index over every help topic, ranked with BM25.

Built once at startup by create_app (a few hundred topics index in milliseconds).
Words are lowercased and lightly stemmed ("approving" and "approved" both match
"approve"). Every query word must match; the last word also matches as a prefix,
so results appear while typing. Matches in a title, keywords or headings count
more than matches in the body. Results honour each topic's roles.
"""

from __future__ import annotations

import bisect
import html
import math
import re
from collections import defaultdict
from dataclasses import dataclass

from markupsafe import Markup

from lattice.components.help.content import Topic

FIELD_WEIGHTS = {"title": 5.0, "keywords": 3.0, "headings": 3.0, "summary": 2.0, "body": 1.0}
K1, B = 1.2, 0.75
MAX_PREFIX_EXPANSIONS = 30
SNIPPET_CHARS = 180
STOP_WORDS = frozenset(["a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its", "of", "on", "or", "so", "that", "the", "their", "then", "there", "these", "this", "to", "was", "what", "when", "where", "which", "who", "will", "with", "you", "your"])
_WORD = re.compile(r"[a-z0-9]+")


def stem(word: str) -> str:
    for suffix in ("ingly", "edly", "ing", "ies", "ied", "ed", "es", "ly", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 4 else word


def tokens(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOP_WORDS]


@dataclass
class Hit:
    topic: Topic
    score: float
    snippet: Markup


class HelpIndex:
    def __init__(self, topics: list[Topic]):
        self.topics = topics
        self.postings: dict[str, dict[int, dict[str, int]]] = defaultdict(dict)
        self.lengths: list[dict[str, int]] = []
        for i, t in enumerate(topics):
            fields = {"title": t.title, "keywords": t.keywords, "summary": t.summary,
                      "headings": " ".join(text for _, _, text in t.toc), "body": t.text}
            lengths = {}
            for name, text in fields.items():
                words = tokens(text)
                lengths[name] = len(words)
                for w in words:
                    counts = self.postings[w].setdefault(i, {})
                    counts[name] = counts.get(name, 0) + 1
            self.lengths.append(lengths)
        n = max(1, len(topics))
        self.average = {f: sum(lens[f] for lens in self.lengths) / n or 1.0 for f in FIELD_WEIGHTS}
        self.vocabulary = sorted(self.postings)

    def _expand(self, term: str, prefix: bool) -> list[str]:
        if not prefix:
            return [term] if term in self.postings else []
        start = bisect.bisect_left(self.vocabulary, term)
        out = []
        for word in self.vocabulary[start:start + MAX_PREFIX_EXPANSIONS]:
            if not word.startswith(term):
                break
            out.append(word)
        return out

    def _weighted_tf(self, doc: int, word: str) -> float:
        counts = self.postings[word].get(doc, {})
        return sum(FIELD_WEIGHTS[f] * tf / (1 - B + B * self.lengths[doc][f] / self.average[f])
                   for f, tf in counts.items())

    def search(self, query: str, user, limit: int = 20) -> list[Hit]:
        raw = [w for w in _WORD.findall(query.lower()) if w not in STOP_WORDS]
        if not raw:
            return []
        typing = not query.endswith(" ")
        groups = []
        for n, word in enumerate(raw):
            prefix = typing and n == len(raw) - 1
            words = self._expand(word if prefix else stem(word), prefix) or \
                (self._expand(stem(word), False) if prefix else [])
            if not words:
                return []                      # every word must match
            groups.append(words)
        total = len(self.topics)
        scores: dict[int, float] = {}
        for i, words in enumerate(groups):
            group_scores: dict[int, float] = {}
            for word in words:
                docs = self.postings[word]
                idf = math.log(1 + (total - len(docs) + 0.5) / (len(docs) + 0.5))
                for doc in docs:
                    tf = self._weighted_tf(doc, word)
                    group_scores[doc] = max(group_scores.get(doc, 0.0), idf * tf * (K1 + 1) / (tf + K1))
            if i == 0:
                scores = group_scores
            else:
                scores = {d: s + group_scores[d] for d, s in scores.items() if d in group_scores}
        hits = [Hit(self.topics[d], s, snippet(self.topics[d], raw))
                for d, s in scores.items() if self.topics[d].visible_to(user)]
        hits.sort(key=lambda h: (-h.score, h.topic.title))
        return hits[:limit]


def snippet(topic: Topic, words: list[str]) -> Markup:
    """A short passage from the topic around the first query word, with matches marked."""
    text = re.sub(r"\s+", " ", topic.text).strip()
    lowered = text.lower()
    stems = [stem(w) for w in words]
    positions = [lowered.find(s) for s in stems if lowered.find(s) >= 0]
    if positions:
        start = max(0, min(positions) - SNIPPET_CHARS // 3)
        start = lowered.rfind(" ", 0, start) + 1 if start else 0
    else:
        start = 0
    passage = text[start:start + SNIPPET_CHARS]
    if start + SNIPPET_CHARS < len(text):
        passage = passage[: passage.rfind(" ")] + " …"
    if start:
        passage = "… " + passage
    marked = html.escape(passage)
    for s in sorted(set(stems), key=len, reverse=True):
        marked = re.sub(rf"(?i)\b({re.escape(html.escape(s))}\w*)", r"<mark>\1</mark>", marked)
    return Markup(marked or html.escape(topic.summary))


INDEX = HelpIndex([])


def build(topics: list[Topic]) -> None:
    global INDEX
    INDEX = HelpIndex(topics)


def search(query: str, user, limit: int = 20) -> list[Hit]:
    return INDEX.search(query, user, limit)
