"""Produce an explainable, bounded wiki review set for explicit changed Data sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

INDEXER_ROOT = Path(__file__).resolve().parent.parent
VAULT_ROOT = INDEXER_ROOT.parent
DATA_ROOT = (VAULT_ROOT / "Data").resolve()
METADATA_ROOT = INDEXER_ROOT / "metadata"
WIKI_PREFIX = "Level Knowledge/"
INTERESTS_PREFIX = "Level Knowledge/interests/"
NON_ROUTABLE_WIKI_PAGES = frozenset({"Level Knowledge/index.md", "Level Knowledge/log.md"})
STOPWORDS = frozenset({"about", "after", "and", "are", "does", "for", "from", "how", "into", "is", "its", "of", "the", "this", "what", "when", "with"})
GENERIC_ROUTING_TERMS = frozenset({"document", "documents", "guide", "guides", "information", "knowledge", "note", "notes", "overview", "process", "processes", "reading", "reference", "references", "retrieval", "review", "signal", "system", "systems", "tool", "tools", "update", "updates"})
PERSON_ROUTING_SIGNAL = re.compile(r"\b(joined|hired|promoted|new\s+team\s+members?|new\s+role|taking\s+ownership|hand(?:ing)?\s+off|will\s+own|now\s+owns|assumes\s+ownership)\b", re.IGNORECASE)
OPERATIONAL_FAILURE_SIGNAL = re.compile(r"\b(fail(?:ed|ure)?|crash(?:ed)?|outage|missed\s+data|broken)\b", re.IGNORECASE)
OPERATIONAL_REMEDIATION_SIGNAL = re.compile(r"\b(backfill(?:ing)?|retry|isolate|isolat(?:ed|ion)|monitor(?:ing)?|validat(?:e|ion)|queue(?:d|ing)?|recover(?:y|ed)?)\b", re.IGNORECASE)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_path(value: str) -> tuple[Path, str]:
    candidate = (VAULT_ROOT / value).resolve()
    if not candidate.is_relative_to(DATA_ROOT) or not candidate.is_file():
        raise ValueError(f"Source must be an existing Data/ file: {value}")
    return candidate, candidate.relative_to(VAULT_ROOT).as_posix()


def add_candidate(candidates: dict[str, dict[str, Any]], page: str, score: int, reason: str) -> None:
    entry = candidates.setdefault(page, {"page": page, "score": 0, "reasons": []})
    entry["score"] = max(entry["score"], score)
    if reason not in entry["reasons"]:
        entry["reasons"].append(reason)


def lexical_tokens(value: str) -> set[str]:
    """Return meaningful terms for a deliberately conservative routing sanity check."""
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", value)
        if token.lower() not in STOPWORDS
    }


def ordered_lexical_tokens(value: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", value)
        if token.lower() not in STOPWORDS
    ]


def normalized_entity_terms(registry: dict[str, Any]) -> list[tuple[str, str, str]]:
    terms: list[tuple[str, str, str]] = []
    for entity in registry["entities"]:
        terms.append((entity["canonical_name"], entity["id"], "canonical name"))
        for alias in entity["aliases"]:
            if alias["state"] == "confirmed":
                terms.append((alias["name"], entity["id"], "confirmed alias"))
    return sorted(terms, key=lambda item: len(item[0]), reverse=True)


def ambiguous_alias_terms(registry: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return aliases that must be reviewed rather than used for automatic routing."""
    terms: list[tuple[str, str, str]] = []
    for entity in registry["entities"]:
        for alias in entity["aliases"]:
            if alias["state"] == "ambiguous":
                terms.append((alias["name"], entity["id"], "ambiguous alias"))
    return sorted(terms, key=lambda item: len(item[0]), reverse=True)


def matched_entities(text: str, terms: list[tuple[str, str, str]]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = defaultdict(list)
    for term, entity_id, term_kind in terms:
        if not term:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
        # Short all-caps aliases are acronyms, not ordinary words. Matching
        # them case-insensitively turns a sentence such as "aim for Monday"
        # into the AIM client, so require their written capitalization.
        if term_kind in {"canonical name", "confirmed alias"} and term.isupper() and len(term) <= 4:
            pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)")
        if pattern.search(text):
            description = f"{term_kind}: {term}"
            if description not in matches[entity_id]:
                matches[entity_id].append(description)
    return dict(matches)


def person_requires_review(content: str, canonical_name: str) -> bool:
    """Return true only when a meeting adds durable people-routing context.

    Attendee lists and ordinary conversational mentions are intentionally
    ignored. A team page enters review only for onboarding, a role change, or
    an explicit ownership handoff. Direct graph evidence remains stronger and
    bypasses this predicate.
    """
    body = re.sub(r"\A---.*?---\s*", "", content, flags=re.DOTALL)
    name_pattern = re.compile(r"(?<!\w)" + re.escape(canonical_name) + r"(?!\w)", re.IGNORECASE)
    sentences = re.split(r"(?<=[.!?])\s+|\n+", body)
    return any(PERSON_ROUTING_SIGNAL.search(sentence) for sentence in sentences if name_pattern.search(sentence))


def primary_entity_pages(entity_id: str, kind: str, pages: list[str]) -> list[str]:
    """Return the narrow default target for a registry match.

    A client mention should not automatically fan out to every overview,
    issues, trends, and wins page. If a client has a conventional overview
    path matching its entity slug, use it; direct graph references still select
    any more-specific page independently.
    """
    if kind != "client" or len(pages) <= 1:
        return pages
    slug = entity_id.split(":", 1)[-1]
    matching = [page for page in pages if Path(page).stem == slug]
    return matching[:1] or pages[:1]


def client_is_central(content: str, match_reasons: list[str]) -> bool:
    """Require a client to be named in the title or a dedicated heading.

    Weekly portfolio meetings routinely mention several clients in passing.
    Those mentions are not enough to review an overview page automatically;
    direct graph evidence still selects pages that already cite the source.
    """
    terms = [reason.split(": ", 1)[-1] for reason in match_reasons]
    title_and_headings = "\n".join([source_title(content), *re.findall(r"^#{1,3}\s+(.+?)\s*$", content, re.MULTILINE)])
    for term in terms:
        if not term:
            continue
        flags = 0 if term.isupper() and len(term) <= 4 else re.IGNORECASE
        if re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", title_and_headings, flags):
            return True
    return False


def qmd_executable() -> str | None:
    configured = os.environ.get("QMD_EXECUTABLE")
    if configured and Path(configured).is_file():
        return configured
    discovered = shutil.which("qmd") or shutil.which("qmd.cmd")
    if discovered:
        return discovered
    candidates = [
        Path(os.environ.get("APPDATA", "")) / "npm" / "qmd.cmd",
        Path.home() / ".local" / "bin" / "qmd",
    ]
    return next((str(candidate) for candidate in candidates if candidate.is_file()), None)


def qmd_candidates(query: str, limit: int) -> tuple[list[tuple[str, float]], str | None]:
    executable = qmd_executable()
    if not executable:
        return [], "qmd executable not found; set QMD_EXECUTABLE to override discovery"
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", query)
    keyword_query = " ".join(list(dict.fromkeys(tokens))[:12])
    command = [executable, "query", keyword_query, "-c", "level-knowledge", "-n", str(limit), "--no-rerank", "--format", "json"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=90)
        payload = json.loads(result.stdout)
    except subprocess.CalledProcessError as exc:
        fallback = [executable, "search", keyword_query, "-c", "level-knowledge", "-n", str(limit), "--format", "json"]
        try:
            result = subprocess.run(fallback, capture_output=True, text=True, check=True, timeout=90)
            payload = json.loads(result.stdout)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as fallback_exc:
            return [], (getattr(fallback_exc, "stderr", "") or exc.stderr or str(fallback_exc)).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        return [], str(exc)
    matches: list[tuple[str, float]] = []
    for item in payload:
        uri = str(item.get("file", ""))
        prefix = "qmd://level-knowledge/"
        if uri.startswith(prefix):
            matches.append((WIKI_PREFIX + uri.removeprefix(prefix), float(item.get("score", 0))))
    return matches, None


QmdProvider = Callable[[str, int], tuple[list[tuple[str, float]], str | None]]
PageContentProvider = Callable[[str], str | None]


def source_title(content: str) -> str:
    frontmatter_title = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", content, re.MULTILINE)
    if frontmatter_title:
        return frontmatter_title.group(1).strip().strip("\"'")
    # Prefer a real document heading over hashes in a fenced shell/code sample.
    # Saved technical references often contain commands such as ``# install``;
    # treating those as titles created nonsensical taxonomy review cues.
    body = re.sub(r"\A---.*?---\s*", "", content, flags=re.DOTALL)
    body = re.sub(r"^```.*?^```\s*", "", body, flags=re.DOTALL | re.MULTILINE)
    heading = re.search(r"^#\s+(.+?)\s*$", body, re.MULTILINE)
    if heading:
        return heading.group(1)
    subheading = re.search(r"^##\s+(.+?)\s*$", content, re.MULTILINE)
    return subheading.group(1) if subheading else ""


def extract_markdown_section(content: str, heading: str) -> str:
    """Return one exact level-two Markdown section from an aggregate source.

    Aggregate captures such as monthly Slack exports retain historical content.
    A newly appended dated section is a separate ingest unit: it must not
    inherit direct-reference evidence from the rest of the aggregate file.
    """
    target = heading.removeprefix("##").strip()
    match = re.search(r"^##\s+" + re.escape(target) + r"\s*$", content, re.MULTILINE)
    if not match:
        raise ValueError(f"Section not found: {heading}")
    following = re.search(r"^##\s+", content[match.end():], re.MULTILINE)
    end = match.end() + following.start() if following else len(content)
    return content[match.start():end].strip() + "\n"


def is_clipping_reference(content: str) -> bool:
    """Return true for saved personal/web clippings.

    Data/Knowledge also contains deliberately curated technical references (for
    example, QMD documentation), so its path alone cannot opt a source out of
    discovery. The capture workflow labels ordinary saved articles with the
    ``clippings`` frontmatter tag. Those sources are eligible to build personal
    knowledge, but semantic discovery may only target the dedicated Interests
    domain, never unrelated work pages.
    """
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*", content, re.DOTALL)
    if not frontmatter:
        return False
    return bool(re.search(r"^\s*-\s*[\"']?clippings[\"']?\s*$", frontmatter.group(1), re.MULTILINE | re.IGNORECASE))


def source_routing_class(source_id: str, content: str) -> str:
    """Classify sources whose capture context changes routing confidence.

    The class deliberately controls only discovery/automatic routing. Raw
    sources remain searchable and a later evidence review can still use them.
    """
    if source_id.startswith("Data/Daily/"):
        return "daily-note"
    if source_id.startswith(("Data/Claude/", "Data/Codex/")):
        return "agent-transcript"
    if source_id.startswith("Data/Work/Analytics/"):
        return "reference-library"
    if source_id.startswith("Data/Knowledge/") and is_clipping_reference(content):
        return "personal-clipping"
    return "standard"


def discovery_policy(source_class: str) -> str:
    return {
        "daily-note": "disabled; daily captures need durable evidence before wiki routing",
        "agent-transcript": "review-only; agent transcripts need independent corroboration",
        "reference-library": "review-only; generic reference material cannot auto-select a wiki page",
        "personal-clipping": "interests-only",
    }.get(source_class, "standard")


def topic_discovery_cues(content: str, source_id: str, source_class: str, direct_pages: set[str], source_scope: str | None, existing_scope_matches: set[str], qmd_error: str | None) -> list[dict[str, Any]]:
    """Flag a possible new durable topic without creating or editing it.

    This is intentionally a review cue rather than automatic taxonomy creation:
    one source can reveal a meaningful operational pattern, but cannot settle a
    page's scope or domain by itself.
    """
    if source_class == "personal-clipping":
        # A semantic candidate is deliberately enough to suppress a new-page
        # cue. It may turn out to be only a partial match, but the safe next
        # action is to inspect that page's scope, not to create a duplicate.
        if direct_pages or existing_scope_matches or (source_scope is not None and source_scope != "whole source"):
            return []
        title = source_title(content) or Path(source_id).stem
        status = "needs-review" if qmd_error else "provisionally-independent"
        return [{
            "suggested_domain": "interests",
            "suggested_title": title,
            "score": 35,
            "independence_status": status,
            "reasons": [
                "no existing Interest page was returned by the bounded lexical/semantic scope check",
                "first independent source for this proposed topic",
                "require two independent source hashes before creating an Interest page",
                *( ["QMD was unavailable, so scope independence cannot yet be confirmed"] if qmd_error else [] ),
            ],
        }]
    if source_class in {"daily-note", "agent-transcript", "reference-library"} or direct_pages or existing_scope_matches or (source_scope is not None and source_scope != "whole source"):
        return []
    if "pipeline" in content.lower() and OPERATIONAL_FAILURE_SIGNAL.search(content) and OPERATIONAL_REMEDIATION_SIGNAL.search(content):
        return [{
            "suggested_domain": "processes",
            "suggested_title": "Data Pipeline Resilience",
            "score": 60,
            "reasons": [
                "operational failure and remediation signals appear together",
                "source describes pipeline isolation, monitoring, validation, retry, or backfill work",
                f"no direct existing-page evidence for {source_id}",
            ],
        }]
    return []


def title_is_people_only(title: str, entity_matches: dict[str, list[str]]) -> bool:
    """Detect a 1:1-style meeting title that has no topical routing signal."""
    title_terms = lexical_tokens(title)
    entity_terms = {
        term
        for reasons in entity_matches.values()
        for reason in reasons
        for term in lexical_tokens(reason.split(": ", 1)[-1])
    }
    return bool(title_terms) and title_terms <= entity_terms


def discovery_query(content: str, title: str, entity_matches: dict[str, list[str]]) -> str:
    """Build a compact, reproducible QMD query from title and salient source terms."""
    title_terms = ordered_lexical_tokens(title)
    body = re.sub(r"\A---.*?---\s*", "", content, flags=re.DOTALL)
    body_terms = [term for term in ordered_lexical_tokens(body) if term not in GENERIC_ROUTING_TERMS and term not in STOPWORDS]
    counts = Counter(body_terms)
    frequent = [term for term, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]]
    heading_terms: list[str] = []
    for heading in re.findall(r"^#{1,3}\s+(.+?)\s*$", body, re.MULTILINE):
        # A colon conventionally separates a generic heading label from its
        # subject (for example, "The missing layer: memory lifecycle").
        # Preserve that subject. For a short standalone heading, retain its
        # first and last meaningful terms ("Search ... scales").
        subject = heading.split(":", 1)[-1] if ":" in heading else heading
        terms = [term for term in ordered_lexical_tokens(subject) if term not in (GENERIC_ROUTING_TERMS - {"knowledge"}) and term not in STOPWORDS]
        if ":" in heading:
            heading_terms.extend(terms)
        elif "search" in terms:
            heading_terms.extend(["search", terms[-1]])
    entity_terms = [reason.split(": ", 1)[-1] for reasons in entity_matches.values() for reason in reasons]
    entity_name_terms = {
        term
        for entity_name in entity_terms
        for term in ordered_lexical_tokens(entity_name)
    }
    # Aggregate activity sources often have a date as their only heading. Keep
    # named concepts from prose near the front of the query so a specific tool
    # such as "Codex" is not crowded out by generic activity wording or the
    # names of conversational participants.
    prose = "\n".join(
        line for line in body.splitlines()
        if not re.match(r"^\s*#{1,3}\s+", line)
    )
    named_terms = [
        match.group(0).lower()
        for match in re.finditer(r"\b(?:[A-Z][A-Za-z0-9-]{2,}|[A-Z]{2,})\b", prose)
        if match.group(0).lower() not in entity_name_terms
        and match.group(0).lower() not in GENERIC_ROUTING_TERMS
    ]
    # QMD receives its first twelve terms as the actual CLI query. Put the
    # source's concepts before a potentially long, prose-like title so that a
    # title such as "...with lessons from building..." cannot crowd out the
    # concepts that distinguish the appropriate wiki page.
    terms = list(dict.fromkeys(named_terms + title_terms[:2] + heading_terms + frequent + title_terms[2:] + entity_terms))
    return " ".join(terms[:16])


TOPIC_SECTION_IGNORE = frozenset({
    "summary", "full notes", "messages sent", "mentions", "channel-wide pings",
    "staff channel", "company announcements", "team check-in and updates",
})
STRUCTURAL_HEADING_TERMS = frozenset({"lesson", "lessons", "part", "chapter", "section", "step", "steps"})


def meaningful_heading(heading: str) -> bool:
    """Return whether an authored heading can safely act as a retrieval topic.

    Long reference clippings often use numbered structural labels (for example,
    ``LESSON 42``).  Those labels do not constrain a semantic query and must
    never cause the resolver to sample an arbitrary prefix of a book.
    """
    return len(lexical_tokens(heading) - STRUCTURAL_HEADING_TERMS - GENERIC_ROUTING_TERMS) >= 2


def clipping_topic_units(content: str) -> list[tuple[str, str, str, bool]]:
    """Return up to six authored topic packets for a long personal clipping.

    Prefer level-two headings, which preserve the article's main teaching
    structure. If a source uses generic level-two labels, supplement those
    packets with descriptive level-three headings rather than treating labels
    such as ``Lesson 42`` as semantic topics.  The source itself remains
    unchanged; these are ephemeral retrieval units only.
    """
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", content, re.MULTILINE))
    units: list[tuple[str, str, str, bool]] = []
    seen_spans: set[tuple[int, int]] = set()

    def add_units(matches: list[re.Match[str]]) -> None:
        for index, match in enumerate(matches):
            heading = match.group(1).strip()
            if not meaningful_heading(heading):
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            span = (match.start(), end)
            if span in seen_spans:
                continue
            section = content[match.start():end].strip()
            if len(lexical_tokens(section)) < 4:
                continue
            units.append((section, heading, heading, True))
            seen_spans.add(span)
            if len(units) == 6:
                return

    add_units(headings)
    if len(units) < 6:
        add_units(list(re.finditer(r"^###\s+(.+?)\s*$", content, re.MULTILINE)))
    return units


def discovery_units(content: str, title: str, entity_matches: dict[str, list[str]], source_id: str, source_scope: str | None) -> list[tuple[str, str, str, bool]]:
    """Build bounded topic-level discovery units for large meetings and Slack deltas.

    A whole sprint-planning note is a portfolio of unrelated work. QMD receives
    each substantive level-three section separately so one dominant topic does
    not hide Signal, migration, or reliability evidence in the same source.
    """
    use_topic_sections = source_id.startswith("Data/Meetings/") or source_scope is not None
    # A long saved personal guide can contain several independent skills. Use
    # its authored teaching headings, but only for Interests-limited clipping
    # discovery. Work reference libraries retain their review-only whole-file
    # policy until there is a separately validated need to split them.
    if source_id.startswith("Data/Knowledge/") and is_clipping_reference(content) and len(content) >= 12_000 and source_scope is None:
        units = clipping_topic_units(content)
        return units or [(content, title, "whole source", False)]
    if not use_topic_sections:
        return [(content, title, "whole source", False)]
    matches = list(re.finditer(r"^###\s+(.+?)\s*$", content, re.MULTILINE))
    units: list[tuple[str, str, str, bool]] = []
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        if heading.lower() in TOPIC_SECTION_IGNORE:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section = content[match.start():end].strip()
        # Brief operational headings such as "SA360 contingency" and
        # "AI Channel" often carry a decisive update in one sentence.
        # Generic channel headings are filtered above, so retain short
        # substantive sections rather than losing their only routing signal.
        if len(lexical_tokens(section)) < 4:
            continue
        units.append((section, heading, heading, True))
        if len(units) == 6:
            break
    return units or [(content, title, "whole source", False)]


def default_page_content(page: str) -> str | None:
    path = (VAULT_ROOT / page).resolve()
    wiki_root = (VAULT_ROOT / "Level Knowledge").resolve()
    if not path.is_relative_to(wiki_root) or not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="ignore")[:8000]


def candidate_match_strength(source_text: str, source_title_value: str, page: str, page_content: str | None) -> str:
    """Classify a QMD hit as strong, weak-review, or unsupported."""
    path_terms = lexical_tokens(Path(page).stem.replace("-", " "))
    title_terms = lexical_tokens(source_title_value)
    shared_path = title_terms & path_terms
    acronym_terms = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{1,}", source_text[:4000])
        if token.isupper()
    }
    # A single filename/title token (for example, a person's first name) is
    # not enough to establish impact. It caused unrelated team pages to pass
    # validation for a source merely titled with that person's name.
    if len(shared_path) >= 2 or shared_path & acronym_terms:
        return "strong"
    if page_content is None:
        return "weak-review"
    source_terms = lexical_tokens(source_title_value + " " + source_text[:4000]) - GENERIC_ROUTING_TERMS
    page_terms = lexical_tokens(page_content)
    title_terms = ordered_lexical_tokens(source_title_value)
    title_anchor = next((term for term in title_terms if term not in STOPWORDS and term not in GENERIC_ROUTING_TERMS), None)
    # A distinctive leading title term is normally the subject of a reference.
    # If it is missing from a candidate page, generic overlap such as "vector
    # search" must not turn a Qdrant reference into an automatic QMD update.
    if title_anchor and len(title_anchor) >= 4 and title_anchor not in page_terms:
        return "weak-review"
    if title_anchor and title_terms.count(title_anchor) >= 2 and title_anchor not in path_terms:
        return "weak-review"
    shared_content = source_terms & page_terms
    if len(shared_content) >= 2 or shared_content & acronym_terms:
        return "strong"
    if shared_content:
        return "weak-review"
    return "unsupported"


def resolve_source(source: Path, source_id: str, graph: dict[str, Any], registry: dict[str, Any], use_qmd: bool, qmd_limit: int, qmd_min_score: float, budget: int, neighbor_degree_cap: int, qmd_provider: QmdProvider | None = None, page_content_provider: PageContentProvider | None = None, content_override: str | None = None, use_direct_evidence: bool = True, source_scope: str | None = None) -> dict[str, Any]:
    content = content_override if content_override is not None else source.read_text(encoding="utf-8", errors="ignore")
    source_hash = file_hash(source)
    candidates: dict[str, dict[str, Any]] = {}
    policy_queue: dict[str, dict[str, Any]] = {}
    # This is broader than the selected review set. A page returned by the
    # scoped QMD search is enough to require a scope comparison before any new
    # taxonomy is proposed, even when it is not safe to update automatically.
    scope_matches: set[str] = set()
    edges_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    entity_pages: dict[str, list[str]] = {entity["id"]: entity["wiki_pages"] for entity in registry["entities"]}
    entity_kinds: dict[str, str] = {entity["id"]: entity.get("kind", "") for entity in registry["entities"]}
    entity_names: dict[str, str] = {entity["id"]: entity.get("canonical_name", "") for entity in registry["entities"]}
    explicit_entity_matches = matched_entities(content, normalized_entity_terms(registry))
    explicitly_named_client_pages = {
        page
        for entity_id in explicit_entity_matches
        if entity_kinds.get(entity_id) == "client"
        for page in entity_pages.get(entity_id, [])
    }
    person_pages = {
        page
        for entity_id, pages in entity_pages.items()
        if entity_kinds.get(entity_id) == "person"
        for page in pages
    }
    wiki_nodes = {node["id"] for node in graph["nodes"] if node["kind"] == "wiki_page"}

    for edge in graph["edges"]:
        edges_by_target[edge["to"]].append(edge)

    source_class = source_routing_class(source_id, content)
    direct_pages: set[str] = set()
    if use_direct_evidence:
        for edge in edges_by_target[source_id]:
            if edge["type"] == "references" and edge["from"] in wiki_nodes:
                if source_class == "agent-transcript":
                    add_candidate(policy_queue, edge["from"], 100, "direct graph evidence: agent transcript requires independent corroboration before an update")
                else:
                    add_candidate(candidates, edge["from"], 100, "direct graph evidence: page references this source")
                direct_pages.add(edge["from"])
                scope_matches.add(edge["from"])

    knowledge_reference = source_id.startswith("Data/Knowledge/")
    clipping_reference = source_class == "personal-clipping"
    entity_matches = {} if knowledge_reference or source_class in {"daily-note", "agent-transcript", "reference-library"} else matched_entities(content, normalized_entity_terms(registry))
    ambiguous_entity_matches = {} if knowledge_reference or source_class in {"daily-note", "agent-transcript", "reference-library"} else matched_entities(content, ambiguous_alias_terms(registry))
    entity_pages_selected: set[str] = set()
    for entity_id, match_reasons in entity_matches.items():
        if entity_kinds.get(entity_id) == "client" and not client_is_central(content, match_reasons):
            continue
        pages = primary_entity_pages(entity_id, entity_kinds.get(entity_id, ""), entity_pages.get(entity_id, []))
        for page in pages:
            reason = f"entity match ({entity_id}): " + "; ".join(match_reasons)
            if entity_kinds.get(entity_id) == "person":
                if person_requires_review(content, entity_names.get(entity_id, "")):
                    add_candidate(policy_queue, page, 70, reason + "; onboarding, role-change, or ownership context requires review")
            else:
                add_candidate(candidates, page, 80, reason)
                entity_pages_selected.add(page)
                scope_matches.add(page)
    for entity_id, match_reasons in ambiguous_entity_matches.items():
        for page in entity_pages.get(entity_id, []):
            add_candidate(policy_queue, page, 70, f"ambiguous entity match ({entity_id}): " + "; ".join(match_reasons) + "; queued for review")

    # One-hop expansion originates only from direct evidence. It is intentionally
    # disabled: direct source references are sufficient and safer than widening
    # the review set through structural proximity.
    skipped_hubs: list[str] = []

    qmd_error = None
    content_provider = page_content_provider or default_page_content
    qmd_discovery_allowed = source_class not in {"daily-note"}
    retrieval_units: list[dict[str, Any]] = []
    if use_qmd and qmd_discovery_allowed and not direct_pages:
        source_title_value = source_title(content)
        provider = qmd_provider or qmd_candidates
        for unit_content, unit_title, unit_label, topic_scoped in discovery_units(content, source_title_value, entity_matches, source_id, source_scope):
            query = discovery_query(unit_content, unit_title, entity_matches) or unit_content
            # `discovery_query` normally avoids generic headings. A focused
            # section heading is different: it is the explicit topic label
            # selected by the source author, so keep it at the front.
            if topic_scoped:
                query = unit_title + " " + query
            retrieval_units.append({
                "label": unit_label,
                "heading": unit_title,
                "characters": len(unit_content),
                "topic_scoped": topic_scoped,
                "query": query,
            })
            qmd_hits, unit_error = provider(query, qmd_limit)
            qmd_error = qmd_error or unit_error
            # Providers normally honor `limit`, but retain the boundary locally
            # so a malformed or replacement provider cannot widen one topic's
            # review set.
            for page, qmd_score in qmd_hits[:qmd_limit]:
                if not (
                    page in wiki_nodes
                    and page not in NON_ROUTABLE_WIKI_PAGES
                    and qmd_score >= qmd_min_score
                    and (not clipping_reference or page.startswith(INTERESTS_PREFIX))
                ):
                    continue
                scope_matches.add(page)
                # A dated section in an aggregate capture must name the
                # client before a semantic hit may even enter that client's
                # queue. This prevents a generic mention (for example, Meta
                # pacing) from becoming an AMF issue merely by proximity.
                if source_scope is not None and source_scope != "whole source" and page.startswith("Level Knowledge/clients/") and page not in explicitly_named_client_pages:
                    continue
                score = 25 + round(min(qmd_score, 1.0) * 20)
                topic_reason = f"; topic segment: {unit_label}" if topic_scoped else ""
                topic_path_overlap = len(
                    lexical_tokens(unit_title) & lexical_tokens(Path(page).stem.replace("-", " "))
                ) >= 2
                if page in person_pages:
                    person_entity = next((entity_id for entity_id, pages in entity_pages.items() if page in pages and entity_kinds.get(entity_id) == "person"), "")
                    if person_requires_review(content, entity_names.get(person_entity, "")):
                        add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}; team profile has onboarding, role-change, or ownership context and requires review")
                    continue
                if knowledge_reference and page.startswith("Level Knowledge/team/"):
                    add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}; external reference cannot automatically update a team profile")
                    continue
                strength = "strong" if page in entity_pages_selected else candidate_match_strength(unit_content, unit_title, page, content_provider(page))
                # A section extracted from an aggregate source has no
                # independent References block. QMD can surface useful
                # candidates, but a single semantic hit is discovery evidence
                # only; queue it for a bounded human/agent review instead of
                # treating it as an automatic page update.
                if source_class in {"agent-transcript", "reference-library"}:
                    if strength != "unsupported":
                        add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}; {discovery_policy(source_class)}")
                elif source_id.startswith("Data/Meetings/") and not topic_scoped:
                    if strength != "unsupported":
                        add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}; whole-meeting discovery requires evidence review")
                elif source_scope is not None and source_scope != "whole source":
                    if strength != "unsupported":
                        add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}; scoped aggregate delta requires review")
                elif topic_scoped and not topic_path_overlap:
                    if strength != "unsupported":
                        add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}; semantic topic hit lacks page-title overlap and requires evidence review")
                elif strength == "strong":
                    add_candidate(candidates, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}")
                elif strength == "weak-review":
                    add_candidate(policy_queue, page, score, f"qmd hybrid discovery score {qmd_score:.3f}{topic_reason}; queued because source title and page path have no meaningful lexical overlap")

    # Section headings are authored, explicit topic labels. A cheap two-term
    # path match recovers known pages even when QMD's top-k omits one section;
    # it remains bounded to the existing wiki-node set and does not scan prose.
    if not direct_pages and source_class == "standard":
        for unit_content, unit_title, unit_label, topic_scoped in discovery_units(content, source_title(content), entity_matches, source_id, source_scope):
            if not topic_scoped:
                continue
            heading_terms = lexical_tokens(unit_title)
            for page in wiki_nodes:
                if page in NON_ROUTABLE_WIKI_PAGES or len(heading_terms & lexical_tokens(Path(page).stem.replace("-", " "))) < 2:
                    continue
                reason = "topic-heading lexical fallback: " + ", ".join(sorted(heading_terms & lexical_tokens(Path(page).stem.replace("-", " "))))
                if source_scope is not None and source_scope != "whole source":
                    add_candidate(policy_queue, page, 42, reason + "; scoped aggregate delta requires review")
                else:
                    add_candidate(candidates, page, 42, reason)

    # QMD can occasionally miss a narrow existing Interest page. Keep the
    # fallback within Interests and require overlap with the page's own topic
    # name; generic prose overlap is not a category classifier.
    if clipping_reference and not direct_pages:
        source_terms = lexical_tokens(source_title(content) + " " + content[:4000]) - GENERIC_ROUTING_TERMS
        for page in sorted(page for page in wiki_nodes if page.startswith(INTERESTS_PREFIX)):
            page_content = content_provider(page)
            shared = source_terms & lexical_tokens(page_content or "")
            path_overlap = source_terms & lexical_tokens(Path(page).stem.replace("-", " "))
            if len(shared) >= 2 and path_overlap:
                add_candidate(policy_queue, page, 40, "interests lexical fallback: shared " + ", ".join(sorted(shared)[:3]) + "; requires evidence review")

    ranked = sorted(candidates.values(), key=lambda entry: (-entry["score"], entry["page"]))
    queued = ranked[budget:]
    selected_pages = {entry["page"] for entry in ranked[:budget]}
    for candidate in sorted(policy_queue.values(), key=lambda entry: (-entry["score"], entry["page"])):
        if candidate["page"] not in selected_pages and candidate["page"] not in {entry["page"] for entry in queued}:
            queued.append(candidate)
    new_topic_review = topic_discovery_cues(content, source_id, source_class, direct_pages, source_scope, scope_matches, qmd_error)
    return {
        "source": source_id,
        "source_scope": source_scope or "whole source",
        "source_class": source_class,
        "discovery_policy": discovery_policy(source_class),
        "direct_evidence": "enabled" if use_direct_evidence else "suppressed for scoped source delta",
        "sha256": source_hash,
        "entity_matches": entity_matches,
        "ambiguous_entity_matches": ambiguous_entity_matches,
        "entity_matching": (
            "skipped for personal/web clipping; discovery is limited to the Interests domain"
            if clipping_reference
            else "skipped for Data/Knowledge reference source"
            if knowledge_reference
            else "enabled"
        ),
        "skipped_hubs": sorted(skipped_hubs),
        "scope_matches": sorted(scope_matches),
        "qmd_error": qmd_error,
        "retrieval_units": retrieval_units,
        "selected": ranked[:budget],
        "queued": queued,
        "new_topic_review": new_topic_review,
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Impact Resolver Review", "", f"Generated: {report['generated_at']}", "", f"Review budget per source: {report['budget']}", ""]
    for result in report["sources"]:
        lines.extend([f"## {result['source']}", "", f"- Scope: {result['source_scope']}", f"- Source class: {result['source_class']}", f"- Discovery policy: {result['discovery_policy']}", f"- Direct evidence: {result['direct_evidence']}", f"- SHA-256: `{result['sha256']}`", f"- Entity matching: {result['entity_matching']}", f"- Existing-page scope matches: {len(result['scope_matches'])}", f"- Confirmed entity matches: {len(result['entity_matches'])}", f"- Ambiguous entity matches: {len(result['ambiguous_entity_matches'])}", f"- Selected pages: {len(result['selected'])}", f"- Queued pages: {len(result['queued'])}", f"- High-degree pages not expanded: {len(result['skipped_hubs'])}"])
        if result["qmd_error"]:
            lines.append(f"- QMD: unavailable ({result['qmd_error']})")
        lines.extend(["", "### Selected review set", ""])
        lines.extend([f"- **{candidate['score']}** — `{candidate['page']}`  \n  {'; '.join(candidate['reasons'])}" for candidate in result["selected"]] or ["- No candidates."])
        if result["queued"]:
            lines.extend(["", "### Queue", ""])
            lines.extend([f"- **{candidate['score']}** — `{candidate['page']}`" for candidate in result["queued"]])
        if result.get("retrieval_units"):
            lines.extend(["", "### Retrieval packets", ""])
            lines.extend(
                f"- `{unit['label']}` ({unit['characters']} characters; {'section' if unit['topic_scoped'] else 'whole source'})"
                for unit in result["retrieval_units"]
            )
        if result["new_topic_review"]:
            lines.extend(["", "### Taxonomy review cues", ""])
            lines.extend(
                f"- `{cue['suggested_domain']}/{cue['suggested_title']}` — {cue['independence_status']}; {'; '.join(cue['reasons'])}"
                for cue in result["new_topic_review"]
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Produce an explainable page-review set for changed Data sources.")
    parser.add_argument("--source", action="append", required=True, help="Vault-relative path to an explicit changed Data/ file. Repeat for multiple sources.")
    parser.add_argument("--budget", type=int, default=10, help="Maximum selected pages per source.")
    parser.add_argument("--qmd-limit", type=int, default=5, help="Maximum QMD discovery results per source.")
    parser.add_argument("--qmd-min-score", type=float, default=0.5, help="Minimum QMD score for a discovery-only candidate after content validation.")
    parser.add_argument("--neighbor-degree-cap", type=int, default=12, help="Do not expand one-hop neighbors from pages with more links than this.")
    parser.add_argument("--no-qmd", action="store_true", help="Disable QMD discovery; retain graph/entity routing only.")
    parser.add_argument("--registry", type=Path, default=METADATA_ROOT / "state" / "entity-registry.json")
    parser.add_argument("--graph", type=Path, default=METADATA_ROOT / "state" / "dependency-graph.json")
    parser.add_argument("--output", type=Path, default=METADATA_ROOT / "reports" / "current" / "impact-review.json")
    parser.add_argument("--report", type=Path, default=METADATA_ROOT / "reports" / "current" / "impact-review.md")
    args = parser.parse_args()
    if args.budget < 1 or args.qmd_limit < 0 or args.neighbor_degree_cap < 0 or not 0 <= args.qmd_min_score <= 1:
        parser.error("--budget must be at least 1 and limits cannot be negative")
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    results = []
    for raw_source in args.source:
        source, source_id = source_path(raw_source)
        results.append(resolve_source(source, source_id, graph, registry, not args.no_qmd, args.qmd_limit, args.qmd_min_score, args.budget, args.neighbor_degree_cap))
    report = {"version": 1, "generated_at": date.today().isoformat(), "budget": args.budget, "sources": results}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(markdown_report(report), encoding="utf-8")
    print(f"Wrote impact review for {len(results)} source(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
