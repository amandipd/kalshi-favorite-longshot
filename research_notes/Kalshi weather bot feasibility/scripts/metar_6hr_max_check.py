"""Research check, 25 Oct 2026 (modeling_and_backtest_methods.md, intraday section).
Data: Iowa Environmental Mesonet (IEM), public. Download into one folder, then pass it as argv[1]:
  CLI (official daily high/low/precip): https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2024  (also KMIA, KLAX; 2024, 2025) -> cli_NYC_2024.json etc.
  ASOS temps: https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=NYC&data=tmpf&year1=2024&month1=1&day1=1&year2=2026&month2=1&day2=2&tz=Etc/UTC&format=onlycomma&latlon=no&missing=empty&trace=T&direct=no&report_type=3&report_type=4 -> asos_NYC.csv
  Raw METAR (for sixhr): same URL with data=metar and 2025 only -> metar_NYC.csv
"""
import json, csv, sys, re
from datetime import datetime, timedelta
from collections import defaultdict
D = sys.argv[1]
c2f = lambda c: c*9/5+32
for s, off in (('NYC', -5), ('MIA', -5), ('LAX', -8)):
    cli = {r['valid']: r['high'] for r in json.load(open(f'{D}/cli_{s}_2025.json'))['results'] if isinstance(r.get('high'), (int, float))}
    six = defaultdict(list); tg = defaultdict(list)
    for r in csv.DictReader(open(f'{D}/metar_{s}.csv')):
        m = r['metar']; t = datetime.strptime(r['valid'], '%Y-%m-%d %H:%M')
        rmk = m.split(' RMK ')[1] if ' RMK ' in m else ''
        lst = t + timedelta(hours=off)
        g = re.search(r'\bT([01])(\d{3})([01])(\d{3})\b', rmk)
        if g:
            tc = int(g.group(2))/10*(-1 if g.group(1)=='1' else 1)
            tg[lst.strftime('%Y-%m-%d')].append(c2f(tc))
        x = re.search(r'(?:^|\s)1([01])(\d{3})(?=\s|$)', rmk)
        if x and t.minute >= 45 or (x and t.minute == 0):
            v = c2f(int(x.group(2))/10*(-1 if x.group(1)=='1' else 1))
            # 6-hr window ends at report time (synoptic ~xx:51 before 00/06/12/18Z); attribute to LST day of window end minus 1 minute
            end = lst + timedelta(minutes=9)
            if 1 <= end.hour <= 5: continue
            six[(end - timedelta(minutes=1)).strftime('%Y-%m-%d')].append((end.hour, v))
    days = [d for d in sorted(cli) if d in tg]
    gT = [cli[d] - round(max(tg[d])) for d in days]
    both = [d for d in days if d in six]
    g6 = [cli[d] - round(max(max(v for _, v in six[d]), max(tg[d]))) for d in both]
    n = len(days); m = len(both)
    print(f'{s} 2025: T-group hourly max vs CLI: mean gap {sum(gT)/n:.2f}F, exact match {sum(1 for x in gT if x==0)/n:.0%}')
    print(f'      adding 6-hr max groups: mean gap {sum(g6)/m:.2f}F, exact {sum(1 for x in g6 if x==0)/m:.0%}, within 1F {sum(1 for x in g6 if abs(x)<=1)/m:.0%}, CLI lower {sum(1 for x in g6 if x<0)/m:.0%} (n={m})')
