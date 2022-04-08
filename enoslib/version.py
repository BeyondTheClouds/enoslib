from pathlib import Path

THIS_DIR = Path(__file__).parent
__version__ = (THIS_DIR / "version.txt").read_text()
__source__ = "https://gitlab.inria.fr/discovery/enoslib"
__chat__ = "https://framateam.org/enoslib"
__documentation__ = "https://discovery.gitlabpages.inria.fr/enoslib/"
