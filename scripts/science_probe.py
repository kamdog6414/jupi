#!/usr/bin/python3
"""Bounded numerical, symbolic, plotting and serial-discovery self-test."""
import json
import os
from pathlib import Path

os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['OMP_NUM_THREADS'] = '2'
import numpy as np
import scipy.linalg
import sympy as sp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from serial.tools import list_ports

x = np.arange(11, dtype=float)
y = 3*x + 2
coefficients, _, _, _ = scipy.linalg.lstsq(np.column_stack([x, np.ones_like(x)]), y)
residual = float(np.max(np.abs(coefficients[0]*x + coefficients[1] - y)))
assert np.allclose(coefficients, [3, 2]) and residual < 1e-10
symbol = sp.Symbol('x')
assert sp.diff(symbol**3, symbol) == 3*symbol**2
output = Path('/home/pi/ChatGPT/JUPI/.cache/probes/calibration-self-test.png')
output.parent.mkdir(parents=True, exist_ok=True)
fig, axis = plt.subplots(figsize=(6, 4))
axis.plot(x, y, 'o', label='Synthetic input')
axis.plot(x, coefficients[0]*x + coefficients[1], label='Least-squares result')
axis.set(xlabel='Synthetic input units', ylabel='Synthetic response units',
         title='JUPI calibration self-test — synthetic data')
axis.legend()
fig.tight_layout()
fig.savefig(output, dpi=140)
plt.close(fig)
print(json.dumps({'test': 'synthetic calibration; no physical sensor data',
                  'numpy': np.__version__, 'scipy': scipy.__version__, 'sympy': sp.__version__,
                  'slope': float(coefficients[0]), 'intercept': float(coefficients[1]),
                  'maximum_residual': residual, 'symbolic_derivative': '3*x**2',
                  'plot': str(output), 'serial_ports': [p.device for p in list_ports.comports()]}))
