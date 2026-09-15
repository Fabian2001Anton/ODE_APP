"""Command handlers and registry for the interactive REPL."""

import os
from pathlib import Path

import Input


class AppState:
    """Shared state passed to every command handler."""

    def __init__(self):
        self.system = None
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
    """Show the currently loaded system."""
    print("  'display' is not implemented yet.")


def cmd_name(state, args):
    """Show or change the system's name."""
    print("  'name' is not implemented yet.")


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
}
