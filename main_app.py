import Commands

LOGO = r"""
    _____    ______     _____       __
   /  _/ |  / / __ \   / ___/____  / /   _____  _____
   / / | | / / /_/ /   \__ \/ __ \/ / | / / _ \/ ___/
 _/ /  | |/ / ____/   ___/ / /_/ / /| |/ /  __/ /
/___/  |___/_/       /____/\____/_/ |___/\___/_/
"""


def run_loop(state):
    while state.running:
        try:
            raw = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            break

        command, _, args = raw.strip().partition(" ")
        command = command.lower()
        if not command:
            continue

        handler = Commands.COMMANDS.get(command)
        if handler is None:
            print(f"Unknown command '{command}'. Type 'help' for a list.")
            continue

        try:
            handler(state, args.strip())
        except Exception as exc:
            print(f"  ✗ '{command}' failed: {exc}")


def main():
    Commands.clear_terminal()
    print(LOGO)
    print("Type 'help' to see the available commands.")

    state = Commands.AppState()
    run_loop(state)


if __name__ == "__main__":
    main()
