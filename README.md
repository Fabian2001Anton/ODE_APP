# ODE App

An interactive command-line tool for systems of ordinary differential equations (initial value problems). You can import or enter a system, name its variables, set its parameters, solve it with a Radau solver, plot the solution, and draw the system as a compartment diagram (PDF).

## Requirements

- Python 3.9 or newer
- The Python packages `numpy`, `pandas`, `sympy` and `matplotlib`
- For `solve`: the compiled solver `radau.out` in the app folder
- For `draw`: a LaTeX distribution with `pdflatex` and TikZ, for example MacTeX, TeX Live or MiKTeX

```bash
pip install numpy pandas sympy matplotlib
```

## Getting started

Start the app from its folder:

```bash
python main_app.py
```

Then type a command at the prompt. `help` lists all commands.

A typical session:

1. `input` loads or enters a system.
2. `name` gives the variables readable names (optional).
3. `parameters` sets the parameter values.
4. `solve` computes the solution and saves it as a CSV file.
5. `plot` plots the solution.
6. `draw` creates a diagram of the system and opens it as a PDF.

## Folders

| Folder | Contents |
|---|---|
| `Models/` | System files (`.json`) |
| `solutions/` | Solution files (`.csv`) that `plot` reads |
| `Diagrams/` | Diagrams created by `draw` (`.tex`, `.pdf`) |

## System file format

A system is stored as a JSON file in `Models/`:

```json
{
  "t_start": 0.0,
  "t_end": 1.0,
  "equations": [
    "-p1 * y1 + p2 * y2",
    "p1 * y1 - p2 * y2 - p3 * y2"
  ],
  "y0": [1.0, 0.0],
  "parameters": {"p1": 2.5, "p2": 1.0, "p3": 0.5},
  "names": {"y1": "blood", "y2": "tissue"}
}
```

| Field | Meaning |
|---|---|
| `equations` | The right-hand sides. Entry *i* is dy*i*/dt. Variables are `y1 … yn`, parameters `p1 … pm`. You can use `+ - * /`, `**` for powers, and functions like `sin` or `exp`. |
| `y0` | The initial values, one per variable |
| `t_start`, `t_end` | The time interval |
| `parameters` | The values of `p1 … pm`, set with `parameters` |
| `names` | Optional names for the variables, set with `name` |

## Solution file format

A solution file is a comma-separated CSV file in `solutions/`. Its first row is a header, which `plot` skips. The first column is the time, followed by one column per variable (`y1 … yn`):

```text
t,y1,y2
0.0,1.0,0.0
0.1,0.78,0.19
```

## Commands

### `input`

Loads a system. You choose:

- `i` to import an existing system file from `Models/` (`ls` lists the files)
- `n` to enter a new system step by step

The loaded system is printed, and the other commands work with it.

### `name`

Gives the variables of the loaded system readable names. The names appear in the diagram from `draw`.

| Input | Effect |
|---|---|
| `y1="drug concentration in blood"` | Sets the name of `y1` |
| `cat` | Shows the system file |
| `done` | Saves the names and leaves |

The names are saved in the system file under `"names"`. Variables without a name get `equation 1`, `equation 2`, and so on.

### `parameters`

Shows or changes the parameter values in a system file.

1. Choose the file, for example `ivp.json`. `ls` lists the files in `Models/`, and `exit` leaves.
2. The current values are shown. Then:

| Input | Effect |
|---|---|
| `p1=2.5` | Sets a value (not saved yet) |
| `ls` | Lists the values, including unsaved changes |
| `cat` | Shows the system file as it is saved |
| `done` | Saves the changes and leaves |

### `solve`

Solves the loaded system with the Radau solver.

1. Choose a name for the solution file. `.csv` is added if it's missing.
2. The app runs `./radau.out <system>.json <name>.csv` in the app folder.

This needs a loaded system and `radau.out` in the app folder.

### `plot`

Plots a solution of the loaded system.

- Type the name of a file in `solutions/`. `.csv` is added if it's missing.
- `ls` lists the `.csv` files in `solutions/` and ends the command. Run `plot` again to choose one.

A window opens with one plot per variable, up to four per row. Each plot is labeled with the variable's name from `"names"` in the system file, or `equation 1`, `equation 2`, and so on if there is none. The app continues when you close the window.

### `draw`

Draws the loaded system as a diagram, saves it as LaTeX, compiles it to a PDF and opens the PDF.

1. Choose a file name, or press Enter for `ivp_diagram.tex`. If the file already exists, you can overwrite it, rename it or cancel.
2. The `.tex` file is saved in `Diagrams/` and compiled with `pdflatex`. The PDF is saved next to it and opens in your default PDF viewer (macOS, Linux and Windows).

What the diagram shows:

| Element | Meaning |
|---|---|
| Box `y1 (name)` | One box per variable |
| Arrow from the upper left | Constant terms of the equation (no variable) |
| Arrow from the upper right | Non-linear terms, for example `sin(y1)` or `y1 * y2` |
| Loop under a box | The variable's own linear factor in its equation |
| Arrow between two boxes | A coupling. It's one arrow if the two factors cancel each other out (the factor of `yj` in dy*i*/dt is minus the factor of `yi` in dy*j*/dt), otherwise two separate arrows, each pointing in the direction of its flow. |

Below the diagram, the equations are listed.

### `help`

Lists all commands with a short description.

### `clear`

Clears the terminal.

### `quit`

Exits the app.

## For developers

### Code overview

| File | Role |
|---|---|
| The command module | The command handlers (`cmd_…`), the `COMMANDS` registry and `AppState` |
| `Input.py` | Input helpers: prompts, loading and saving system files, parameters |
| `draw.py` | Builds the LaTeX/TikZ document for `draw` |
| `create_matrix_for_eq.py` | Splits each equation into constant, linear and non-linear parts (used by `draw`) |
| `plot.py` | Plots a solution, one plot per variable. Its `Settings` class sets the plots per row, the figure size and the axis labels. |
| `radau.out` | The compiled Radau solver |
| `radau.cpp` | The Radau solver in C++|


### Adding a command

1. Write a function `cmd_<name>(state, args)`. Its docstring is the description that `help` shows.
2. Add it to `COMMANDS`.

Every command receives the shared `AppState`:

| Field | Content |
|---|---|
| `system` | The loaded system (a dict, as in the system file) |
| `JSON_name` | The file name of the loaded system |
| `diagram_path` | The last `.tex` file written by `draw` |
| `solution_file` | The last solution file written by `solve` |
| `running` | Set to `False` to exit the app |
