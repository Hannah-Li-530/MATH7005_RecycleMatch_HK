"""Apriori frequent-itemset mining for recycling-material combinations.

Implements the classic Apriori algorithm by hand (candidate generation,
downward-closure pruning, support counting) rather than delegating to a
library, so every step can be explained in the live demonstration.

A "transaction" is one recycling point and its items are the material
categories that point accepts (split from ``waste_type``). A frequent
itemset is a set of materials that many points accept together, which is
useful product knowledge: e.g. "points that take Paper almost always take
Metals too", so the recommendation engine can suggest sensible next stops.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Iterable

Transaction = frozenset[str]


def load_transactions(
    waste_type_series: Iterable[str], sep: str = ","
) -> list[Transaction]:
    """Convert a series of comma-separated waste_type strings to transactions.

    Items are lower-cased and stripped; empty strings and blank items are
    dropped so they never pollute the itemset lattice.
    """
    transactions: list[Transaction] = []
    for raw in waste_type_series:
        items = {part.strip().lower() for part in str(raw).split(sep) if part.strip()}
        if items:
            transactions.append(frozenset(items))
    return transactions


def _candidate_gen(freq_prev: set[Transaction]) -> set[Transaction]:
    """Generate candidate k-itemsets from frequent (k-1)-itemsets (join step).

    Two itemsets of size k-1 join into a k-itemset when they share the same
    first k-2 items (canonical sorted order). Using the sorted-tuple
    representation avoids generating duplicate candidates.
    """
    prev_tuples = sorted(frozenset(x) for x in freq_prev)
    candidates: set[Transaction] = set()
    n = len(prev_tuples)
    for i in range(n):
        a = prev_tuples[i]
        a_sorted = sorted(a)
        for j in range(i + 1, n):
            b = prev_tuples[j]
            b_sorted = sorted(b)
            if a_sorted[:-1] == b_sorted[:-1]:
                candidates.add(frozenset(a | b))
    return candidates


def _has_infrequent_subset(cand: Transaction, freq_prev: set[Transaction]) -> bool:
    """Downward-closure (anti-monotonicity) pruning.

    If any (k-1)-subset of the candidate is not frequent, the candidate cannot
    be frequent either, so it is discarded before counting.
    """
    return any(
        frozenset(subset) not in freq_prev
        for subset in combinations(cand, len(cand) - 1)
    )


def _count_support(
    candidates: set[Transaction], transactions: list[Transaction]
) -> dict[Transaction, int]:
    """Count absolute support of every candidate over the transaction list."""
    counts: Counter = Counter()
    for transaction in transactions:
        for cand in candidates:
            if cand.issubset(transaction):
                counts[cand] += 1
    return dict(counts)


def apriori(
    transactions: list[Transaction],
    min_support: float,
    min_confidence: float = 0.0,
) -> tuple[dict[Transaction, float], list[dict[str, float | Transaction]]]:
    """Mine frequent itemsets and association rules with the Apriori algorithm.

    Parameters
    ----------
    transactions : list[Transaction]
        List of frozensets of material names (see :func:`load_transactions`).
    min_support : float
        Minimum relative support in [0, 1]; itemsets below this are pruned.
    min_confidence : float, optional
        Minimum confidence in [0, 1] for association rules; default 0 means
        every rule derivable from frequent itemsets is returned.

    Returns
    -------
    (frequent, rules)
        frequent : dict[Transaction, float]
            Mapping itemset -> relative support, keyed by frozenset.
        rules : list[dict]
            Each dict has keys "antecedent", "consequent", "support",
            "confidence", "lift".
    """
    n = len(transactions)
    if n == 0:
        return {}, []

    item_counts = Counter(item for t in transactions for item in t)
    frequent: dict[Transaction, float] = {
        frozenset([item]): count / n
        for item, count in item_counts.items()
        if count / n >= min_support
    }

    level: set[Transaction] = set(frequent.keys())
    while level:
        candidates = _candidate_gen(level)
        # Downward-closure pruning keeps only candidates whose subsets are all
        # frequent, then counting decides the rest.
        candidates = {
            c for c in candidates if not _has_infrequent_subset(c, level)
        }
        if not candidates:
            break
        counts = _count_support(candidates, transactions)
        level = {c for c, count in counts.items() if count / n >= min_support}
        for itemset in level:
            frequent[itemset] = counts[itemset] / n

    rules: list[dict[str, float | Transaction]] = []
    if min_confidence > 0:
        for itemset, support in frequent.items():
            if len(itemset) < 2:
                continue
            for removed in itemset:
                antecedent = frozenset(itemset - {removed})
                antecedent_support = frequent[antecedent]
                confidence = support / antecedent_support
                if confidence >= min_confidence:
                    lift = confidence / (frequent[frozenset([removed])])
                    rules.append(
                        {
                            "antecedent": antecedent,
                            "consequent": frozenset([removed]),
                            "support": support,
                            "confidence": confidence,
                            "lift": lift,
                        }
                    )
    return frequent, rules
