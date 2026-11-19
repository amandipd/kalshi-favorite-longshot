"""Tests for losses_check.py: reading METARs, station summaries (DSM) and climate reports (CLI), and deciding
when a day's official high first became public.

    python -m pytest research/weather_favourites/tests -q
"""
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import losses_check as lc  # noqa: E402


def utc(s):
    return int(datetime.fromisoformat(s + "+00:00").timestamp())


# --- METAR ---------------------------------------------------------------------------------------------------------

def test_metar_t_group_and_six_hour_max():
    m = "KNYC 142351Z AUTO VRB05G19KT 10SM CLR 31/19 A2992 RMK AO2 SLP122 T03110194 10322 20306 56014 $"
    g = lc.metar_groups(m)
    assert g["temp"] == 88 and g["max6"] == 90 and g["max24"] is None


def test_metar_negative_temperatures_and_24_hour_group():
    m = "KMDW 060551Z 27010KT 10SM OVC020 M01/M06 A3010 RMK AO2 SLP199 T10111056 11006 21017 410061017 51010"
    g = lc.metar_groups(m)
    assert g["temp"] == 30 and g["max6"] == 31 and g["max24"] == 31


def test_metar_without_remarks_has_no_groups():
    g = lc.metar_groups("KLAX 231953Z 25008KT 10SM FEW020 18/12 A3001")
    assert g == {"temp": None, "max6": None, "max24": None}


def test_pressure_and_precip_groups_are_not_read_as_maxima():
    g = lc.metar_groups("KSEA 032353Z 18012KT 10SM RA OVC015 12/10 A2990 RMK AO2 SLP127 P0002 60010 T01170100 10128 20111 58010")
    assert g["max6"] == 55 and g["temp"] == 53


# --- DSM and CLI ---------------------------------------------------------------------------------------------------

DSM = """339
CXUS41 KOKX 142015
DSMNYC
KNYC DS 1500 14/07 891451/ 720629// 89/ 72//9961459/00/00/00/00/00/
"""

DSM_FINAL = """714
CXUS41 KOKX 140515
DSMNYC
KNYC DS 13/07 841341/ 700557// 84/ 70//0122359/00/00/00/00/00/00/00/
"""


def test_dsm_gives_max_so_far_and_its_time():
    d = lc.dsm(DSM, year=2026, month=7)
    assert d == {"issued": utc("2026-07-14T20:15:00"), "day": 14, "max": 89, "at": "1451", "final": False}


def test_final_dsm_has_no_valid_time():
    d = lc.dsm(DSM_FINAL, year=2026, month=7)
    assert d["final"] and d["max"] == 84 and d["day"] == 13


CLI = """000
CDUS41 KOKX 142033
CLINYC

CLIMATE REPORT
NATIONAL WEATHER SERVICE NEW YORK NY
433 PM EDT TUE JUL 14 2026

...THE CENTRAL PARK NY CLIMATE SUMMARY FOR JULY 14 2026...
VALID TODAY AS OF 0400 PM LOCAL TIME.

TEMPERATURE (F)
 TODAY
  MAXIMUM         89   1451 PM 102    1995  85      4       86
"""


def test_cli_gives_issue_time_and_maximum():
    c = lc.cli(CLI, year=2026, month=7)
    assert c == {"issued": utc("2026-07-14T20:33:00"), "max": 89, "preliminary": True}


def test_split_products():
    assert len(lc.split_products(DSM + "\n" + DSM_FINAL)) == 2


# --- when did the high become public? -------------------------------------------------------------------------

DAY = (utc("2026-07-14T05:00:00"), utc("2026-07-15T05:00:00"))   # New York climate day, standard time
T = utc("2026-07-14T22:59:00")


def ev(t, src, value):
    return {"t": utc(t), "source": src, "value": value}


def test_first_public_is_the_earliest_source_at_or_above_the_high():
    evs = [ev("2026-07-14T17:51:00", "hourly", 89), ev("2026-07-14T21:15:00", "dsm", 89),
           ev("2026-07-14T23:51:00", "6-hour group", 90), ev("2026-07-15T04:51:00", "24-hour group", 90)]
    assert lc.first_public(evs, 90, DAY) == (utc("2026-07-14T23:51:00"), "6-hour group")


def test_first_public_ignores_reports_outside_the_climate_day():
    evs = [ev("2026-07-14T03:51:00", "hourly", 95), ev("2026-07-15T06:21:00", "final CLI", 90)]
    assert lc.first_public(evs, 90, DAY) == (None, None)


@pytest.mark.parametrize("public,max_at,want", [
    ("2026-07-14T20:51:00", "2026-07-14T20:40:00", "public before 6 PM"),
    ("2026-07-14T23:51:00", "2026-07-14T21:12:00", "measured before 6 PM, public after"),
    (None, "2026-07-14T21:12:00", "measured before 6 PM, never public before close"),
    ("2026-07-15T02:51:00", "2026-07-15T02:30:00", "late warming after 6 PM"),
])
def test_classify(public, max_at, want):
    assert lc.classify(utc(public) if public else None, utc(max_at), T) == want


def test_cli_time_of_max_is_local_standard_time():
    # 4:12 PM standard time in New York (UTC-5) is 21:12 UTC, summer or winter
    assert lc.max_time("2026-07-14", "412 PM", -5) == utc("2026-07-14T21:12:00")
    assert lc.max_time("2026-01-05", "1154 PM", -5) == utc("2026-01-06T04:54:00")
    assert lc.max_time("2026-01-05", "1200 AM", -5) == utc("2026-01-05T05:00:00")
