from pathlib import Path

PATH = Path("utils/const/libraries")
libraries = PATH.joinpath("list.txt").read_text().strip("\n").split(" ")

__all__ = ["libraries"]
