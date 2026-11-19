"""Starts the dashboard: python dashboard.py [--port 8080] [--lan], then open http://localhost:8080.

The code is in kalshi_bot/web beside this file; this is only its front door.
"""
if __name__ == "__main__":
    from kalshi_bot.web.dashboard import cli

    cli()
