"""Interactive solver for initial value problems (IVP)."""

import csv
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

SAFE_NAMES = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "exp": np.exp, "log": np.log, "log10": np.log10,
    "sqrt": np.sqrt, 
    "pi": np.pi, "e": np.e,
}

SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def split_top_level(text, sep=","):
    """Split on `sep`, ignoring separators nested inside brackets."""
    parts, current, depth = [], [], 0
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced brackets.")
        if char == sep and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if depth != 0:
        raise ValueError("Unbalanced brackets.")
    parts.append("".join(current).strip())
    return [p for p in parts if p]


def strip_lhs(text):
    """Drop a leading 'name = ' such as 't=' or 'f(t,y)=', keeping ==, <=, >=, != intact."""
    cut, depth = None, 0
    for index, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "=" and depth == 0:
            if text[index - 1:index] in {"<", ">", "!", "="} or text[index + 1:index + 2] == "=":
                continue
            cut = index
    return text if cut is None else text[cut + 1:]


def parse_number_list(raw):
    body = strip_lhs(raw).strip()
    if body[:1] in "([" and body[-1:] in ")]":
        body = body[1:-1]
    parts = split_top_level(body)
    if not parts:
        raise ValueError("No values given.")
    values = []
    for part in parts:
        try:
            values.append(float(part))
        except ValueError:
            raise ValueError(f"'{part}' is not a number.") from None
    return values


def parse_time_range(raw):
    values = parse_number_list(raw)
    if len(values) != 2:
        raise ValueError(f"Expected exactly 2 values, got {len(values)}.")
    t_start, t_end = values
    if t_start == t_end:
        raise ValueError("Start and end time must differ.")
    return t_start, t_end


def parse_equations(raw):
    body = strip_lhs(raw).replace("^", "**")
    exprs = split_top_level(body)
    if not exprs:
        raise ValueError("No equations given.")
    codes = []
    for index, expr in enumerate(exprs, start=1):
        try:
            codes.append(compile(expr, f"<equation {index}>", "eval"))
        except SyntaxError as exc:
            raise ValueError(f"Equation {index} '{expr}' is not valid Python: {exc.msg}.") from None
    allowed = set(SAFE_NAMES) | {"t", "y"} | {f"y{i + 1}" for i in range(len(exprs))}
    for index, (expr, code) in enumerate(zip(exprs, codes), start=1):
        unknown = sorted(set(code.co_names) - allowed)
        if unknown:
            raise ValueError(
                f"Equation {index} '{expr}' uses unknown name(s): {', '.join(unknown)}. "
                f"Available: t, y, y1..y{len(exprs)}, {', '.join(sorted(SAFE_NAMES))}."
            )
    return exprs, codes


def make_rhs(codes):
    """Build f(t, y). In equation i, bare `y` is yi; `y1`..`yn` reach every component."""
    def rhs(t, y):
        namespace = dict(SAFE_NAMES, t=t)
        for index in range(len(codes)):
            namespace[f"y{index + 1}"] = y[index]
        return [
            eval(code, {"__builtins__": {}}, dict(namespace, y=y[index]))
            for index, code in enumerate(codes)
        ]
    return rhs


def check_rhs(rhs, t_start, y0):
    try:
        derivatives = rhs(t_start, np.asarray(y0, dtype=float))
    except ZeroDivisionError:
        raise ValueError("Division by zero at the initial condition.") from None
    except Exception as exc:
        raise ValueError(f"Could not evaluate your equations: {exc}.") from None
    values = np.asarray(derivatives, dtype=float)
    if values.shape != (len(y0),):
        raise ValueError("Each equation must return a single number.")
    if not np.all(np.isfinite(values)):
        raise ValueError("Equations are not finite at the initial condition.")


def render_system(exprs, y0, t_start, t_end):
    lines = [f"ẏ{str(i).translate(SUBSCRIPTS)} = {expr}" for i, expr in enumerate(exprs, start=1)]
    lines.append("y({}) = ({})".format(t_start, ", ".join(str(v) for v in y0)))
    lines.append(f"t ∈ [{t_start}, {t_end}]")
    if len(lines) == 1:
        return f"{{ {lines[0]}"
    brace = ["⎪"] * len(lines)
    brace[0], brace[-1] = "⎧", "⎩"
    brace[len(lines) // 2] = "⎨"
    return "\n".join(f"{b} {line}" for b, line in zip(brace, lines))


def ask(prompt, parser, default=None):
    while True:
        try:
            raw = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)
        if not raw.strip() and default is not None:
            return default
        try:
            return parser(raw)
        except ValueError as exc:
            print(f"  ✗ {exc} Please try again.\n")


def parse_choice(raw):
    choice = raw.strip().lower()[:1]
    if choice not in {"o", "r", "c"}:
        raise ValueError("Type 'o', 'r' or 'c'.")
    return choice


def parse_filename(raw):
    name = raw.strip().strip('"').strip("'")
    if not name:
        raise ValueError("File name must not be empty.")
    if not name.lower().endswith(".csv"):
        name += ".csv"
    path = Path(name).expanduser()
    if path.is_dir():
        raise ValueError(f"'{path}' is a directory.")
    return path


def choose_output_path(default="ivp.csv"):
    path = ask(f"Save the solution as [{default}]:\n> ", parse_filename, default=Path(default))
    while path.exists():
        print(f"  ! '{path}' already exists.")
        choice = ask("  Overwrite, rename or cancel? [o/r/c]: ", parse_choice)
        if choice == "o":
            return path
        if choice == "c":
            return None
        path = ask("  New file name:\n> ", parse_filename)
    return path


def write_csv(path, sol):
    header = ["t"] + [f"y{i + 1}" for i in range(sol.y.shape[0])]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(np.column_stack([sol.t, sol.y.T]))
    except OSError as exc:
        print(f"  ✗ Could not write '{path}': {exc}")
        return False
    return True


def main():
    print(
        "This app solves and saves the solution of your IVP.\n"
        "Please define your system of ordinary differential equations.\n"
        "In equation i, 'y' means yi; use y1, y2, ... to couple the equations.\n"
    )
    print("⎧ ẏ = f(t, y)\n⎨\n⎩ (t₀, y₀)\n")

    t_start, t_end = ask(
        "Define the time range: (e.g. t=(0,1))\n> ", parse_time_range
    )
    exprs, codes = ask(
        "Define f(t, y), one equation per comma: (e.g. y+1, cos(y2)-1, y^2+y)\n> ",
        parse_equations,
    )
    rhs = make_rhs(codes)
    count = len(exprs)

    def parse_initial(raw):
        values = parse_number_list(raw)
        if len(values) != count:
            raise ValueError(
                f"You gave {len(values)} initial value(s) for {count} equation(s)."
            )
        check_rhs(rhs, t_start, values)
        return values

    example = ", ".join(str(i) for i in range(1, count + 1))
    y0 = ask(
        f"Define y₀ = y({t_start}), {count} value(s): (e.g. ({example}))\n> ",
        parse_initial,
    )

    print("\nSolving:\n" + render_system(exprs, y0, t_start, t_end) + "\n")

    try:
        sol = solve_ivp(
            rhs, (t_start, t_end), y0,
            t_eval=np.linspace(t_start, t_end, 200),
            rtol=1e-8, atol=1e-10,
        )
    except Exception as exc:
        print(f"  ✗ The solver failed: {exc}")
        return
    if not sol.success:
        print(f"  ✗ The solver stopped early: {sol.message}")
        if sol.t.size == 0:
            return

    final = ", ".join(f"{value:.6g}" for value in sol.y[:, -1])
    print(f"  ✓ {sol.t.size} steps, y({sol.t[-1]:.6g}) = ({final})\n")

    path = choose_output_path()
    if path is None:
        print("Nothing saved.")
        return
    if write_csv(path, sol):
        print(f"  ✓ Solution saved to '{path}'")


if __name__ == "__main__":
    main()