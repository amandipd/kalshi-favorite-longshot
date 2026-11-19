"""Research check, 25 Oct 2026 (modeling_and_backtest_methods.md, intraday section).
Data: Iowa Environmental Mesonet (IEM), public. Download into one folder, then pass it as argv[1]:
  CLI (official daily high/low/precip): https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024  (also KMIA, KLAX; 2024, 2025) -> cli_NYC_2024.json etc.
  ASOS temps: https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC&data=tmpf&year1=2024&month1=1&day1=1&year2=2026&month2=1&day2=2&tz=Etc/UTC&format=onlycomma&latlon=no&missing=empty&trace=T&direct=no&report_type=3&report_type=4 -> asos_NYC.csv
  Raw METAR (for sixhr): same URL with data=metar and 2025 only -> metar_NYC.csv
"""
import json, csv, sys, math
from datetime import datetime, timedelta
from collections import defaultdict
D = sys.argv[1]
OFF = {'NYC': -5, 'MIA': -5, 'LAX': -8}
HOURS = [10, 11, 12, 13, 14, 15, 16, 17]
for s, off in OFF.items():
    cli = {}
    for y in (2024, 2025):
        for r in json.load(open(f'{D}/cli_{s}_{y}.json'))['results']:
            h = r.get('high')
            if isinstance(h, (int, float)):
                cli[r['valid']] = h
    obs = defaultdict(list)  # LST date -> list of (lst hour float, temp)
    with open(f'{D}/asos_{s}.csv') as f:
        rd = csv.DictReader(f)
        for r in rd:
            if not r['tmpf']: continue
            t = datetime.strptime(r['valid'], '%Y-%m-%d %H:%M') + timedelta(hours=off)
            obs[t.strftime('%Y-%m-%d')].append((t.hour + t.minute/60, float(r['tmpf'])))
    days = sorted(d for d in cli if d in obs and len(obs[d]) >= 20)
    gap_full = []
    res = {H: [] for H in HOURS}
    for d in days:
        o = obs[d]
        full = round(max(t for _, t in o))
        gap_full.append(cli[d] - full)
        for H in HOURS:
            sofar = [t for h, t in o if h < H]  # obs before H:00 LST
            if not sofar: continue
            res[H].append(cli[d] - round(max(sofar)))
    n = len(days)
    print(f'== {s}: {n} days (2024-2025), CLI high vs METAR/ASOS reports (routine+specials), LST hours')
    gf = gap_full
    print(f'  CLI high minus max of reports all day: mean {sum(gf)/n:.2f}F; share 0: {sum(1 for g in gf if g==0)/n:.0%}; share >=1: {sum(1 for g in gf if g>=1)/n:.0%}; share >=2: {sum(1 for g in gf if g>=2)/n:.0%}; share <0: {sum(1 for g in gf if g<0)/n:.0%}')
    for H in HOURS:
        r = res[H]; m = len(r)
        mean = sum(r)/m; sd = math.sqrt(sum((x-mean)**2 for x in r)/m)
        print(f'  before {H:02d}:00 LST: remaining rise mean {mean:.2f}F sd {sd:.2f}; already-reached(<=0) {sum(1 for x in r if x<=0)/m:.0%}; <=1F {sum(1 for x in r if x<=1)/m:.0%}; >=3F {sum(1 for x in r if x>=3)/m:.0%}; >=5F {sum(1 for x in r if x>=5)/m:.0%}')
    # seasonal split at 14 LST
    for lab, months in (('Jun-Aug', {6,7,8}), ('Dec-Feb', {12,1,2})):
        r = [cli[d] - round(max(t for h, t in obs[d] if h < 14)) for d in days if int(d[5:7]) in months and any(h < 14 for h, _ in obs[d])]
        m = len(r); mean = sum(r)/m; sd = math.sqrt(sum((x-mean)**2 for x in r)/m)
        print(f'  {lab} before 14:00 LST: n {m}, mean {mean:.2f}, sd {sd:.2f}, already-reached {sum(1 for x in r if x<=0)/m:.0%}')
