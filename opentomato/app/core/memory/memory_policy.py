from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Pattern


@dataclass(frozen=True)
class CaptureDecision:
    enabled: bool
    reason: str = ""
    text: str = ""
    category: str = "profile"


@dataclass(frozen=True)
class CaptureRule:
    pattern: Pattern[str]
    category: str
    formatter: Callable[[re.Match[str]], str]


def _split_env_list(name: str, defaults: Iterable[str]) -> List[str]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return [str(item).strip() for item in defaults if str(item).strip()]
    values = [item.strip() for item in raw.split("||") if item.strip()]
    return values or [str(item).strip() for item in defaults if str(item).strip()]


class MemoryPolicy:
    """System policy used by memory plugin. Recall is unconditional in plugin; policy only handles capture."""

    _DEFAULT_NAME_PATTERNS = (
        r"^\s*我是(?P<value>.+?)\s*$",
        r"^\s*我叫(?P<value>.+?)\s*$",
        r"^\s*my name is (?P<value>.+?)\s*$",
        r"^\s*i am (?P<value>.+?)\s*$",
    )
    _DEFAULT_LOCATION_PATTERNS = (
        r"^\s*我家在(?P<value>.+?)\s*$",
        r"^\s*i live in (?P<value>.+?)\s*$",
    )
    _DEFAULT_HOUSEHOLD_PATTERNS = (
        r"^\s*我家有(?P<count>[零一二两三四五六七八九十百千0-9]+)个人\s*$",
        r"^\s*there are (?P<count>[0-9]+) people in my family\s*$",
    )
    _DEFAULT_ASSET_PATTERNS = (
        r"^\s*我的设备是(?P<value>.+?)\s*$",
        r"^\s*my device is (?P<value>.+?)\s*$",
        r"^\s*my devices are (?P<value>.+?)\s*$",
    )
    _DEFAULT_EXPLICIT_CAPTURE_KEYWORDS = (
        "记一下",
        "记住这个",
        "帮我记住",
        "remember this",
        "save this",
    )

    def __init__(self) -> None:
        self.explicit_capture_keywords = [
            item.lower()
            for item in _split_env_list(
                "MEMORY_POLICY_EXPLICIT_CAPTURE_KEYWORDS",
                self._DEFAULT_EXPLICIT_CAPTURE_KEYWORDS,
            )
        ]
        self.capture_rules = self._build_capture_rules()

    def _build_capture_rules(self) -> List[CaptureRule]:
        def clean(value: str) -> str:
            return str(value or "").strip("。?!！？,，")

        return [
            *[
                CaptureRule(
                    pattern=re.compile(pattern, re.I),
                    category="identity",
                    formatter=lambda m: f"用户常用姓名是 {clean(m.group('value'))}",
                )
                for pattern in _split_env_list("MEMORY_POLICY_CAPTURE_NAME_PATTERNS", self._DEFAULT_NAME_PATTERNS)
            ],
            *[
                CaptureRule(
                    pattern=re.compile(pattern, re.I),
                    category="household",
                    formatter=lambda m: f"用户家庭所在地是 {clean(m.group('value'))}",
                )
                for pattern in _split_env_list("MEMORY_POLICY_CAPTURE_LOCATION_PATTERNS", self._DEFAULT_LOCATION_PATTERNS)
            ],
            *[
                CaptureRule(
                    pattern=re.compile(pattern, re.I),
                    category="household",
                    formatter=lambda m: f"用户家庭人数是 {clean(m.group('count'))} 人",
                )
                for pattern in _split_env_list("MEMORY_POLICY_CAPTURE_HOUSEHOLD_PATTERNS", self._DEFAULT_HOUSEHOLD_PATTERNS)
            ],
            *[
                CaptureRule(
                    pattern=re.compile(pattern, re.I),
                    category="asset",
                    formatter=lambda m: f"用户设备信息是：{clean(m.group('value'))}",
                )
                for pattern in _split_env_list("MEMORY_POLICY_CAPTURE_ASSET_PATTERNS", self._DEFAULT_ASSET_PATTERNS)
            ],
        ]

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join((text or "").strip().split())

    def should_auto_capture(self, query: str) -> CaptureDecision:
        normalized_query = self._normalize(query)
        if not normalized_query:
            return CaptureDecision(enabled=False)

        for rule in self.capture_rules:
            match = rule.pattern.search(normalized_query)
            if not match:
                continue
            text = self._normalize(rule.formatter(match))
            if text:
                return CaptureDecision(
                    enabled=True,
                    reason=f"{rule.category}_fact",
                    text=text,
                    category=rule.category,
                )

        lowered = normalized_query.lower()
        if any(token in lowered for token in self.explicit_capture_keywords):
            return CaptureDecision(
                enabled=True,
                reason="explicit_capture_request",
                text=normalized_query,
                category="profile",
            )

        return CaptureDecision(enabled=False)


PREFERENCE_QUERY_RE = re.compile(r"(偏好|喜欢|爱好|更倾向|preference|prefer|favorite|like)", re.I)
TEMPORAL_QUERY_RE = re.compile(
    r"(昨天|今天|明天|前几天|上周|下周|上个月|下个月|去年|明年|什么时候|何时|yesterday|today|tomorrow|last|next|when)",
    re.I,
)
QUERY_TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.I)
QUERY_TOKEN_STOPWORDS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "did",
    "does",
    "is",
    "are",
    "was",
    "were",
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "you",
}


def clamp_score(value: Any) -> float:
    if not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _normalize_dedupe_text(text: str) -> str:
    return _normalize_text(text)


def _is_event_like(item: Dict[str, Any]) -> bool:
    category = str(item.get("category", "") or "").lower()
    uri = str(item.get("uri", "") or "").lower()
    return category == "events" or "/events/" in uri or category == "cases" or "/cases/" in uri


def _is_preference_like(item: Dict[str, Any]) -> bool:
    category = str(item.get("category", "") or "").lower()
    uri = str(item.get("uri", "") or "").lower()
    return category == "preferences" or "/preferences/" in uri


def _is_leaf_like(item: Dict[str, Any]) -> bool:
    level = item.get("level")
    uri = str(item.get("uri", "") or "")
    return level == 2 or uri.endswith(".md")


def _dedupe_key(item: Dict[str, Any]) -> str:
    abstract = _normalize_dedupe_text(str(item.get("abstract", "") or item.get("overview", "") or ""))
    category = str(item.get("category", "") or "unknown").lower()
    if abstract and not _is_event_like(item):
        return f"abstract:{category}:{abstract}"
    return f"uri:{str(item.get('uri', '') or '').lower()}"


def post_process_memories(
    items: List[Dict[str, Any]],
    *,
    limit: int,
    score_threshold: float,
    leaf_only: bool = False,
) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    sorted_items = sorted(items, key=lambda item: clamp_score(item.get("score")), reverse=True)
    for item in sorted_items:
        if leaf_only and not _is_leaf_like(item):
            continue
        if clamp_score(item.get("score")) < score_threshold:
            continue
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def _build_query_profile(query_text: str) -> Dict[str, Any]:
    text = (query_text or "").strip()
    tokens = [
        token.lower()
        for token in (QUERY_TOKEN_RE.findall(text) or [])
        if token.lower() not in QUERY_TOKEN_STOPWORDS
    ]
    return {
        "tokens": tokens,
        "wants_preference": bool(PREFERENCE_QUERY_RE.search(text)),
        "wants_temporal": bool(TEMPORAL_QUERY_RE.search(text)),
    }


def _lexical_overlap_boost(tokens: List[str], text: str) -> float:
    haystack = _normalize_text(text)
    if not tokens or not haystack:
        return 0.0
    matched = 0
    for token in tokens[:8]:
        if token in haystack:
            matched += 1
    return min(0.2, (matched / max(1, min(len(tokens), 4))) * 0.2)


def _rank_for_injection(item: Dict[str, Any], query_profile: Dict[str, Any]) -> float:
    base_score = clamp_score(item.get("score"))
    abstract = str(item.get("abstract", "") or item.get("overview", "") or "")
    leaf_boost = 0.12 if _is_leaf_like(item) else 0.0
    event_boost = 0.1 if query_profile["wants_temporal"] and _is_event_like(item) else 0.0
    preference_boost = 0.08 if query_profile["wants_preference"] and _is_preference_like(item) else 0.0
    overlap_boost = _lexical_overlap_boost(query_profile["tokens"], f"{item.get('uri', '')} {abstract}")
    return base_score + leaf_boost + event_boost + preference_boost + overlap_boost


def pick_memories_for_injection(
    items: List[Dict[str, Any]],
    *,
    query_text: str,
    limit: int,
) -> List[Dict[str, Any]]:
    if not items or limit <= 0:
        return []

    query_profile = _build_query_profile(query_text)
    sorted_items = sorted(items, key=lambda item: _rank_for_injection(item, query_profile), reverse=True)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted_items:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    leaves = [item for item in deduped if _is_leaf_like(item)]
    if len(leaves) >= limit:
        return leaves[:limit]

    picked = list(leaves)
    used_uris = {str(item.get("uri", "")) for item in leaves}
    for item in deduped:
        if len(picked) >= limit:
            break
        uri = str(item.get("uri", ""))
        if uri in used_uris:
            continue
        picked.append(item)
    return picked


def format_injection_block(items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""
    lines = ["[RELEVANT MEMORIES]"]
    for index, item in enumerate(items, start=1):
        category = str(item.get("category", "") or "memory")
        abstract = str(item.get("abstract", "") or item.get("overview", "") or item.get("uri", "")).strip()
        score = clamp_score(item.get("score"))
        lines.append(f"{index}. [{category}] {abstract} ({score:.2f})")
    return "\n".join(lines)
