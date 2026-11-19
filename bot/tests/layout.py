"""Where the tests find the code's own files: the bot/ folder, the package, the dashboard's pages, deploy/."""
import os
import shutil

TESTS = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.dirname(TESTS)                                  # the bot/ folder: README.md, .env.example, state/
PACKAGE = os.path.join(BOT, "kalshi_bot")
STATIC = os.path.join(PACKAGE, "web", "static")               # dashboard.html, tape.html and their .js and .css
DEPLOY = os.path.join(BOT, "deploy")

# What `python bot.py` needs to run: the front door and the package's core. fast_entry.py is left out on purpose, so a
# copy runs the way the bot does without it (every window normal), and nothing else rides along.
CORE = ("__init__.py", "bot.py", "kalshi.py", "ledger.py", "market.py")


def copy_code(dest):
    """A copy of the bot's code in `dest` (a folder that exists): bot.py and kalshi_bot/ with CORE in it. Its state/
    is dest/state, so nothing it does reaches the real one. Returns the copy's kalshi_bot/bot.py, the module itself."""
    shutil.copy(os.path.join(BOT, "bot.py"), dest)
    package = os.path.join(dest, "kalshi_bot")
    os.makedirs(package)
    for name in CORE:
        shutil.copy(os.path.join(PACKAGE, name), package)
    return os.path.join(package, "bot.py")
