from __future__ import annotations


def update_probability(prior: float, likelihood_if_type: float, likelihood_if_not_type: float) -> float:
    numerator = likelihood_if_type * prior
    denominator = numerator + likelihood_if_not_type * (1.0 - prior)
    if denominator <= 0:
        return prior
    return numerator / denominator

