import Input
import os

def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")

LOGO = r"""
    _____    ______     _____       __
   /  _/ |  / / __ \   / ___/____  / /   _____  _____
   / / | | / / /_/ /   \__ \/ __ \/ / | / / _ \/ ___/
 _/ /  | |/ / ____/   ___/ / /_/ / /| |/ /  __/ /
/___/  |___/_/       /____/\____/_/ |___/\___/_/
"""

def main():
    clear_terminal()
    print(LOGO)
    