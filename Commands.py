"""Command handlers and registry for the interactive REPL."""

import os
from pathlib import Path

import Draw
import Input


class AppState:
    """Shared state passed to every command handler."""

    def __init__(self):
        self.system = None
        self.diagram_path = None
        self.running = True


def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


def choose_mode():
    while True:
        choice = input("Do you want to [i]mport an existing system or enter a [n]ew one? [i/n]: ").strip().lower()[:1]
        if choice in ("i", "n"):
            return choice
        print("  ✗ Please type 'i' or 'n'.\n")


def cmd_help(state, args):
    """List the available commands."""
    print("Available commands:")
    for name, handler in sorted(COMMANDS.items()):
        description = (handler.__doc__ or "").strip()
        print(f"  {name:<10} {description}")


def cmd_quit(state, args):
    """Exit the app."""
    state.running = False


def cmd_clear(state, args):
    """Clear the terminal."""
    clear_terminal()


def cmd_input(state, args):
    """Import an existing system or enter a new one."""
    mode = choose_mode()
    print()
    if mode == "i":
        state.system = Input.import_system()
    else:
        state.system = Input.collect_system()
    print(state.system)


def cmd_solve(state, args):
    """Solve the loaded system."""
    print("  'solve' is not implemented yet.")


def cmd_plot(state, args):
    """Plot the solution."""
    print("  'plot' is not implemented yet.")


def cmd_display(state, args):
    """Compile a diagram .tex to a PDF and open it."""
    default = state.diagram_path if state.diagram_path and state.diagram_path.exists() else None
    hint = f", Enter for '{default.name}'" if default else ""
    prompt = f"Which .tex file should I compile? ('ls' to list{hint})\n> "
    while True:
        try:
            raw = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if not raw.strip() and default:
            path = default
            break
        if raw.strip().lower() == "ls":
            files = sorted(Path.cwd().glob("*.tex"))
            print(("  " + "\n  ".join(f.name for f in files)) if files else "  (no .tex files here)")
            print()
            continue
        try:
            path = Draw.parse_existing_tex(raw)
            break
        except ValueError as exc:
            print(f"  ✗ {exc} Please try again.\n")

    print(f"  Compiling '{path}' ...")
    try:
        pdf = Draw.compile_document(path)
    except ValueError as exc:
        print(f"  ✗ {exc}")
        return
    print(f"  ✓ Built '{pdf}'")
    try:
        Draw.open_document(pdf)
    except ValueError as exc:
        print(f"  ✗ {exc}")


def cmd_name(state, args):
    """Show or change the system's name."""
    print("  'name' is not implemented yet.")


def cmd_draw(state, args):
    """Write a TikZ diagram of the loaded system to a .tex file."""
    if state.system is None:
        print("  ✗ No system loaded. Run 'input' first.")
        return
    print()
    print(Draw.render_tikz(state.system))
    print()
    path = Draw.save_document(Draw.build_document(state.system))
    if path is not None:
        state.diagram_path = path
        print(f"  ✓ Diagram saved to '{path}'")


def parse_parameter_assignment(raw):
    if "=" not in raw:
        raise ValueError("Use the form name=value, e.g. p1=2.5.")
    name, _, value = raw.partition("=")
    name = Input.parse_parameter_name(name)
    value = value.strip()
    try:
        value = float(value)
    except ValueError:
        raise ValueError(f"'{value}' is not a number.") from None
    return name, value


def print_parameters(parameters):
    if not parameters:
        print("  (none set)")
        return
    for name in sorted(parameters, key=lambda n: int(n[1:])):
        print(f"  {name} = {parameters[name]}")


def cmd_parameters(state, args):
    """View or set the parameter values stored in a system file."""
    prompt = "Which system file holds the parameters? (e.g. ivp.json, or 'ls' to list)\n> "
    while True:
        try:
            raw = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if raw.strip().lower() == "ls":
            files = sorted(Path.cwd().glob("*.json"))
            print(("  " + "\n  ".join(f.name for f in files)) if files else "  (no .json files here)")
            print()
            continue
        try:
            path = Input.parse_input_path(raw)
            parameters = Input.load_parameters(path)
        except ValueError as exc:
            print(f"  ✗ {exc} Please try again.\n")
            continue
        break

    print(f"\nCurrent parameters in '{path}':")
    print_parameters(parameters)
    print("\nSet a value (e.g. p1=2.5), 'ls' to list current values, or 'done' to finish:")

    updates = {}
    while True:
        try:
            raw = input("> ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            break
        command = raw.strip().lower()
        if command == "done":
            break
        if command == "ls":
            print_parameters({**parameters, **updates})
            continue
        try:
            name, value = parse_parameter_assignment(raw)
        except ValueError as exc:
            print(f"  ✗ {exc}")
            continue
        updates[name] = value
        print(f"  ✓ {name} = {value}")

    if not updates:
        print("No changes made.")
        return

    if Input.save_parameters(path, updates):
        print(f"  ✓ Parameters saved to '{path}'")


COMMANDS = {
    "help": cmd_help,
    "quit": cmd_quit,
    "clear": cmd_clear,
    "input": cmd_input,
    "solve": cmd_solve,
    "plot": cmd_plot,
    "display": cmd_display,
    "name": cmd_name,
    "parameters": cmd_parameters,
    "draw": cmd_draw,
}
