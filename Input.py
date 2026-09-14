"""Collect and validate an IVP definition, then store it to disk."""

import json
import sys
from pathlib import Path

import numpy as np


SAFE_NAMES = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "asin": np.arcsin, "acos": np.arccos, "atan": np.arctan,
    "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh,
    "exp": np.exp, "log": np.log, "log10": np.log10,
    "sqrt": np.sqrt, "abs": np.abs, "sign": np.sign,
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


def check_equations(codes, t_start, y0):
    """Evaluate each equation once at (t0, y0) to catch runtime errors before storing."""
    namespace_base = dict(SAFE_NAMES, t=t_start)
    for index in range(len(codes)):
        namespace_base[f"y{index + 1}"] = y0[index]
    values = []
    for index, code in enumerate(codes):
        try:
            values.append(eval(code, {"__builtins__": {}}, dict(namespace_base, y=y0[index])))
        except ZeroDivisionError:
            raise ValueError(f"Equation {index + 1} divides by zero at the initial condition.") from None
        except Exception as exc:
            raise ValueError(f"Equation {index + 1} could not be evaluated: {exc}.") from None
    values = np.asarray(values, dtype=float)
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
    if not name.lower().endswith(".json"):
        name += ".json"
    path = Path(name).expanduser()
    if path.is_dir():
        raise ValueError(f"'{path}' is a directory.")
    return path


def choose_output_path(default="ivp.json"):
    path = ask(f"Save the definition as [{default}]:\n> ", parse_filename, default=Path(default))
    while path.exists():
        print(f"  ! '{path}' already exists.")
        choice = ask("  Overwrite, rename or cancel? [o/r/c]: ", parse_choice)
        if choice == "o":
            return path
        if choice == "c":
            return None
        path = ask("  New file name:\n> ", parse_filename)
    return path


def write_json(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as handle:
            json.dump(data, handle, indent=2)
    except OSError as exc:
        print(f"  ✗ Could not write '{path}': {exc}")
        return False
    return True


def main():
    print(
        "This app collects and stores the definition of your IVP.\n"
        "In equation i, 'y' means yi; use y1, y2, ... to couple the equations.\n"
    )
    print("⎧ ẏ = f(t, y)\n⎨\n⎩ (t₀, y₀)\n")

    t_start, t_end = ask(
        "Define the time range: (e.g. t=(0,1))\n> ", parse_time_range
    )
    exprs, codes = ask(
        "Define f(t, y), one equation per comma: (e.g. y1+1, cos(y2)-1, y2^2+y3)\n> ",
        parse_equations,
    )
    count = len(exprs)

    def parse_initial(raw):
        values = parse_number_list(raw)
        if len(values) != count:
            raise ValueError(
                f"You gave {len(values)} initial value(s) for {count} equation(s)."
            )
        check_equations(codes, t_start, values)
        return values

    example = ", ".join(str(i) for i in range(1, count + 1))
    y0 = ask(
        f"Define y₀ = y({t_start}), {count} value(s): (e.g. ({example}))\n> ",
        parse_initial,
    )

    print("\nStoring:\n" + render_system(exprs, y0, t_start, t_end) + "\n")

    path = choose_output_path()
    if path is None:
        print("Nothing saved.")
        return

    data = {"t_start": t_start, "t_end": t_end, "equations": exprs, "y0": y0}
    if write_json(path, data):
        print(f"  ✓ Definition saved to '{path}'")


if __name__ == "__main__":
    main()