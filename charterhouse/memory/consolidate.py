"""S9 consolidation — the deterministic, REVERSIBLE view pass (INV-MEM-3, docs/33 §Consolidation).

One pass, in order, all without touching the ledger (view mutations only):
1. **Merge duplicates** — same ``kind``, cosine ≥ ``dup_threshold``; the
   highest-confidence member stays ``active`` (tie → smallest lesson_id), the rest are
   marked ``superseded``.
2. **Retire** — remaining active lessons with ``confidence < retire_below`` → ``retired``.
3. **Promote** — a tag spanning ≥ ``promote_min_ventures`` DISTINCT ventures across the
   remaining active lessons → exactly one new ``playbook`` row, assembled
   deterministically (sorted member texts under a canonical header, mean confidence,
   member-id source_ref). **No LLM** — LLM-assisted summarization is a later S11
   capability calling ``write_lesson``, never S9 logic. Idempotent: an existing active
   playbook for the tag suppresses re-promotion.
4. **Doctrine proposals** — returned in the report ONLY; the founder writes Doctrine.

Reversibility: the pre-pass lesson set remains reconstructible from the ledger's
``lesson_written`` history (tested); nothing here can edit or delete a ledger event —
no such API even exists on the store.

Determinism (docs/61 §INV-DET): pure planning over rows; stdlib only; no LLM, no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from charterhouse.memory.types import RetrievalWeights

__all__ = ["ConsolidationPlan", "plan"]


@dataclass(frozen=True)
class ConsolidationPlan:
    """The pure output of one planning pass; the facade applies it (status flips + new
    playbook rows) and appends the single ``consolidate`` event."""

    supersede: tuple[tuple[str, str], ...]  # (superseded_id, kept_id)
    retire: tuple[str, ...]
    playbooks: tuple[dict, ...]  # new rows, vector-less (facade embeds)
    doctrine_proposals: tuple[str, ...]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _duplicate_groups(active: list[dict], threshold: float) -> list[list[dict]]:
    """Greedy deterministic grouping (id order): same kind + cosine ≥ threshold."""
    groups: list[list[dict]] = []
    taken: set[str] = set()
    for row in active:  # rows arrive id-sorted (store.all_rows determinism)
        if row["id"] in taken:
            continue
        group = [row]
        taken.add(row["id"])
        for other in active:
            if other["id"] in taken or other["kind"] != row["kind"]:
                continue
            if _cosine(row["vector"], other["vector"]) >= threshold:
                group.append(other)
                taken.add(other["id"])
        groups.append(group)
    return groups


def plan(rows: list[dict], weights: RetrievalWeights) -> ConsolidationPlan:
    """Plan one consolidation pass over ``all_rows()``. Pure and deterministic —
    identical rows always yield the identical plan."""
    active = [r for r in rows if r["status"] == "active"]

    # 1. merge duplicates (highest confidence kept; tie → smallest id).
    supersede: list[tuple[str, str]] = []
    survivors: list[dict] = []
    for group in _duplicate_groups(active, weights.dup_threshold):
        # Deterministic keeper: highest confidence, ties broken by smallest id.
        kept = sorted(group, key=lambda r: (-float(r["confidence"]), r["id"]))[0]
        survivors.append(kept)
        supersede.extend((other["id"], kept["id"]) for other in group
                         if other["id"] != kept["id"])

    # 2. retire low-confidence survivors.
    retire = tuple(r["id"] for r in survivors
                   if float(r["confidence"]) < weights.retire_below)
    remaining = [r for r in survivors if r["id"] not in set(retire)]

    # 3. promote recurring tags (lessons only) to ONE playbook each — idempotent.
    existing_playbook_tags = {tag for r in rows
                              if r["kind"] == "playbook" and r["status"] == "active"
                              for tag in (r["tags"] or ())}
    by_tag: dict[str, list[dict]] = {}
    for r in remaining:
        if r["kind"] != "lesson":
            continue
        for tag in (r["tags"] or ()):
            by_tag.setdefault(tag, []).append(r)
    playbooks: list[dict] = []
    proposals: list[str] = []
    for tag in sorted(by_tag):
        members = by_tag[tag]
        ventures = {r["venture_id"] for r in members if r["venture_id"]}
        if len(ventures) < weights.promote_min_ventures:
            continue
        if tag in existing_playbook_tags:
            continue  # already promoted — a second pass is a no-op
        member_ids = sorted(r["id"] for r in members)
        texts = sorted(r["text"] for r in members)
        playbooks.append({
            "id": f"pb-{tag}",
            "kind": "playbook",
            "text": f"PLAYBOOK[{tag}] — distilled from {len(members)} recurring "
                    f"lessons:\n" + "\n".join(f"- {t}" for t in texts),
            "tags": [tag],
            "venture_id": None,
            "segment": None,
            "confidence": round(sum(float(r["confidence"]) for r in members)
                                / len(members), 4),
            "status": "active",
            "created_active_time": max(int(r["created_active_time"])
                                       for r in members),
            "source_ref": "lessons:" + "+".join(member_ids),
        })
        proposals.append(
            f"doctrine candidate: the '{tag}' playbook recurs across "
            f"{len(ventures)} ventures — founder review suggested")

    return ConsolidationPlan(
        supersede=tuple(sorted(supersede)),
        retire=retire,
        playbooks=tuple(playbooks),
        doctrine_proposals=tuple(proposals),
    )
