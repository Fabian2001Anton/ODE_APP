"""Turn a stored IVP system into a TikZ block diagram.

Each state variable becomes a box; each term becomes an arrow labelled with its
parameter. A term that is negative in one equation and positive in another is drawn
as a single arrow between those two boxes (mass leaving one and entering the other).
"""

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

import Input

ROW_LENGTH = 4
COLUMN_DISTANCE = "4cm"
ROW_DISTANCE = "3.5cm"


class RenameBareY(ast.NodeTransformer):
    """In equation i a bare `y` means yi; rewrite it so every variable is explicit."""

    def __init__(self, owner):
        self.owner = owner

    def visit_Name(self, node):
        return ast.Name(id=self.owner, ctx=node.ctx) if node.id == "y" else node


def split_terms(node, sign=1):
    """Flatten an expression into signed additive terms, distributing products over sums."""
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return split_terms(node.left, sign) + split_terms(node.right, sign)
        if isinstance(node.op, ast.Sub):
            return split_terms(node.left, sign) + split_terms(node.right, -sign)
        if isinstance(node.op, ast.Mult):
            return [
                (sign * left_sign * right_sign, ast.BinOp(left=left, op=ast.Mult(), right=right))
                for left_sign, left in split_terms(node.left)
                for right_sign, right in split_terms(node.right)
            ]
        if isinstance(node.op, ast.Div):
            return [
                (sign * left_sign, ast.BinOp(left=left, op=ast.Div(), right=node.right))
                for left_sign, left in split_terms(node.left)
            ]
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return split_terms(node.operand, -sign)
        if isinstance(node.op, ast.UAdd):
            return split_terms(node.operand, sign)
    return [(sign, node)]


def flatten_product(node, denominator=False):
    """Flatten a term into (factor, is_denominator) pairs."""
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Mult):
            return flatten_product(node.left, denominator) + flatten_product(node.right, denominator)
        if isinstance(node.op, ast.Div):
            return flatten_product(node.left, denominator) + flatten_product(node.right, not denominator)
    return [(node, denominator)]


def variables_in(node, variables):
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and child.id in variables}


def is_chain(node, variables):
    """True if `node` is one variable wrapped in function calls and/or constant powers."""
    if isinstance(node, ast.Name):
        return node.id in variables
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1:
        return is_chain(node.args[0], variables)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
        if not variables_in(node.right, variables):
            return is_chain(node.left, variables)
    return False


def unparse(node):
    return ast.unparse(ast.fix_missing_locations(node))


def format_coefficient(factors):
    numerator = [unparse(node) for node, denominator in factors if not denominator]
    denominator = [unparse(node) for node, denominator in factors if denominator]
    text = " ".join(numerator)
    if denominator:
        text = f"{text or '1'}/{'/'.join(denominator)}"
    return text


def term_key(node, variables):
    """Order-independent identity for a term, so p*y1*y2 and p*y2*y1 match."""
    parts = []
    for factor, denominator in flatten_product(node):
        parts.append(("/" if denominator else "") + unparse(factor))
    return " ".join(sorted(parts))


def classify_term(node, variables):
    """Describe a term as one of: constant, linear, product, chain, complex."""
    plain, transformed, coefficient = [], [], []
    for factor, denominator in flatten_product(node):
        used = variables_in(factor, variables)
        if isinstance(factor, ast.Name) and factor.id in variables and not denominator:
            plain.append(factor.id)
        elif used:
            transformed.append((factor, denominator))
        else:
            coefficient.append((factor, denominator))

    label = format_coefficient(coefficient)
    unique = list(dict.fromkeys(plain))

    if transformed:
        if not plain and len(transformed) == 1:
            factor, denominator = transformed[0]
            inner = variables_in(factor, variables)
            if not denominator and len(inner) == 1 and is_chain(factor, variables):
                return {"kind": "chain", "vars": sorted(inner), "label": label}
        return {"kind": "complex", "vars": sorted(variables_in(node, variables)), "label": label}

    if not unique:
        return {"kind": "constant", "vars": [], "label": label}
    if len(unique) == 1:
        kind = "chain" if len(plain) > 1 else "linear"
        return {"kind": kind, "vars": unique, "label": label}
    return {"kind": "product", "vars": unique, "label": label}


def build_label(info, endpoint):
    """Label for an arrow: the coefficient, any other variables, plus a nonlinearity marker."""
    parts = [info["label"]] if info["label"] else []
    parts.extend(name for name in info["vars"] if name != endpoint)
    if info["kind"] == "chain":
        parts.append("\\circ")
    elif info["kind"] == "complex":
        parts.append("*")
    return " ".join(parts) or "1"


def collect_arrows(equations):
    variables = [f"y{index}" for index in range(1, len(equations) + 1)]
    groups = {}

    for index, expression in enumerate(equations):
        owner = variables[index]
        tree = RenameBareY(owner).visit(ast.parse(expression, mode="eval").body)
        for sign, term in split_terms(tree):
            info = classify_term(term, variables)
            group = groups.setdefault(
                term_key(term, variables), {"info": info, "sources": [], "targets": []}
            )
            (group["targets"] if sign > 0 else group["sources"]).append(owner)

    arrows = []
    for group in groups.values():
        info, sources, targets = group["info"], group["sources"], group["targets"]
        if sources and targets:
            for source in sources:
                for target in targets:
                    if source != target:
                        arrows.append({"kind": "edge", "source": source, "target": target,
                                       "label": build_label(info, source)})
            continue
        for target in targets:
            dependencies = [name for name in info["vars"] if name != target]
            if dependencies:
                arrows.append({"kind": "edge", "source": dependencies[0], "target": target,
                               "label": build_label(info, dependencies[0])})
            else:
                arrows.append({"kind": "stub", "box": target, "direction": "in",
                               "label": build_label(info, target)})
        for source in sources:
            arrows.append({"kind": "stub", "box": source, "direction": "out",
                           "label": build_label(info, source)})
    return arrows


def latex(text): #transforms equations to Latex compileable code
    text = text.replace(" ** ", "^").replace(" * ", " ")
    text = re.sub(r"\b([yp])(\d+)\b", r"\1_{\2}", text)
    return f"${text}$"


def render_tikz(system):
    equations = system["equations"]
    variables = [f"y{index}" for index in range(1, len(equations) + 1)]
    grid = {name: (index % ROW_LENGTH, index // ROW_LENGTH) for index, name in enumerate(variables)}
    arrows = collect_arrows(equations)

    lines = ["\\begin{tikzpicture}[auto, node distance=1cm,>=latex']"]
    for index, name in enumerate(variables):
        box = f"$y_{{{index + 1}}}$"
        if index == 0:
            lines.append(f"    \\node [block] ({name}) {{{box}}};")
        elif index % ROW_LENGTH == 0:
            lines.append(f"    \\node [block, below of={variables[index - ROW_LENGTH]}, "
                         f"node distance={ROW_DISTANCE}] ({name}) {{{box}}};")
        else:
            lines.append(f"    \\node [block, right of={variables[index - 1]}, "
                         f"node distance={COLUMN_DISTANCE}] ({name}) {{{box}}};")
    lines.append("")

    pairs = {(arrow["source"], arrow["target"]) for arrow in arrows if arrow["kind"] == "edge"}
    for arrow in arrows:
        if arrow["kind"] != "edge":
            continue
        source, target = arrow["source"], arrow["target"]
        label = latex(arrow["label"])
        column, row = grid[source]
        other_column, other_row = grid[target]
        adjacent = row == other_row and abs(column - other_column) == 1
        if (target, source) in pairs or not adjacent:
            lines.append(f"    \\draw [->] ({source}) to[bend left=20] "
                         f"node[sloped, anchor=south, font=\\scriptsize]{{{label}}} ({target});")
        else:
            lines.append(f"    \\draw [->] ({source}) --node[sloped, anchor=south, font=\\scriptsize]{{{label}}} ({target});")

    slots = {}
    for arrow in arrows:
        if arrow["kind"] != "stub":
            continue
        box, direction = arrow["box"], arrow["direction"]
        slot = slots.get((box, direction), 0)
        slots[(box, direction)] = slot + 1
        offset = round(0.8 + 0.9 * slot, 2)
        label = latex(arrow["label"])
        if direction == "out":
            lines.append(f"    \\draw [<-] ($({offset}cm,1.5cm)+({box})$)"
                         f"node[above, font=\\scriptsize]{{{label}}} -- ({box});")
        else:
            lines.append(f"    \\draw [->] ($(-{offset}cm,-1.5cm)+({box})$)"
                         f"node[below, font=\\scriptsize]{{{label}}} -- ({box});")

    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)


def build_document(system):
    return "\n".join([
        "\\documentclass[border=10pt]{standalone}",
        "\\usepackage{tikz}",
        "\\usetikzlibrary{calc,arrows}",
        "\\tikzstyle{block} = [draw, rectangle, minimum height=1cm, minimum width=1cm]",
        "\\begin{document}",
        render_tikz(system),
        "\\end{document}",
        "",
    ])


def parse_tex_filename(raw):
    name = raw.strip().strip('"').strip("'")
    if not name:
        raise ValueError("File name must not be empty.")
    if not name.lower().endswith(".tex"):
        name += ".tex"
    path = Path(name).expanduser()
    if path.is_dir():
        raise ValueError(f"'{path}' is a directory.")
    return path


def parse_existing_tex(raw, folder="."):
    name = raw.strip().strip('"').strip("'")
    if not name:
        raise ValueError("File name must not be empty.")
    if not name.lower().endswith(".tex"):
        name += ".tex"
    path = Path(folder) / Path(name).expanduser()
    if not path.exists():
        raise ValueError(f"'{path}' does not exist.")
    if path.is_dir():
        raise ValueError(f"'{path}' is a directory.")
    return path


def compile_document(path):
    """Compile `path` with pdflatex and return the PDF it produced."""
    if shutil.which("pdflatex") is None:
        raise ValueError("pdflatex was not found. Install a LaTeX distribution such as MacTeX or TeX Live.")
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", path.name],
        cwd=path.parent,
        capture_output=True,
        text=True,
    )
    pdf = path.with_suffix(".pdf")
    if result.returncode != 0 or not pdf.exists():
        complaints = [line for line in result.stdout.splitlines() if line.startswith("!")]
        detail = complaints[0] if complaints else f"See '{path.with_suffix('.log')}'."
        raise ValueError(f"pdflatex failed: {detail}")
    return pdf


def open_document(path):
    """Hand the file to the desktop's default viewer."""
    if sys.platform == "darwin":
        command = ["open", str(path)]
    elif sys.platform.startswith("win"):
        command = ["cmd", "/c", "start", "", str(path)]
    else:
        command = ["xdg-open", str(path)]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"Could not open '{path}': {exc}") from None


def save_document(text, default="ivp_diagram.tex", folder="Diagrams"):
    folder = Path(folder)
    name = Input.ask(f"Save the diagram as [{default}]:\ndraw > ", parse_tex_filename, default=Path(default))
    default = Path(default)
    path = folder / name
    while path.exists():
        print(f"  ! '{path}' already exists.")
        choice = Input.ask("  Overwrite, rename or cancel? [o/r/c]: ", Input.parse_choice)
        if choice == "o":
            break
        if choice == "c":
            print("Nothing saved.")
            return None
        path = _in_own_folder(Input.ask("  New file name:\ndraw > ", parse_tex_filename))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    except OSError as exc:
        print(f"  ✗ Could not write '{path}': {exc}")
        return None
    return path
