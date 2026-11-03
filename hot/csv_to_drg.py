#!/usr/bin/env python3
"""Convierte una tabla estructurada (rho,e) en CSV al formato .drg que lee SU2.

Formato tomado del lector del propio SU2 (Common/src/containers/CFileReaderLUT.cpp):
version 1.0.1 = tabla 2-D de un solo nivel. Bloques <Header>, <Data>, <Connectivity>
y <Hull>, con indices de triangulos y casco EN BASE 1.

uso: csv_to_drg.py ENTRADA.csv SALIDA.drg NR NE
     (NR = numero de valores de densidad, NE = numero de valores de energia;
      el CSV debe estar ordenado con la densidad variando mas lento)
"""
import sys

import numpy as np

CSV, DRG = sys.argv[1], sys.argv[2]
NR, NE = int(sys.argv[3]), int(sys.argv[4])

d = np.genfromtxt(CSV, delimiter=",", names=True)
VARS = ["Density", "Energy", "s", "dsdrho_e", "dsde", "d2sdrho2", "d2sdedrho", "d2sde2"]
for v in VARS:
    if v not in d.dtype.names:
        sys.exit("falta la columna %s en %s" % (v, CSV))
N = len(d)
if N != NR * NE:
    sys.exit("el CSV tiene %d puntos pero NR*NE = %d" % (N, NR * NE))

# indice del punto (i,j) en base 1, con la densidad variando mas lento
pid = lambda i, j: i * NE + j + 1

# dos triangulos por celda
tris = []
for i in range(NR - 1):
    for j in range(NE - 1):
        a, b, c, e_ = pid(i, j), pid(i + 1, j), pid(i + 1, j + 1), pid(i, j + 1)
        tris.append((a, b, c))
        tris.append((a, c, e_))

# casco: el perimetro del rectangulo, recorrido en orden
hull = ([pid(0, j) for j in range(NE)] +
        [pid(i, NE - 1) for i in range(1, NR)] +
        [pid(NR - 1, j) for j in range(NE - 2, -1, -1)] +
        [pid(i, 0) for i in range(NR - 2, 0, -1)])

with open(DRG, "w", newline="\n") as f:
    f.write("<Header>\n\n[Version]\n1.0.1\n\n")
    f.write("[Number of points]\n%d\n\n" % N)
    f.write("[Number of triangles]\n%d\n\n" % len(tris))
    f.write("[Number of hull points]\n%d\n\n" % len(hull))
    f.write("[Number of variables]\n%d\n\n" % len(VARS))
    f.write("[Variable names]\n")
    for k, v in enumerate(VARS, 1):
        f.write("%d:%s\n" % (k, v))
    f.write("\n</Header>\n\n<Data>\n")
    for i in range(N):
        f.write(" ".join("%.10e" % d[v][i] for v in VARS) + "\n")
    f.write("</Data>\n\n<Connectivity>\n")
    for t in tris:
        f.write("%d %d %d\n" % t)
    f.write("</Connectivity>\n\n<Hull>\n")
    for h in hull:
        f.write("%d\n" % h)
    f.write("</Hull>\n")

print("escrito %s" % DRG)
print("  %d puntos, %d triangulos, %d puntos de casco, %d variables"
      % (N, len(tris), len(hull), len(VARS)))
print("  rango Density %.4e a %.4e   Energy %.4e a %.4e"
      % (d["Density"].min(), d["Density"].max(), d["Energy"].min(), d["Energy"].max()))
