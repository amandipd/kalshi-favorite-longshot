"""Starts the bot: python bot.py [--live] [--env prod] ... (python bot.py --help lists every option).

The code is in the kalshi_bot package beside this file; this is only its front door, so the commands the bot and the
dashboard print (python bot.py --resume, for one) work from this folder.
"""
if __name__ == "__main__":
    from kalshi_bot.bot import cli

    cli()
