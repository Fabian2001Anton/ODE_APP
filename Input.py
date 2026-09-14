import ast
import sys
import numpy as np
from pathlib import Path
from scipy.integrate import solve_ivp
import csv

"""Dialoge"""
Explaination = f"This App solves and saves the solution of your IVP. \nPlease define your system of ordinary differential equations:\n"

system = """\
⎧ ẏ = f(t, y)
⎨
⎩ (t₀, y₀)
"""
print(Explaination + system)

str_time_range = input("Define the time range: (e.g. t=(0,1))\n")
t_start, t_end = ast.literal_eval(str_time_range.split("=")[-1].strip())

str_initial_condition = input("Define the initial condition: (e.g. (t0,y0)=(0,1))\n")
t0, y0 = ast.literal_eval(str_initial_condition.split("=")[-1].strip())

str_f = input("Define f(t, y): (e.g. y - t**2 + 1)\n")

ALLOWED_NAMES = {"t": None, "y": None, "np": np, "sin": np.sin, "cos": np.cos,
                  "exp": np.exp, "sqrt": np.sqrt, "log": np.log, "pi": np.pi}

def f(t, y):
    local_ns = {**ALLOWED_NAMES, "t": t, "y": y}
    return eval(str_f, {"__builtins__": {}}, local_ns)

sol = solve_ivp(f, (t_start, t_end), [y0], dense_output=True,
                 t_eval=np.linspace(t_start, t_end, 200))

print(f"\nSolved IVP on t ∈ [{t_start}, {t_end}] with y({t0}) = {y0}")

filename = "ivp_solution.csv"
with open(filename, "w", newline="") as f_out:
    writer = csv.writer(f_out)
    writer.writerow(["t", "y"])
    for t_val, y_val in zip(sol.t, sol.y[0]):
        writer.writerow([t_val, y_val])

print(f"Solution saved to '{filename}'")