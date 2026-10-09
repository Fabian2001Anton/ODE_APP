import re
import sympy
import pandas as pd

from create_matrix_for_eq import main_create_matrix_for_eq as create_matrix

class Settings:
    def __init__(self):
        self.ROW_LENGTH = 4
        self.COLUMN_DISTANCE = "4cm"
        self.ROW_DISTANCE = "3.5cm"


def latex(text): #transforms equations to Latex compileable code
    text = text.replace(" ** ", "^").replace(" * ", " ")
    text = re.sub(r"\b([yp])(\d+)\b", r"\1_{\2}", text)
    return f"${text}$"


def label(cell): #transforms a cell of the matrix to a LaTeX label
    return f"${sympy.latex(sympy.sympify(cell))}$"


def render_tikz(equations, eq_names, settings):
    variables = [f"y{index}" for index in range(1, len(equations) + 1)]
    grid = {name: (index % settings.ROW_LENGTH, index // settings.ROW_LENGTH) for index, name in enumerate(variables)}

    lines = [r"\begin{tikzpicture}[auto, node distance=1cm]",]
    for index, name in enumerate(variables):
        box = f"$y_{{{index + 1}}}$ ({eq_names[index]})"
        if index == 0:
            lines.append(f"    \\node [block] ({name}) {{{box}}};")
        elif index % settings.ROW_LENGTH == 0:
            lines.append(f"    \\node [block, below of={variables[index - settings.ROW_LENGTH]}, "
                         f"node distance={settings.ROW_DISTANCE}] ({name}) {{{box}}};")
        else:
            lines.append(f"    \\node [block, right of={variables[index - 1]}, "
                         f"node distance={settings.COLUMN_DISTANCE}] ({name}) {{{box}}};")
    lines.append("")

    #arrows
    
    df = create_matrix(equations)

    #the constant terms
    const_col = df["constant"]
    for index, name in enumerate(variables):
        if pd.isna(const_col.iloc[index]):
            continue
        lines.append(f"\\draw [->] ($(-0.8cm,1.5cm)+({name})$)node[above]{{{label(const_col.iloc[index])}}} -- ({name});")

    #the rest terms 
    rest_col = df["rest"]
    for index, name in enumerate(variables):
        if pd.isna(rest_col.iloc[index]):
            continue
        lines.append(f"\\draw [->] ($(0.8cm,1.5cm)+({name})$)node[above]{{{label(rest_col.iloc[index])}}} -- ({name});")

    #terms on the diagonal
    diagonal = [df.loc[f"dy{index}/dt", f"y{index}"] for index in range(1, len(equations) + 1)]
    for index, name in enumerate(variables): #draw arrows that band under the box
        if pd.isna(diagonal[index]):
            continue
        lines.append(f"\\draw [->] ({name}) to [loop below] node {{{label(diagonal[index])}}} ({name});")

    #upper and lower diagonal of matrix 
    #check for each element if NONE
    for row in range(1, len(equations) + 1):
        for col in range(row + 1, len(equations) + 1):
            box_row, box_col = f"y{row}", f"y{col}"
            element_upper = df.loc[f"dy{row}/dt", box_col]
            element_lower = df.loc[f"dy{col}/dt", box_row]
            if pd.notna(element_upper) and pd.notna(element_lower) and sympy.sympify(element_upper) == -sympy.sympify(element_lower): #here the strings need to be transforemed to numbers
                lines.append(f"\\draw [->] ({box_col}) --node[name=z,anchor=north]{{{label(element_upper)}}} ({box_row});")
            else:
                if pd.notna(element_upper):
                    lines.append(f"\\draw [->] ($({box_col})!0.35!({box_row})!0.5cm!90:({box_row})$) --node[name=z]{{{label(element_upper)}}}({box_row});") #upper diagonal matrix
                if pd.notna(element_lower):
                    lines.append(f"\\draw [->] ($({box_row})!0.35!({box_col})!0.5cm!90:({box_col})$) --node[name=z]{{{label(element_lower)}}}({box_col});") #lower diagonal matrix

    lines.append("\\end{tikzpicture}")
    return "\n".join(lines)

def render_eq_list(equations):
    """Render the ODE system as a LaTeX align block, one row per equation."""
    rows = [
        rf"    \dot{{y}}_{{{i}}} &= {sympy.latex(sympy.sympify(eq))}"
        for i, eq in enumerate(equations, start=1)
    ]
    return "\n".join([r"$\begin{aligned}", (r" \\" + "\n").join(rows), r"\end{aligned}$"])

def build_document(system):
    equations = system["equations"]
    settings = Settings()
    d = len(equations)
    names = system.get("names", {})
    names = [names.get(f"y{i}", f"equation {i}") for i in range(1, d + 1)]
    
    return "\n".join([
        r"\documentclass[border=10pt]{standalone}",
        r"\usepackage{amsmath}",
        r"\usepackage{tikz}",
        r"\usetikzlibrary{arrows.meta, positioning, calc}",
        r"\tikzset{block/.style = {draw, rectangle, minimum size=1cm},>={Latex},}",
        r"\begin{document}",
        r"\begin{tabular}{c}",
        render_tikz(equations, names, settings),
        r"\\[1em]",
        render_eq_list(equations),
        r"\end{tabular}",
        r"\end{document}",
        "",
    ])