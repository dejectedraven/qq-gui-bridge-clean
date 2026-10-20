import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search import main

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--db", "group"] + sys.argv[1:]
    raise SystemExit(main())
