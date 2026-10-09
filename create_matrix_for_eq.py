import re
import pandas as pd
import math
import sympy

#pair to strings
def format_elements(elements):
    """[nan, ('+', 'p1 * y1'), ('-', 'p4')] -> [nan, 'p1 * y1', '- p4']"""
    row = []
    for element in elements:
        if isinstance(element, tuple):      # a (sign, body) pair
            sign, body = element
            row.append(f"{sign} {body}")
        else:                               # an empty group (NaN) stays NaN
            row.append(element)
    for i, text in enumerate(row):
        if isinstance(text, str):           # the first real element is written without '+ '
            row[i] = text.removeprefix("+ ")
            break
    return row

#helper functions

def multiply_signs(a, b):
    """Sign rule: same signs give '+', different signs give '-'."""
    return "+" if a == b else "-"

def join_elements(elements):
    """[('+', 'p1 * y1'), ('-', 'p4')] -> 'p1 * y1 - p4'"""
    return " ".join(format_elements(elements))

def signed(element):
    """'- p3 * y2' -> ('-', 'p3 * y2'),  'p1 * y1' -> ('+', 'p1 * y1')"""
    if element[0] in "+-":
        return element[0], element[1:].strip()
    return "+", element


def is_bracketed(text):
    """True if one bracket pair encloses all of text: '(p1 - p2)' yes, '(p1) * (y1)' no."""
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    for char in text[:-1]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth == 0:
            return False    # the first bracket closed before the end
    return True


def split_factors(element):
    """'p1 * sin(y1 * y2) * y1' -> ['p1', 'sin(y1 * y2)', 'y1']  ('**' is not split: 'y1 ** 2' stays one factor)"""
    factors = []
    current = ""
    depth = 0
    for i, char in enumerate(element):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "*" and depth == 0 and "**" not in element[i - 1:i + 2]:
            factors.append(current.strip())
            current = ""
            continue
        current += char
    factors.append(current.strip())
    return factors

def has_variable(text):
    """True if text contains a state variable y1, y2, ..."""
    return re.search(r"\by\d+\b", text) is not None



def split_elements(equation):
    """'p1 * y1 - p3 * y2 + sin(y1) - p4' -> ['p1 * y1', '- p3 * y2', '+ sin(y1)', '- p4']"""
    elements = []
    sign = ""       # sign of the element being built: "", "+" or "-"
    current = ""    # text of the element being built, without its sign
    depth = 0       # how many brackets are open at this point
    for char in equation:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char in "+-" and depth == 0:
            if not current.strip():
                # nothing collected yet: sign in front of the first element, e.g. '-p1 * y1'
                sign = char
                continue
            if current.rstrip()[-1] not in "*/^":
                # the previous element is complete: save it and start a new one
                elements.append(f"{sign} {current.strip()}".strip())
                sign, current = char, ""
                continue
            # otherwise the sign belongs to a factor, e.g. 'p1 * -y1', so it's kept below
        current += char
    elements.append(f"{sign} {current.strip()}".strip())
    return elements

#pipline steps

#removes brackets
def flatten(equation):
    """'(p1 * y1 - p3 * y2) - (p4 - p5)' -> [('+', 'p1 * y1'), ('-', 'p3 * y2'), ('-', 'p4'), ('+', 'p5')]"""
    result = []
    for element in split_elements(equation):
        sign, body = signed(element)
        if is_bracketed(body):
            for inner_sign, inner_body in flatten(body[1:-1]):
                result.append((multiply_signs(sign, inner_sign), inner_body))
        else:
            result.append((sign, body))
    return result

def group_keys(dimension):
    """2 -> ['constant', 'y1', 'y2', 'rest']"""
    return ["constant"] + [f"y{k}" for k in range(1, dimension + 1)] + ["rest"]

#groups by variable
def group_linear(elements, dimension):
    #happens after flatten
    """[('-', 'p2 * y1'), ('+', 'sin(y1)'), ('-', 'p1 * y1')], dimension 2 -> [nan, ('-', '(p2 + p1)'), nan, ('+', 'sin(y1)')]"""

    groups = {key: [] for key in group_keys(dimension)}    # key -> [(sign, coefficient, body), ...], already in the final order
    for sign, body in elements:
        factors = split_factors(body)
        variables = [f for f in factors if re.fullmatch(r"y\d+", f)]
        rest = [f for f in factors if not re.fullmatch(r"y\d+", f)]
        if len(variables) == 1 and not any(has_variable(f) for f in rest):
            key, coefficient = variables[0], " * ".join(rest) or "1"    # linear: only the factor in front of yk
            if key not in groups:
                raise ValueError(f"'{key}' is not a variable of a system with {dimension} variables.")
        elif not has_variable(body):
            key, coefficient = "constant", body                         # no variable at all
        else:
            key, coefficient = "rest", body                             # anything else
        groups[key].append((sign, coefficient))

    result = []
    for key, items in groups.items():
        if not items:
            result.append(math.nan)                                     # empty group
            continue
        if len(items) == 1:
            result.append(items[0])
            continue
        outer = items[0][0]
        inner = join_elements([(multiply_signs(outer, sign), coefficient) for sign, coefficient in items])
        result.append((outer, f"({inner})"))
    return result

#simplifies the groups

def simplify_groups(elements):
    """[nan, ('+', '(1 + 1)'), ('-', '(p2 - p2)')] -> [nan, ('+', '2'), nan]"""
    result = []
    for element in elements:
        if isinstance(element, tuple):
            sign, body = element
            expr = sympy.sympify(body)
            if expr == 0:
                element = math.nan                                      # the group cancels out
            elif expr.is_Add:
                element = (sign, f"({expr})")                           # still a sum: keep the brackets
            elif expr.could_extract_minus_sign():
                element = (multiply_signs(sign, "-"), str(-expr))       # e.g. (1 - 3) -> -2: the minus moves into the sign
            else:
                element = (sign, str(expr))
        result.append(element)
    return result

#builds one matrix row
def move_brackets_eq(equation, dimension):
    """'p3 - p2 * y1 + sin(y1) - p1 * y1', dimension 2 -> ['p3', '- (p2 + p1)', nan, '+ sin(y1)']"""
    elements = flatten(equation)
    elements = group_linear(elements, dimension)
    elements = simplify_groups(elements)
    return format_elements(elements)



def main_create_matrix_for_eq(equations):
    dimension = len(equations)
    matrix = []
    for equation in equations:
        elements = move_brackets_eq(equation, dimension)
        # 1. removes unnecessary brackets
        # 2. groups linear elements with the same variable y_ together and keeps only the factor
        # 3. sorts the groups: constant, y1, ..., yn, rest (NaN for an empty group)
        # 4. simplifies each group, e.g. (1 + 1) -> 2 (a group that cancels out becomes NaN)
        matrix.append(elements)
    index = [f"dy{i}/dt" for i in range(1, dimension + 1)]
    return pd.DataFrame(matrix, index=index, columns=group_keys(dimension))

# data = [
#     "- p2 * y2 + p1 * y1 + sin(y1) - p3 * y2 + p4 + p5 + cos(y2)",
#     "y1 +p1 * y2 - p2 * y2 - p3 * y2 + y1"
#   ]
# print(f"data: {data}")
# df = main_create_matrix_for_eq(data)
# print(df)