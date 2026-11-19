"""Property-based tests for kalshi_calibration/analysis/statistics.py.

test_statistics.py checks each estimator against a worked example. These check what must hold for *any*
input: an interval is ordered and stays inside [0, 1], a standard error is never negative and ignores how
clusters are labelled, Benjamini-Hochberg never makes a p-value smaller, and so on. Hypothesis generates the
inputs and shrinks any failure to the smallest one that breaks the rule.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from kalshi_calibration.analysis.statistics import (
    benjamini_hochberg,
    cluster_bootstrap_ci,
    cluster_bootstrap_ratio_ci,
    cluster_robust_se,
    clustered_mean_test,
    wilson_interval,
)

confidence = st.floats(0.5, 0.999)


@st.composite
def counts(draw):
    n = draw(st.integers(1, 5000))
    return draw(st.integers(0, n)), n


# ------------------------------------------------------------------ Wilson


@given(counts(), confidence)
def test_wilson_is_an_ordered_interval_inside_the_unit_interval(kn, conf):
    k, n = kn
    low, high = wilson_interval(k, n, conf)
    assert 0.0 <= low <= high <= 1.0


@given(counts(), confidence)
def test_wilson_contains_the_observed_proportion(kn, conf):
    k, n = kn
    low, high = wilson_interval(k, n, conf)
    assert low - 1e-12 <= k / n <= high + 1e-12


@given(counts(), confidence)
def test_wilson_is_symmetric_under_relabelling_success_and_failure(kn, conf):
    k, n = kn
    low, high = wilson_interval(k, n, conf)
    low2, high2 = wilson_interval(n - k, n, conf)
    assert low == pytest.approx(1 - high2, abs=1e-12) and high == pytest.approx(1 - low2, abs=1e-12)


@given(counts(), st.floats(0.5, 0.98))
def test_wilson_widens_with_confidence(kn, conf):
    k, n = kn
    narrow, wide = wilson_interval(k, n, conf), wilson_interval(k, n, conf + 0.01)
    assert wide[0] <= narrow[0] + 1e-12 and wide[1] >= narrow[1] - 1e-12


@given(st.integers(-5, 0) | st.integers(1, 10).map(lambda n: -n))
def test_wilson_refuses_an_empty_or_negative_sample(n):
    with pytest.raises(ValueError):
        wilson_interval(0, n)


# ------------------------------------------------------------------ clustered standard errors


@st.composite
def clustered_values(draw, min_size=1, max_size=60):
    n = draw(st.integers(min_size, max_size))
    values = draw(hnp.arrays(np.float64, n, elements=st.floats(-1e3, 1e3)))
    labels = draw(hnp.arrays(np.int64, n, elements=st.integers(0, max(1, n // 2))))
    return values, labels


@given(clustered_values())
def test_cluster_se_is_never_negative_and_counts_distinct_clusters(data):
    values, labels = data
    se, g = cluster_robust_se(values, labels)
    assert se >= 0.0 and g == len(np.unique(labels))
    if g == 1:
        assert se == 0.0


@given(clustered_values(), st.randoms(use_true_random=False))
def test_cluster_se_ignores_row_order_and_label_names(data, rnd):
    values, labels = data
    se, g = cluster_robust_se(values, labels)
    order = list(range(len(values)))
    rnd.shuffle(order)
    renamed = np.array([f"event-{int(x) * 7 + 3}" for x in labels])
    se2, g2 = cluster_robust_se(values[order], renamed[order])
    assert g2 == g and se2 == pytest.approx(se, rel=1e-9, abs=1e-12)


@given(clustered_values(), st.floats(-1e3, 1e3))
def test_cluster_se_is_unchanged_by_shifting_every_value(data, shift):
    values, labels = data
    assert cluster_robust_se(values + shift, labels)[0] == pytest.approx(
        cluster_robust_se(values, labels)[0], rel=1e-6, abs=1e-6)


@given(clustered_values(), st.floats(0.01, 100))
def test_cluster_se_scales_with_the_values(data, scale):
    values, labels = data
    assert cluster_robust_se(values * scale, labels)[0] == pytest.approx(
        scale * cluster_robust_se(values, labels)[0], rel=1e-6, abs=1e-9)


@given(hnp.arrays(np.float64, st.integers(2, 60), elements=st.floats(-100, 100)))
def test_singleton_clusters_reduce_to_the_independent_standard_error(values):
    n = len(values)
    se, g = cluster_robust_se(values, np.arange(n))
    naive = math.sqrt(np.sum((values - values.mean()) ** 2) / (n - 1)) / math.sqrt(n)
    assert g == n and se == pytest.approx(naive, rel=1e-9, abs=1e-12)


@given(clustered_values())
def test_clustered_mean_test_is_a_valid_test(data):
    values, labels = data
    t = clustered_mean_test(values, labels)
    assert t.mean == pytest.approx(float(np.mean(values)), rel=1e-12, abs=1e-12)
    assert 0.0 <= t.p_value <= 1.0
    assert t.n == len(values) and t.n_clusters == len(np.unique(labels))
    if t.se == 0:
        assert t.p_value == 1.0 and t.t_stat == 0.0


# ------------------------------------------------------------------ Benjamini-Hochberg

p_values = hnp.arrays(np.float64, st.integers(0, 40),
                      elements=st.floats(0.0, 1.0) | st.just(float("nan")))
alphas = st.floats(0.001, 0.5)


@given(p_values, alphas)
def test_bh_never_makes_a_p_value_smaller_and_caps_q_at_one(p, alpha):
    rejected, q = benjamini_hochberg(p, alpha)
    valid = ~np.isnan(p)
    assert np.all(q[valid] >= p[valid] - 1e-15) and np.all(q[valid] <= 1.0)
    assert np.all(np.isnan(q[~valid])) and not rejected[~valid].any()


@given(p_values, alphas)
def test_bh_rejects_exactly_the_hypotheses_whose_q_clears_alpha(p, alpha):
    rejected, q = benjamini_hochberg(p, alpha)
    valid = ~np.isnan(p)
    # Equivalent definitions of the procedure; a float-rounding tie at the boundary is the only slack.
    assert np.all(q[valid & rejected] <= alpha * (1 + 1e-9))
    assert np.all(q[valid & ~rejected] > alpha * (1 - 1e-9))


@given(p_values, alphas)
def test_bh_rejections_are_the_smallest_p_values(p, alpha):
    rejected, _ = benjamini_hochberg(p, alpha)
    if rejected.any() and (~rejected & ~np.isnan(p)).any():
        assert p[rejected].max() <= p[~rejected & ~np.isnan(p)].min()


@given(p_values, alphas)
def test_bh_q_is_monotone_in_p(p, alpha):
    _, q = benjamini_hochberg(p, alpha)
    valid = np.flatnonzero(~np.isnan(p))
    order = valid[np.argsort(p[valid], kind="stable")]
    assert np.all(np.diff(q[order]) >= -1e-15)


@given(p_values, alphas, st.randoms(use_true_random=False))
def test_bh_does_not_depend_on_input_order(p, alpha, rnd):
    rejected, q = benjamini_hochberg(p, alpha)
    order = list(range(len(p)))
    rnd.shuffle(order)
    rejected2, q2 = benjamini_hochberg(p[order], alpha)
    np.testing.assert_array_equal(rejected2, rejected[order])
    np.testing.assert_allclose(q2, q[order], rtol=0, atol=1e-15)


@given(p_values, alphas)
def test_bh_rejects_no_more_than_an_uncorrected_sweep(p, alpha):
    rejected, _ = benjamini_hochberg(p, alpha)
    assert rejected.sum() <= np.sum(p[~np.isnan(p)] <= alpha)


# ------------------------------------------------------------------ cluster bootstrap


@st.composite
def bucket_table(draw):
    """A calibration-table-shaped problem: binary outcomes, each row in exactly one of k buckets."""
    n = draw(st.integers(2, 80))
    k = draw(st.integers(1, 4))
    bucket = draw(hnp.arrays(np.int64, n, elements=st.integers(0, k - 1)))
    outcome = draw(hnp.arrays(np.float64, n, elements=st.sampled_from([0.0, 1.0])))
    clusters = draw(hnp.arrays(np.int64, n, elements=st.integers(0, n // 2)))
    membership = np.zeros((n, k))
    membership[np.arange(n), bucket] = 1.0
    return membership * outcome[:, None], membership, clusters


@given(bucket_table(), st.integers(0, 2**31 - 1), confidence)
def test_bootstrap_ratio_interval_is_an_ordered_probability_or_nan(table, seed, conf):
    numerator, denominator, clusters = table
    low, high = cluster_bootstrap_ratio_ci(numerator, denominator, clusters, reps=50, seed=seed, confidence=conf)
    for column in range(numerator.shape[1]):
        if denominator[:, column].sum() == 0:
            assert math.isnan(low[column]) and math.isnan(high[column])
        else:
            assert 0.0 <= low[column] <= high[column] <= 1.0


@given(bucket_table(), st.integers(0, 2**31 - 1))
def test_the_bootstrap_is_a_pure_function_of_its_seed(table, seed):
    numerator, denominator, clusters = table
    a = cluster_bootstrap_ratio_ci(numerator, denominator, clusters, reps=30, seed=seed)
    b = cluster_bootstrap_ratio_ci(numerator, denominator, clusters, reps=30, seed=seed)
    np.testing.assert_array_equal(a[0], b[0])
    np.testing.assert_array_equal(a[1], b[1])


@given(hnp.arrays(np.float64, st.tuples(st.integers(1, 40), st.integers(1, 3)), elements=st.floats(-10, 10)),
       st.integers(0, 1000))
def test_bootstrap_sum_bounds_bracket_a_constant_column(matrix, seed):
    """With every row in its own cluster and every value equal, every replicate's sum is n * value."""
    matrix[:] = matrix[0]
    n = matrix.shape[0]
    low, high = cluster_bootstrap_ci(matrix, np.arange(n), reps=20, seed=seed)
    np.testing.assert_allclose(low, n * matrix[0], rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(high, n * matrix[0], rtol=1e-9, atol=1e-9)


@given(st.integers(1, 5), st.integers(1, 5))
def test_bootstrap_refuses_mismatched_inputs(rows, extra):
    assume(rows != rows + extra)
    with pytest.raises(ValueError):
        cluster_bootstrap_ci(np.ones((rows, 2)), np.arange(rows + extra), reps=5, seed=0)
    with pytest.raises(ValueError):
        cluster_bootstrap_ratio_ci(np.ones((rows, 2)), np.ones((rows, 3)), np.arange(rows), reps=5, seed=0)
