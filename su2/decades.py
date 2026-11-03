# -*- coding: utf-8 -*-
"""Decadas de caida del residuo DENTRO de cada paso fisico (criterio >= 1.2).
En paso dual el NIVEL del residuo no mide convergencia; lo que mide es esta caida.
Uso: python3 decades.py <history_*.csv>"""
import csv, os, sys, statistics as st
from collections import defaultdict
import glob
args = sys.argv[1:] or ["history_A.csv"]
ps = [q for a in args for q in glob.glob(os.path.expanduser(a))]
if not ps:
    sys.exit("no hay archivos de history que coincidan con %s" % args)
p = sorted(ps)[0]
rows = list(csv.reader(open(p)))
hdr = [c.strip().strip('"') for c in rows[0]]
i_t = hdr.index("Time_Iter"); i_in = hdr.index("Inner_Iter")
i_r = [k for k, c in enumerate(hdr) if "rms[Rho]" in c][0]
per = defaultdict(list)
for r in rows[1:]:
    if r and r[0].strip():
        per[int(r[i_t])].append((int(r[i_in]), float(r[i_r])))
ks = sorted(per)
dec = []
for s in ks:
    v = sorted(per[s])
    if len(v) > 1:
        dec.append((s, v[0][1] - v[-1][1], len(v)))
print("pasos fisicos con mas de una iteracion interna: %d" % len(dec))
if dec:
    d = [x[1] for x in dec]
    print("decadas de caida DENTRO del paso:")
    print("  mediana %.3f | min %.3f | max %.3f | iteraciones internas %d"
          % (st.median(d), min(d), max(d), dec[0][2]))
    print("  ultimos 10 pasos:", " ".join("%.2f" % x for x in d[-10:]))
    print()
    print("  CRITERIO >= 1.2 decadas:", "PASA" if st.median(d) >= 1.2 else "NO PASA")
