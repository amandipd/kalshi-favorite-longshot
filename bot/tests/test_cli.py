"""bot.py's command line, run through main() against a fake Kalshi and a temporary state folder, with the
clock frozen: --status, --halt, --resume, --check, --fund-crypto, --rebase, and starting a dry, demo or prod run.

    python -m pytest tests/test_cli.py -q
"""
import os
import types

import pytest

from kalshi_bot import bot
from test_bot import W, FakeKalshi, fake_bet

NOW = W + 100  # minute 1 of a window: the loop's one step does nothing but settle and write its heartbeat
KEYS = {"KALSHI_API_KEY_ID": "id", "KALSHI_PRIVATE_KEY_PATH": "/keys/k.pem"}


class CliFake(FakeKalshi):
    """FakeKalshi plus what the command line uses: last_error and transfer."""

    def __init__(self):
        super().__init__()
        self.last_error, self.transfers, self.transfer_result = None, [], (200, {"transfer_id": "t-1"})
        self.balance_result, self.position_list = "real", []

    def balance(self):
        return super().balance() if self.balance_result == "real" else self.balance_result

    def positions(self, **p):
        return {"market_positions": self.position_list} if self.position_list is not None else None

    def transfer(self, dollars, from_section, to_section):
        self.transfers.append((dollars, from_section, to_section))
        return self.transfer_result


@pytest.fixture
def cli(tmp_path, monkeypatch):
    fake = CliFake()
    made = []
    cfg = {"KALSHI_ENV": "demo", **KEYS}
    monkeypatch.setattr(bot, "STATE", str(tmp_path))
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=lambda s: None))
    monkeypatch.setattr(bot, "load_env", lambda *a, **k: dict(cfg))
    monkeypatch.setattr(bot, "Kalshi", lambda *a, **k: (made.append((a, k)), fake)[1])
    answers = []
    monkeypatch.setattr("builtins.input", lambda prompt="": answers.pop(0) if answers else pytest.fail(f"unexpected prompt: {prompt}"))
    return types.SimpleNamespace(fake=fake, made=made, cfg=cfg, answers=answers, dir=tmp_path)


def out(capsys):
    return capsys.readouterr().out


def exits(argv):
    with pytest.raises(SystemExit) as e:
        bot.main(argv)
    return str(e.value)


def db_at(cli, name):
    return bot.connect(str(cli.dir / f"{name}.db"))


# ------------------------------------------------------------------ small helpers
def test_state_paths_name_the_mode_and_environment():
    assert bot.state_path(True, "prod").endswith(os.path.join("state", "live-prod.db"))
    assert bot.state_path(False, "demo").endswith(os.path.join("state", "dry-demo.db"))
    assert bot.state_path(False, "prod", paper=True).endswith(os.path.join("state", "paper-prod.db"))


@pytest.mark.parametrize("left, is_broke", [(66.66, True), (66.67, False), (0.0, True), (100.0, False)])
def test_broke_is_when_1_5_percent_is_under_the_1_dollar_minimum(tmp_path, left, is_broke):
    db = bot.connect(str(tmp_path / "x.db"))
    bot.set_start(db, 100.0)
    fake_bet(db, 0, W, False, left - 100.0, settled=W + 1)
    assert bot.broke(db) is is_broke
    fake_bet(db, 1, W, None, None, status="open")
    assert bot.broke(db) is False                        # never while a bet is still riding


def test_status_line_summarises_an_account(tmp_path):
    db = bot.connect(str(tmp_path / "x.db"))
    bot.set_start(db, 100.0)
    assert bot.status_line(db) == "$100.00 settled from $100.00 (+0.0%) · 0 won, 0 lost, 0 open"
    fake_bet(db, 0, W, True, 0.5, settled=W + 1)
    fake_bet(db, 1, W, False, -3.0, settled=W + 2)
    fake_bet(db, 2, W, None, None, status="open")
    assert bot.status_line(db) == "$97.50 settled from $100.00 (-2.5%) · 1 won, 1 lost, 1 open"


# ------------------------------------------------------------------ --status, --halt, --resume
def test_status_with_nothing_yet(cli, capsys):
    bot.main(["--status"])
    text = out(capsys)
    assert text.splitlines()[0] == "not halted"
    assert "next blackout: Fed decision, Wed Oct 28 02:00 PM ET" in text


def test_status_after_the_last_blackout(cli, capsys, monkeypatch):
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: bot.ts("2027-12-09T00:00:00Z"), sleep=lambda s: None))
    bot.main(["--status"])
    assert "no blackouts scheduled" in out(capsys)


def test_status_lists_every_account_that_has_started(cli, capsys):
    live = db_at(cli, "live-prod")
    bot.set_start(live, 100.0)
    fake_bet(live, 0, W, True, 0.5, settled=W + 1)
    fake_bet(live, 1, W, False, -3.0, settled=W + 2)
    fake_bet(live, 2, W, None, None, status="open")
    live.commit()
    bot.set_start(db_at(cli, "dry-demo"), 250.0)
    db_at(cli, "never-started")  # a database that never got a starting balance isn't listed
    bot.main(["--status"])
    lines = out(capsys).splitlines()
    assert "  dry-demo.db      $250.00 settled from $250.00 (+0.0%) · 0 won, 0 lost, 0 open" in lines
    assert "  live-prod.db     $97.50 settled from $100.00 (-2.5%) · 1 won, 1 lost, 1 open" in lines
    assert not any("never-started" in l for l in lines)


def test_halt_stops_everything_and_says_so(cli, capsys):
    bot.main(["--halt", "checking the switch"])
    text = out(capsys)
    assert "HALTED (you): checking the switch" in text
    assert "HALTED since 2026-09-28T16:01:40Z (you): checking the switch" in text
    assert bot.halt_info() == {"ts": "2026-09-28T16:01:40Z", "reason": "checking the switch", "by": "you"}


def test_halt_without_a_reason_says_stopped_by_hand(cli, capsys):
    bot.main(["--halt"])
    assert bot.halt_info()["reason"] == "stopped by hand"


def test_the_kill_switch_works_even_with_an_empty_reason(cli, capsys):
    """`--halt ""` is still a halt: it must never fall through and start the bot instead. (--once only makes a
    regression fail instead of looping forever.)"""
    bot.main(["--halt", "", "--once"])
    assert bot.halt_info() is not None and bot.halt_info()["by"] == "you"
    assert "dry run" not in out(capsys) and cli.made == []  # and it never even built a client


def test_halting_twice_keeps_the_first_reason(cli, capsys):
    bot.main(["--halt", "first"])
    bot.main(["--halt", "second"])
    assert bot.halt_info()["reason"] == "first"


def test_halt_leaves_the_accounts_alone(cli, capsys):
    db = db_at(cli, "live-prod")
    bot.set_start(db, 100.0)
    bot.main(["--halt", "x"])
    assert bot.get_meta(db_at(cli, "live-prod"), "halt_seen") is None


def test_resume_lifts_the_halt_and_re_arms_every_account(cli, capsys):
    db = db_at(cli, "live-prod")
    bot.set_start(db, 100.0)
    fake_bet(db, 0, W, False, -30.0, settled=W + 1)
    db.commit()
    bot.main(["--halt", "why"])
    out(capsys)
    bot.main(["--resume"])
    text = out(capsys)
    assert "resumed (was halted since 2026-09-28T16:01:40Z: why)" in text and "not halted" in text
    assert bot.halt_info() is None
    after = db_at(cli, "live-prod")
    assert float(bot.get_meta(after, "halt_seen")) == NOW and float(bot.get_meta(after, "halt_base")) == 70.0


def test_resume_when_not_halted(cli, capsys):
    bot.main(["--resume"])
    assert "wasn't halted" in out(capsys)


# ------------------------------------------------------------------ --check
def test_check_without_a_key_says_what_to_set(cli):
    cli.fake.authed = False
    assert "needs KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH in .env" in exits(["--check"])


@pytest.mark.parametrize("env, where", [("demo", "demo.kalshi.co"), ("prod", "kalshi.com")])
def test_check_explains_a_balance_it_cant_read(cli, env, where):
    cli.fake.balance_result, cli.fake.last_error = None, "HTTP 401: bad signature"
    msg = exits(["--check", "--env", env])
    assert f"couldn't read the {env} account balance. Kalshi said: HTTP 401: bad signature" in msg
    assert where in msg and f"KALSHI_ENV={env}" in msg


def test_check_treats_a_reply_without_a_balance_as_unreadable(cli):
    cli.fake.balance_result = {"error": "x"}
    assert "couldn't read" in exits(["--check"])


def test_check_shows_the_balance_and_places_nothing(cli, capsys):
    cli.fake.position_list = [{"ticker": "A"}, {"ticker": "B"}]
    bot.main(["--check"])
    text = out(capsys)
    assert ("connected to Kalshi demo: $100.00 in the account, $100.00 of it in the Crypto & Commodities section"
            " these markets trade in · 2 open positions") in text
    assert "needs at least" not in text
    assert cli.fake.orders == [] and cli.fake.transfers == [] and os.listdir(cli.dir) == []  # not even a database


def test_check_warns_when_the_crypto_section_is_too_small_for_a_bet(cli, capsys):
    cli.fake.crypto_cash = "10.0000"
    bot.main(["--check"])
    text = out(capsys)
    assert "$10.00 of it in the Crypto" in text
    assert "The bot needs at least $67 in Crypto & Commodities to place a $1 bet." in text and "--fund-crypto" in text


def test_check_copes_with_positions_it_cant_read(cli, capsys):
    cli.fake.position_list = None
    bot.main(["--check"])
    assert "0 open positions" in out(capsys)


def test_check_uses_the_key_from_env_for_the_environment_asked(cli, capsys):
    bot.main(["--check", "--env", "prod"])
    assert cli.made == [(("prod", "id", "/keys/k.pem"), {})]
    assert "connected to Kalshi prod" in out(capsys)


# ------------------------------------------------------------------ --fund-crypto
def test_fund_crypto_moves_the_whole_default_section_after_a_confirmation(cli, capsys):
    cli.fake.crypto_cash = "0.0039"          # $99.9961 sits in Default
    cli.answers.append("MOVE")
    bot.main(["--fund-crypto"])
    assert cli.fake.transfers == [(99.99, 0, 2)]  # whole cents, rounded down
    text = out(capsys)
    assert "transfer t-1 sent" in text and "python bot.py --check" in text
    assert os.listdir(cli.dir) == []              # it returns before the bot starts


def test_fund_crypto_moves_only_the_amount_asked(cli, capsys):
    cli.fake.crypto_cash = "50.0000"
    cli.answers.append("MOVE")
    bot.main(["--fund-crypto", "25.50"])
    assert cli.fake.transfers == [(25.5, 0, 2)]


def test_fund_crypto_asks_first_and_anything_but_move_cancels(cli, capsys):
    cli.fake.crypto_cash = "50.0000"
    cli.answers.append("yes")
    assert exits(["--fund-crypto"]) == "nothing moved"
    assert cli.fake.transfers == []


def test_fund_crypto_with_yes_doesnt_ask(cli, capsys):
    cli.fake.crypto_cash = "50.0000"
    bot.main(["--fund-crypto", "10", "--yes"])   # any prompt would fail the test
    assert cli.fake.transfers == [(10.0, 0, 2)]


@pytest.mark.parametrize("arg", ["60", "50.01", "0", "-5", "0.004"])
def test_fund_crypto_refuses_amounts_it_cant_move(cli, arg):
    cli.fake.crypto_cash = "50.0000"
    assert "the Default section has $50.00: can't move" in exits(["--fund-crypto", arg, "--yes"])
    assert cli.fake.transfers == []


def test_fund_crypto_with_nothing_in_default(cli):
    cli.fake.crypto_cash = "100.0000"
    assert "the Default section has $0.00: can't move $0.00" in exits(["--fund-crypto", "--yes"])


def test_fund_crypto_reports_a_refused_transfer(cli):
    cli.fake.crypto_cash = "50.0000"
    cli.fake.transfer_result = (400, {"error": "not allowed"})
    assert exits(["--fund-crypto", "--yes"]) == "Kalshi refused the transfer (400): {'error': 'not allowed'}"


def test_fund_crypto_needs_a_working_key(cli):
    cli.fake.authed = False
    assert "needs KALSHI_API_KEY_ID" in exits(["--fund-crypto"])


def test_fund_crypto_targets_whichever_section_kalshi_calls_crypto(cli, monkeypatch):
    cli.fake.crypto_cash = "50.0000"
    monkeypatch.setattr(cli.fake, "exchange_status", lambda: {"exchange_index_statuses": [
        {"exchange_index": 0, "description": "Default"}, {"exchange_index": 7, "description": "Crypto & Commodities"}]})
    bot.main(["--fund-crypto", "5", "--yes"])
    assert cli.fake.transfers == [(5.0, 0, 7)]


# ------------------------------------------------------------------ starting the bot
def test_a_dry_run_needs_no_key_and_starts_from_a_simulated_1000(cli, capsys):
    cli.cfg.pop("KALSHI_API_KEY_ID")
    bot.main(["--once"])
    text = out(capsys)
    assert text.splitlines()[0] == "dry run on demo · $1000.00 settled from $1000.00 (+0.0%) · 0 won, 0 lost, 0 open"
    assert ("1.5% a bet, 10% a window, whole contracts, no cap on an order, skipping 2c+ spreads and late favorites"
            " · next bet about $15.00") in text
    assert cli.made == [(("demo",), {})]                    # a client with no key
    assert os.listdir(cli.dir) == ["dry-demo.db"]
    assert float(bot.get_meta(db_at(cli, "dry-demo"), "heartbeat")) == NOW  # and it ran its one step


def test_the_environment_comes_from_the_flag_then_env_then_demo(cli, capsys):
    bot.main(["--once"])
    bot.main(["--once", "--env", "prod"])
    cli.cfg["KALSHI_ENV"] = "prod"
    bot.main(["--once"])
    del cli.cfg["KALSHI_ENV"]
    bot.main(["--once"])
    assert sorted(os.listdir(cli.dir)) == ["dry-demo.db", "dry-prod.db"]
    assert [m[0][0] for m in cli.made] == ["demo", "prod", "prod", "demo"]


def test_a_bad_environment_is_rejected_by_argparse(cli, capsys):
    with pytest.raises(SystemExit) as e:
        bot.main(["--env", "staging"])
    assert e.value.code == 2 and os.listdir(cli.dir) == []


def test_a_dry_runs_start_never_moves(cli, capsys):
    bot.main(["--once"])
    db = db_at(cli, "dry-demo")
    bot.set_start(db, 100.0)
    db.commit()
    bot.main(["--once"])
    assert bot.get_meta(db_at(cli, "dry-demo"), "start") == "100.0"


def test_live_on_demo_starts_from_the_crypto_section_cash(cli, capsys):
    cli.fake.crypto_cash = "80.0000"
    bot.main(["--live", "--once"])
    assert "LIVE on demo · $80.00 settled from $80.00 (+0.0%) · 0 won, 0 lost, 0 open" in out(capsys).splitlines()
    assert os.listdir(cli.dir) == ["live-demo.db"] and bot.get_meta(db_at(cli, "live-demo"), "start") == "80.0"


def test_live_needs_a_working_key(cli):
    cli.fake.authed = False
    assert "needs KALSHI_API_KEY_ID" in exits(["--live", "--once"])
    assert os.listdir(cli.dir) == []


def test_the_live_start_is_re_read_until_the_first_bet(cli, capsys):
    """A deposit that hadn't cleared at the first start must not stay out of the bankroll for good."""
    cli.fake.crypto_cash = "0.0039"
    bot.main(["--live", "--once"])
    assert bot.get_meta(db_at(cli, "live-demo"), "start") == "0.0039"
    cli.fake.crypto_cash = "100.0000"           # the deposit lands
    bot.main(["--live", "--once"])
    assert bot.get_meta(db_at(cli, "live-demo"), "start") == "100.0"
    db = db_at(cli, "live-demo")
    fake_bet(db, 0, W, None, None, status="open")  # its first bet is placed ...
    db.commit()
    cli.fake.crypto_cash = "200.0000"           # ... so later deposits never change what it bets from
    bot.main(["--live", "--once"])
    assert bot.get_meta(db_at(cli, "live-demo"), "start") == "100.0"


def test_a_new_live_start_resets_the_halt_reference(cli, capsys):
    bot.main(["--live", "--once"])
    db = db_at(cli, "live-demo")
    bot.set_meta(db, "halt_base", 40.0)
    db.commit()
    cli.fake.crypto_cash = "90.0000"
    bot.main(["--live", "--once"])
    assert bot.get_meta(db_at(cli, "live-demo"), "halt_base") is None


def test_live_on_prod_asks_you_to_type_live(cli, capsys):
    cli.answers.append("LIVE")
    bot.main(["--live", "--env", "prod", "--once"])
    assert any(l.startswith("LIVE on prod") for l in out(capsys).splitlines())
    assert cli.answers == []                                 # the prompt was used


@pytest.mark.parametrize("reply", ["", "live", "yes", "LIVE now"])
def test_anything_but_live_doesnt_start_prod(cli, reply):
    cli.answers.append(reply)
    assert exits(["--live", "--env", "prod", "--once"]) == "not started"
    assert not os.path.exists(cli.dir / "live-prod.db") or bot.get_meta(db_at(cli, "live-prod"), "heartbeat") is None  # it never ran a step


def test_yes_skips_the_prod_prompt(cli, capsys):
    bot.main(["--live", "--env", "prod", "--yes", "--once"])   # any prompt would fail the test
    assert any(l.startswith("LIVE on prod") for l in out(capsys).splitlines())


def test_the_prompt_is_only_for_live_on_prod(cli, capsys):
    bot.main(["--live", "--once"])                # demo
    bot.main(["--env", "prod", "--once"])         # a dry run on prod
    assert "LIVE on demo" in out(capsys)


def test_a_halted_bot_says_so_at_the_start(cli, capsys):
    bot.set_halt(NOW - 60, "earlier trouble")
    bot.main(["--once"])
    text = out(capsys)
    assert "HALTED since 2026-09-28T16:00:40Z: earlier trouble. It will log what it would do but place nothing until --resume." in text


# ------------------------------------------------------------------ --paper
def test_a_paper_account_has_its_own_state_and_starts_from_a_simulated_1000(cli, capsys):
    cli.cfg.pop("KALSHI_API_KEY_ID")
    bot.main(["--paper", "--once"])
    text = out(capsys)
    assert text.splitlines()[0] == "paper on demo · $1000.00 settled from $1000.00 (+0.0%) · 0 won, 0 lost, 0 open"
    assert "no stop-losses: it runs until it's broke" in text
    assert os.listdir(cli.dir) == ["paper-demo.db"] and cli.made == [(("demo",), {})]   # no key needed
    assert float(bot.get_meta(db_at(cli, "paper-demo"), "heartbeat")) == NOW


def test_paper_never_goes_live(cli):
    with pytest.raises(SystemExit) as e:
        bot.main(["--paper", "--live"])
    assert e.value.code == 2 and os.listdir(cli.dir) == []


def test_a_paper_account_says_real_money_is_halted_and_carries_on(cli, capsys):
    bot.set_halt(NOW - 60, "earlier trouble")
    out(capsys)
    bot.main(["--paper", "--once"])
    text = out(capsys)
    assert "Real money is halted (earlier trouble). This paper account ignores halts and keeps trading." in text
    assert "place nothing until --resume" not in text


def test_a_broke_paper_account_stops_and_says_how_to_start_again(cli, capsys, monkeypatch):
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=lambda s: pytest.fail("it kept running")))
    db = db_at(cli, "paper-demo")
    bot.set_start(db, 100.0)
    fake_bet(db, 0, W, False, -33.34, settled=W + 1)   # $66.66 left: 1.5% is 99c
    db.commit()
    bot.main(["--paper"])                               # no --once: being broke is what ends it
    text = out(capsys)
    assert "broke: $66.66 left, too little for a $1 bet at 1.5%." in text and "paper-demo.db" in text
    assert bot.get_meta(db_at(cli, "paper-demo"), "heartbeat") is None


def test_a_paper_account_with_a_bet_still_riding_isnt_broke_yet(cli, capsys):
    db = db_at(cli, "paper-demo")
    bot.set_start(db, 100.0)
    fake_bet(db, 0, W, False, -70.0, settled=W + 1)
    fake_bet(db, 1, W, None, None, status="open")      # if it wins, it may be back over $66.67
    db.commit()
    bot.main(["--paper", "--once"])
    assert "broke:" not in out(capsys) and float(bot.get_meta(db_at(cli, "paper-demo"), "heartbeat")) == NOW


def test_a_paper_account_carries_on_after_an_error_but_a_real_one_doesnt(cli, capsys, monkeypatch):
    steps, slept = [], []

    def flaky(self, now):
        steps.append(now)
        raise ValueError("odd reply")

    def _stop():
        raise KeyboardInterrupt

    monkeypatch.setattr(bot.Bot, "step", flaky)
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=lambda s: (slept.append(s), _stop() if len(slept) == 2 else None)))
    with pytest.raises(KeyboardInterrupt):
        bot.main(["--paper"])
    assert len(steps) == 2 and "error, carrying on: ValueError('odd reply')" in out(capsys)
    with pytest.raises(ValueError):
        bot.main(["--once"])                            # a dry or live run still stops on it, as before


def test_the_loop_steps_until_stopped_and_sleeps_between(cli, monkeypatch, capsys):
    slept, steps = [], []
    monkeypatch.setattr(bot, "time", types.SimpleNamespace(monotonic=lambda: 0.0, time=lambda: NOW, sleep=lambda s: (slept.append(s), _stop() if len(slept) == 3 else None)))

    def _stop():
        raise KeyboardInterrupt

    real_step = bot.Bot.step
    monkeypatch.setattr(bot.Bot, "step", lambda self, now: (steps.append(now), real_step(self, now))[1])
    with pytest.raises(KeyboardInterrupt):
        bot.main([])
    assert steps == [NOW] * 3 and slept == [bot.POLL] * 3    # a step, then the rest of the 3 s poll, over and over


# ------------------------------------------------------------------ --rebase: the books, restarted from the cash now
def ledger(cli, losses=(-10.0, -5.08), name="live-demo"):
    """A live ledger that started at $100 and lost $15.08: $84.92 now."""
    db = db_at(cli, name)
    bot.set_start(db, 100.0)
    for i, pnl in enumerate(losses):
        fake_bet(db, i, W, False, pnl, settled=W + 10 + i)
    db.commit()
    return db


def test_rebase_restarts_the_books_from_the_crypto_cash_and_keeps_the_history(cli, capsys):
    db = ledger(cli)
    cli.fake.crypto_cash = "224.9200"
    cli.answers.append("REBASE")
    bot.main(["--rebase"])
    text = out(capsys)
    assert bot.bankroll(db) == pytest.approx(224.92)
    assert float(bot.get_meta(db, "start")) == pytest.approx(240.00)            # as if the $140 had been there all along ...
    assert db.execute("SELECT COUNT(*) FROM bets").fetchone()[0] == 2            # ... with every bet still on the books
    assert bot.status_line(db).startswith("$224.92 settled from $240.00 (-6.3%)")   # so the P&L is still -$15.08
    assert float(bot.get_meta(db, "halt_base")) == pytest.approx(224.92) and float(bot.get_meta(db, "halt_seen")) == NOW
    assert "the demo ledger holds $84.92; Crypto & Commodities holds $224.92" in text
    # demo: no $700 stop, so the line is half the new start (prod's is in test_halt_floor.py)
    assert "rebased: $84.92 -> $224.92, history kept · bets about $3.37 · halts if it falls 35% within 24 hours or reaches $112.46" in text


def test_after_a_rebase_the_halts_measure_from_the_new_books(cli):
    db = ledger(cli)
    cli.fake.crypto_cash = "224.9200"
    bot.main(["--rebase", "--yes"])
    bot.check_halts(db, NOW + 60, True)
    assert bot.halt_info() is None                                               # the old losses don't count against it
    fake_bet(db, 9, W, False, -112.0, settled=NOW + 120)                         # down to $112.92: just over half of $224.92
    bot.check_halts(db, NOW + 121, True)
    assert "within 24 hours" in bot.halt_info()["reason"]                        # (the 24-hour rule fires first: a 49.8% day)


def test_rebase_asks_first_and_anything_but_rebase_cancels(cli, capsys):
    db = ledger(cli)
    cli.fake.crypto_cash = "224.9200"
    cli.answers.append("yes")
    assert exits(["--rebase"]) == "nothing changed"
    assert float(bot.get_meta(db, "start")) == 100.0


def test_rebase_with_yes_doesnt_ask(cli, capsys):
    ledger(cli)
    cli.fake.crypto_cash = "224.9200"
    bot.main(["--rebase", "--yes"])                                              # any prompt would fail the test
    assert "rebased:" in out(capsys)


def test_rebase_waits_for_open_bets_to_settle(cli):
    db = ledger(cli)
    fake_bet(db, 7, W, None, None, status="open")
    db.commit()
    assert exits(["--rebase", "--yes"]) == "it has bets still open: run --rebase once they settle"
    assert float(bot.get_meta(db, "start")) == 100.0


def test_rebase_needs_a_live_ledger_and_never_makes_one(cli):
    assert exits(["--rebase", "--yes"]) == "no demo ledger yet: its first live run starts from the cash in Crypto & Commodities"
    assert not os.path.exists(cli.dir / "live-demo.db")
    bot.connect(str(cli.dir / "live-demo.db"))                                  # a database with no start in it yet
    assert exits(["--rebase", "--yes"]).startswith("no demo ledger yet")


def test_rebase_uses_the_environment_asked_for(cli, capsys):
    prod = ledger(cli, name="live-prod")
    cli.fake.crypto_cash = "90.0000"
    bot.main(["--rebase", "--env", "prod", "--yes"])
    assert bot.bankroll(prod) == pytest.approx(90.0)


def test_rebase_says_when_cash_sits_in_other_sections(cli, capsys):
    ledger(cli)
    cli.fake.crypto_cash = "60.0000"                                             # $40 left in Default
    bot.main(["--rebase", "--yes"])
    assert "$40.00 more is in other sections, which the bot can't bet from" in out(capsys)


def test_rebase_with_nothing_to_change(cli, capsys):
    db = ledger(cli)
    cli.fake.crypto_cash = "84.9200"
    bot.main(["--rebase"])                                                       # no prompt: nothing to confirm
    assert out(capsys).rstrip().endswith("they match: nothing to change")
    assert float(bot.get_meta(db, "start")) == 100.0


def test_rebase_leaves_a_halt_in_place_and_says_so(cli, capsys):
    ledger(cli)
    cli.fake.crypto_cash = "224.9200"
    bot.set_halt(NOW, "by hand", "you")
    bot.main(["--rebase", "--yes"])
    assert "still halted (by hand): it places nothing until python bot.py --resume" in out(capsys)
    assert bot.halt_info()["reason"] == "by hand"


def test_rebase_needs_the_key(cli):
    cli.fake.authed = False
    assert exits(["--rebase"]).startswith("needs KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH")
