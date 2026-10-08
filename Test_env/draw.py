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


def render_tikz(equations, eq_names, settings):
    variables = [f"y{index}" for index in range(1, len(equations) + 1)]
    grid = {name: (index % settings.ROW_LENGTH, index // settings.ROW_LENGTH) for index, name in enumerate(variables)}

    lines = [r"\begin{tikzpicture}[auto, node distance=1cm]",]
    for index, name in enumerate(variables):
        box = f"$y_{{{index + 1}}}$"
        if index == 0:
            lines.append(f"    \\node [block] ({name} ({eq_names[index]})) {{{box}}};")
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
            box = f"$y_{{{index + 1}}}$"
            lines.append(f"\draw [->] ($(0.8cm,-1.5cm)+({{{box}}})node[above]{${{{const_col[index]}}}$} -- ({{{box}}});")

    #the rest terms 
    rest_col = df["rest"]
    for index, name in enumerate(variables):
        box = f"$y_{{{index + 1}}}$"
        lines.append(f"\draw [->] ($(0.8cm,1.5cm)+({{{box}}})$)node[above]{${{{rest_col[index]}}}$} -- ({{{box}}});")

    #terms on the diagonal
    diagonal = [df.loc[f"dy{index}/dt", f"y{index}"] for index in range(len(equations))]
    for #draw arrows that band under the box

    #upper and lower diagonal of matrix 
    #check for each element if NONE
    for 
        for 
            if element_upper_number == -element_lower_number #here the strings need to be transforemed to numbers
                lines.append(f"\draw [->] ({{{box_col}}}) --node[name=z,anchor=north]{${{{element}}}$} ({{{box_row}}});")
            else:
                lines.append(f"\draw [->] ($(1.4cm,-0.5cm)+({{{box_col}}})$) --node[name=z,anchor=north]{${{{element}}}$}({{{box_row}}});") #upper diagonal matrix
                lines.append(f"\draw [<-] ($(1.4cm,-0.5cm)+({{{box_row}}})$) --node[name=z,anchor=north]{${{{element}}}$}({{{box_col}}});") #upper diagonal matrix                                                                                       

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
    try:
        names = system["names"]
    except:
        names = [f"equation {i+1}" for i in range(d)]
    
    return "\n".join([
        r"\documentclass[border=10pt]{standalone}",
        r"\usepackage{amsmath}",
        r"\usepackage{tikz}",
        r"\usetikzlibrary{arrows.meta, positioning}",
        r"\tikzset{block/.style = {draw, rectangle, minimum size=1cm},>={Latex},}",
        r"\begin{document}",
        r"\begin{tabular}{c}",
        render_tikz(system),
        r"\\[1em]",
        render_eq_list(equations, names, settings),
        r"\end{tabular}",
        r"\end{document}",
        "",
    ])