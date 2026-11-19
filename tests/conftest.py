"""Shared settings for the property-based ("fuzz") tests.

Hypothesis generates the inputs for every test that uses `@given`. Two profiles:

    default   the one a plain `pytest` run uses: enough examples to catch a broken invariant without
              making the suite slow
    thorough  HYPOTHESIS_PROFILE=thorough pytest -- ten times the examples, for a deliberate hunt

There is no per-example deadline: several properties drive pandas, statsmodels or a bootstrap, whose first
call pays a one-off import or JIT cost that a deadline would misread as a slow input.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

settings.register_profile(
    "default",
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "thorough",
    max_examples=600,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
