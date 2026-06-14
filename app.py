from flask import Flask, render_template, jsonify
from flask import redirect, url_for
import math
import numpy as np
from scipy.stats import norm
import random
from flask import request
import pyttsx3
import threading
import queue
import time
import pythoncom

speech_active = False
_board_lock = threading.Lock()


def speech_worker():
    global speech_active
    # Initialize COM once for the thread
    pythoncom.CoInitialize()

    while True:
        text = speech_queue.get()
        if text is None:
            break

        speech_active = True
        try:
            # Re-initialize the engine for EVERY message
            engine = pyttsx3.init()
            engine.setProperty("rate", 220)
            
            print(f"Speaking: {text}")
            engine.say(text)
            engine.runAndWait()
            
            # Explicitly stop and delete to release system resources
            engine.stop()
            del engine 
            
        except Exception as e:
            print(f"Speech worker error: {e}")
        finally:
            speech_active = False
            speech_queue.task_done()





def speak_text(text):
    speech_queue.put(text)




app = Flask(__name__)

MIN_TICK = 0.01

def black_scholes_price(S, K, T, r, vol, option_type='call'):
    d1 = (math.log(S / K) + (r + 0.5 * vol**2) * T) / (vol * math.sqrt(T))
    d2 = d1 - vol * math.sqrt(T)

    if option_type == 'call':
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return round(price, 2)


def black_scholes_delta(S, K, T, r, vol, option_type='call'):
    d1 = (math.log(S / K) + (r + 0.5 * vol**2) * T) / (vol * math.sqrt(T))
    if option_type == 'call':
        return round(float(norm.cdf(d1)), 4)
    else:
        return round(float(norm.cdf(d1) - 1), 4)

def generate_opening_board():
    K = float(np.random.choice(range(30, 105, 5)))
    #tick_size = float(np.random.choice([2.5, 5]))
    tick_size = 5

    S = float(K + round(np.random.uniform(-tick_size / 2, tick_size / 2), 2))
    stock_edge = round(np.random.uniform(0, 0.1), 2)
    T = np.random.uniform(0.2, 0.8)
    r = 0.001
    vol = np.random.uniform(0.1, 0.4)

    strikes = [round(K + tick_size * i, 2) for i in range(-2, 3)]
    highlight = {
        "strike": random.choice(strikes),
        "side": random.choice(["call", "put"])
    }


    # Answers mapped by strike
    answers = {}
    for strike in strikes:
        answers[strike] = {
            "call": black_scholes_price(S, strike, T, r, vol, "call"),
            "put": black_scholes_price(S, strike, T, r, vol, "put")
        }

    rc = round(K - K * math.exp(-r * T), 2)
    atm_straddle = round(answers[K]["call"] + answers[K]["put"], 2)

    if random.choice([True, False]):
        cs = round(answers[K]["call"] - answers[K + tick_size]["call"], 2)
        cs_ticks = (K,K+tick_size)
        ps = round(answers[K]["put"] - answers[K - tick_size]["put"], 2)
        ps_ticks = (K - tick_size, K)
    else:
        cs = round(answers[K - tick_size]["call"] - answers[K]["call"], 2)
        cs_ticks = (K - tick_size, K)
        ps = round(answers[K + tick_size]["put"] - answers[K]["put"], 2)
        ps_ticks = (K, K + tick_size)

    # B/W always on lowest strike, P&S always on highest strike
    bw_strike     = K - 2 * tick_size
    p_and_s_strike = K + 2 * tick_size
    bw       = round(answers[bw_strike]["put"]      + rc, 2)
    bw_ticks = bw_strike
    p_and_s       = round(answers[p_and_s_strike]["call"] - rc, 2)
    p_and_s_ticks = p_and_s_strike

    # Deltas for all five strikes (fixed for lifetime of the board)
    bw_delta           = black_scholes_delta(S, bw_strike,      T, r, vol, 'call')
    bw_put_delta       = black_scholes_delta(S, bw_strike,      T, r, vol, 'put')
    atm_call_delta     = black_scholes_delta(S, K,              T, r, vol, 'call')
    atm_put_delta      = black_scholes_delta(S, K,              T, r, vol, 'put')
    p_and_s_delta      = black_scholes_delta(S, p_and_s_strike, T, r, vol, 'put')
    p_and_s_call_delta = black_scholes_delta(S, p_and_s_strike, T, r, vol, 'call')

    # Inside strikes: the two strikes adjacent to ATM (not the exact middle K)
    inside_low_strike  = K - tick_size   # bw_strike + tick_size
    inside_high_strike = K + tick_size   # p_and_s_strike - tick_size

    # Signed deltas for inside-strike options (call +, put -)
    inside_low_call_delta  = black_scholes_delta(S, inside_low_strike,  T, r, vol, 'call')
    inside_low_put_delta   = black_scholes_delta(S, inside_low_strike,  T, r, vol, 'put')
    inside_high_call_delta = black_scholes_delta(S, inside_high_strike, T, r, vol, 'call')
    inside_high_put_delta  = black_scholes_delta(S, inside_high_strike, T, r, vol, 'put')

    # Spread-correlated flow bias for inside-strike options.
    # Randomly pick a spread direction for this board so that flow tends to
    # look like customers trading call/put spreads between adjacent strikes.
    # Bullish spread: bid K-tick call, offer K+tick call, bid K-tick put, offer K+tick put.
    _spread_bullish = random.choice([True, False])
    def _spread_bias(preferred):
        # preferred is "buying" or "selling"; apply a 55/25/20 weight so the
        # bias is present but not deterministic.
        return random.choices(
            ["buying", "selling", "random"],
            weights=[55, 25, 20] if preferred == "buying" else [25, 55, 20]
        )[0]

    # First info line: always the ATM straddle
    first_info_key = K
    first_info = f"{K} straddle: {atm_straddle}"

    stock_size = random.choice([20,30,30,50,50,75,100,150])
    impact_function = round(float(np.random.uniform(0.005, 0.05) * 0.8), 4)
    rand_factor = float(np.random.uniform(0.5, 1.5))

    # Spread: 1-3 cents wide, weighted toward tighter
    full_spread_ticks = random.choices(
        [1, 2, 3],
        weights=[10, 30, 25]
    )[0]
    spread = full_spread_ticks * MIN_TICK
    half_spread = spread / 2.0
    bid   = round_to_cent(S - math.floor(full_spread_ticks / 2) * MIN_TICK)
    offer = round_to_cent(bid + spread)
    start_width     = half_spread
    start_width_raw = half_spread
    board = {
        "strikes": sorted(strikes),
        "stock_size": stock_size,
        "stock_num": S,
        "initial_stock_num": S,
        'rc_num': rc,
        'stock_edge': stock_edge,
        "impact_function": impact_function,
        "rand_factor": rand_factor,
        "start_width_raw": start_width_raw,
        "start_width": start_width,
        "initial_bid": bid,
        "initial_offer": offer,
        "target_spread": round(2 * start_width, 2),
        "stock_spread": {
            "bid": bid,
            "offer": offer,
            "bid_size": stock_size,
            "offer_size": stock_size
        },
        "rc": f"r/c: {rc}",
        "info": [text for _, text in sorted([
            (bw_strike,       f"{bw_ticks} B/W: {bw}"),
            (cs_ticks[0],     f"{cs_ticks[0]}/{cs_ticks[1]} CS: {cs}"),
            (ps_ticks[0],     f"{ps_ticks[0]}/{ps_ticks[1]} PS: {ps}"),
            (first_info_key,  first_info),
            (p_and_s_strike,  f"{p_and_s_ticks} P&S: {p_and_s}"),
        ], key=lambda x: x[0])],
        "bw":             bw,
        "bw_strike":      bw_strike,
        "bw_delta":           bw_delta,
        "bw_put_delta":       bw_put_delta,
        "atm_call_delta":     atm_call_delta,
        "atm_put_delta":      atm_put_delta,
        "p_and_s":            p_and_s,
        "p_and_s_strike":     p_and_s_strike,
        "p_and_s_delta":      p_and_s_delta,
        "p_and_s_call_delta": p_and_s_call_delta,
        "inside_low_strike":       inside_low_strike,
        "inside_high_strike":      inside_high_strike,
        "inside_low_call_delta":   inside_low_call_delta,
        "inside_low_put_delta":    inside_low_put_delta,
        "inside_high_call_delta":  inside_high_call_delta,
        "inside_high_put_delta":   inside_high_put_delta,
        "answers": answers,
        "T": T,
        "r": r,
        "vol": vol,
        "highlight": highlight,
        "direction_bias": random.choice(["bid", "offer"]),
        "direction_strength": random.uniform(0.5,0.5),
        # Per-instrument flow bias (buying / selling / random), fixed for board lifetime.
        # Affects the 80/20 or 50/50 side split in order generators.
        "flow_bias": {
            **{f"{int(s)} combo": random.choice(["buying", "selling", "random"])
               for s in sorted(strikes)},
            # ITM options: equal 1/3 chance of each bias
            f"{int(bw_strike)} call":      random.choice(["buying", "selling", "random"]),
            f"{int(p_and_s_strike)} put":  random.choice(["buying", "selling", "random"]),
            # OTM options: 40% buying / 40% selling / 20% random
            f"{int(p_and_s_strike)} call": random.choices(["buying", "selling", "random"], weights=[40, 40, 20])[0],
            f"{int(bw_strike)} put":       random.choices(["buying", "selling", "random"], weights=[40, 40, 20])[0],
            # Inside-strike options: spread-correlated bias to simulate call/put spread flow.
            # Bullish spread → bid lower call/put, offer higher call/put (and vice-versa).
            f"{int(inside_low_strike)} call":  _spread_bias("buying"  if _spread_bullish else "selling"),
            f"{int(inside_high_strike)} call": _spread_bias("selling" if _spread_bullish else "buying"),
            f"{int(inside_low_strike)} put":   _spread_bias("buying"  if _spread_bullish else "selling"),
            f"{int(inside_high_strike)} put":  _spread_bias("selling" if _spread_bullish else "buying"),
            # ATM options: equal 1/3 chance of each bias
            f"{int(K)} call": random.choice(["buying", "selling", "random"]),
            f"{int(K)} put":  random.choice(["buying", "selling", "random"]),
        },
    }

    board["ladder_levels"]           = generate_ladder_levels(bid, offer)
    board["best_bid"]                = bid
    board["best_offer"]              = offer
    board["customer_resting_orders"] = []

    # ── Market dynamics — default matches UI drift slider at "Very high" (level=0.75) ──
    _lv         = 0.75
    tick_vol    = 0.001  * (2000.0  ** _lv)   # ≈ 0.299  random-walk speed (ticks/√s)
    drift_sigma = 0.0001 * (30000.0 ** _lv)   # ≈ 0.228  OU drift innovation
    drift_alpha = 10.0   * (0.01    ** _lv)   # ≈ 0.316  mean-reversion speed
    board["dynamics"] = {
        "fair_mid":    (bid + offer) / 2.0,
        "drift":       0.0,   # start with no directional bias
        "tick_vol":    tick_vol,
        "drift_alpha": drift_alpha,
        "drift_sigma": drift_sigma,
        "half_spread": half_spread,
        "enabled":     True,
        "last_update": None,
    }

    return board


def round_to_cent(value):
    return round(round(value / MIN_TICK) * MIN_TICK, 2)


# ─── Stock ladder helpers ──────────────────────────────────────────────────────

def _sparse_level_size():
    """Sparse order-book size: ~35 % empty, rest lognormal with irregular (non-round) sizes."""
    if random.random() < 0.35:
        return 0
    size = int(float(np.random.lognormal(mean=6.5, sigma=0.8)))
    return max(47, min(size, 15000))


def _random_lot():
    """Small, irregular lot for churn additions — looks like a real inbound order."""
    return int(float(np.random.lognormal(mean=5.2, sigma=0.75)))


def _empty_level():
    return {"market_bid": 0, "market_offer": 0,
            "user_buy": 0, "user_sell": 0, "filled_buy": 0, "filled_sell": 0}


def generate_ladder_levels(best_bid, best_offer, n_levels=30):
    """Generate sparse fake liquidity for the stock order-book ladder."""
    levels = {}
    for i in range(n_levels):
        bid_price = round_to_cent(best_bid - i * MIN_TICK)
        lvl = _empty_level()
        lvl["market_bid"] = _sparse_level_size()
        levels[bid_price] = lvl

        offer_price = round_to_cent(best_offer + i * MIN_TICK)
        if offer_price not in levels:
            lvl = _empty_level()
            lvl["market_offer"] = _sparse_level_size()
            levels[offer_price] = lvl

    return levels


def _update_ladder_best_prices(board):
    """Recalculate best_bid / best_offer from the current ladder state."""
    levels = board["ladder_levels"]
    offer_levels = [p for p, d in levels.items() if d["market_offer"] + d["user_sell"] > 0]
    bid_levels   = [p for p, d in levels.items() if d["market_bid"]  + d["user_buy"]  > 0]
    if offer_levels:
        board["best_offer"] = min(offer_levels)
    if bid_levels:
        board["best_bid"] = max(bid_levels)
    board["stock_spread"]["bid"]   = board["best_bid"]
    board["stock_spread"]["offer"] = board["best_offer"]


def execute_ladder_order(board, side, qty, limit):
    """Execute a limit order against the ladder book."""
    levels    = board["ladder_levels"]
    remaining = qty
    fills     = []

    if side == "buy":
        while remaining > 0:
            # Only fill against offer levels at or above the current best offer.
            # Stale market_offer entries that drifted below the bid must not fill
            # passive orders placed in the bid zone.
            offer_with_vol = [p for p, d in levels.items()
                              if d["market_offer"] > 0 and p >= board["best_offer"]]
            if not offer_with_vol:
                break
            best_p = min(offer_with_vol)
            if best_p > limit:
                break
            available = levels[best_p]["market_offer"]
            fill = min(remaining, available)
            levels[best_p]["market_offer"] -= fill
            levels[best_p]["filled_buy"]   += fill
            remaining -= fill
            fills.append({"price": best_p, "qty": fill})

        if remaining > 0:
            p = round_to_cent(limit)
            if p not in levels:
                levels[p] = {
                    "market_bid": 0, "market_offer": 0,
                    "user_buy": 0, "user_sell": 0,
                    "filled_buy": 0, "filled_sell": 0,
                }
            levels[p]["user_buy"] += remaining

    elif side == "sell":
        while remaining > 0:
            # Only fill against bid levels at or below the current best bid.
            bids_with_vol = [p for p, d in levels.items()
                             if d["market_bid"] > 0 and p <= board["best_bid"]]
            if not bids_with_vol:
                break
            best_p = max(bids_with_vol)
            if best_p < limit:
                break
            available = levels[best_p]["market_bid"]
            fill = min(remaining, available)
            levels[best_p]["market_bid"]    -= fill
            levels[best_p]["filled_sell"]   += fill
            remaining -= fill
            fills.append({"price": best_p, "qty": fill})

        if remaining > 0:
            p = round_to_cent(limit)
            if p not in levels:
                levels[p] = {
                    "market_bid": 0, "market_offer": 0,
                    "user_buy": 0, "user_sell": 0,
                    "filled_buy": 0, "filled_sell": 0,
                }
            levels[p]["user_sell"] += remaining

    else:
        return {"ok": False, "message": "Unknown side"}

    _update_ladder_best_prices(board)

    total_filled = sum(f["qty"] for f in fills)

    # ── User-trade market impact ───────────────────────────────────────────────
    # Buying stock pushes fair_mid (the quoted ladder center) up; selling pushes
    # it down.  This is the price-discovery mechanism: trading in the correct
    # direction relative to the hidden fair (stock_num) closes the gap opened by
    # options/combo flow.  Magnitude mirrors the options impact formula.
    if total_filled > 0:
        dyn = board.get("dynamics")
        if dyn:
            hidden_fair   = board["stock_num"]
            avg_fill_price = sum(f["price"] * f["qty"] for f in fills) / total_filled
            # Good-direction trade (buy below fair, sell above fair): market makers
            # are just passively providing liquidity → no direct fair_mid push.
            # Bad-direction trade (buy above fair, sell below fair): market makers
            # treat the aggression as a signal → small fair_mid move confirms their view.
            is_bad = (avg_fill_price > hidden_fair) if side == "buy" else (avg_fill_price < hidden_fair)
            if is_bad:
                impact = (total_filled / board["stock_size"]) * board["impact_function"] * 0.03
                dyn["fair_mid"] += impact if side == "buy" else -impact

    if total_filled > 0:
        avg_price = round(sum(f["price"] * f["qty"] for f in fills) / total_filled, 4)
        verb = "Bought" if side == "buy" else "Sold"
        msg  = f"{verb} {total_filled:,} @ {avg_price:.2f}"
        if remaining > 0:
            msg += f", {remaining:,} resting @ {limit:.2f}"
    elif remaining > 0:
        action = "Buy" if side == "buy" else "Sell"
        msg = f"{action} {remaining:,} resting @ {limit:.2f}"
    else:
        msg = "No fill"

    return {
        "ok":     True,
        "fills":  fills,
        "filled": total_filled,
        "remaining": remaining,
        "message": msg,
    }


# ─── Dynamic market ────────────────────────────────────────────────────────────

def _churn_ladder_liquidity(board):
    """Simulate intra-tick market activity: partial trades eat size, new orders add size."""
    levels    = board["ladder_levels"]
    best_bid  = board["best_bid"]
    best_offer = board["best_offer"]

    for price, data in levels.items():
        # ── Bid side ──────────────────────────────────────────────────────────
        if data["market_bid"] > 0:
            r = random.random()
            if r < 0.10:
                # A trade hits this level, eating an irregular chunk
                pct   = random.uniform(0.04, 0.30)
                eaten = max(1, int(data["market_bid"] * pct))
                # Keep inside bid alive; outer levels can drain to zero
                if price == best_bid:
                    data["market_bid"] = max(_random_lot(), data["market_bid"] - eaten)
                else:
                    data["market_bid"] = max(0, data["market_bid"] - eaten)
            elif r < 0.16:
                # A new limit order arrives at this level
                data["market_bid"] = min(data["market_bid"] + _random_lot(), 25000)

        # ── Offer side ────────────────────────────────────────────────────────
        if data["market_offer"] > 0:
            r = random.random()
            if r < 0.10:
                pct   = random.uniform(0.04, 0.30)
                eaten = max(1, int(data["market_offer"] * pct))
                if price == best_offer:
                    data["market_offer"] = max(_random_lot(), data["market_offer"] - eaten)
                else:
                    data["market_offer"] = max(0, data["market_offer"] - eaten)
            elif r < 0.16:
                data["market_offer"] = min(data["market_offer"] + _random_lot(), 25000)


def _apply_market_update(board):
    """Advance the simulated market by one time-step (called by background worker)."""
    dyn = board.get("dynamics")
    if not dyn or not dyn.get("enabled", True):
        return

    # Simulate active trading even when the NBBO hasn't moved yet
    _churn_ladder_liquidity(board)

    now = time.time()
    if dyn["last_update"] is None:
        dyn["last_update"] = now
        return

    dt = min(now - dyn["last_update"], 2.0)   # cap: don't blow up after a long pause
    dyn["last_update"] = now
    if dt <= 0:
        return

    # ── Update drift (OU process, mean-reverts to 0) ──────────────────────────
    dyn["drift"] += (
        -dyn["drift_alpha"] * dyn["drift"] * dt
        + float(np.random.normal(0, dyn["drift_sigma"] * math.sqrt(dt)))
    )

    # ── Advance both quoted price and hidden fair by the same random step ────
    # This keeps them in sync during normal drift while allowing options impact
    # (which moves stock_num only) to create a persistent gap that the user
    # must close by trading stock.
    drift_delta = (
        dyn["drift"] * MIN_TICK * dt
        + float(np.random.normal(0, dyn["tick_vol"] * MIN_TICK * math.sqrt(dt)))
    )

    # ── Customer resting order resistance ────────────────────────────────────
    # Large make-market orders that did not cross create a floor (bid) or
    # ceiling (offer) at their implied stock price.  This models market
    # participants needing to absorb that liquidity before fair_mid can move
    # through the level.  stock_num (the hidden fair) always drifts freely;
    # only fair_mid (the displayed quoted price) is damped.
    #
    # Resistance = size / stock_size, mapped smoothly to [0, 1) via the
    # Michaelis–Menten function:  resist = ratio / (ratio + 1).
    # A 40× stock_size order gives resist ≈ 0.976, slowing movement by ~97 %.
    # The order is worked through at 1.5 % per tick (good-to-fair) or 4 % per
    # tick (bad-to-fair / adverse selection) whenever it is being tested.
    cust_orders = board.setdefault("customer_resting_orders", [])
    for _o in list(cust_orders):                         # age / expire
        _o["age_ticks"] += 1
        if _o["age_ticks"] > _o["max_ticks"] or _o["remaining"] <= 0:
            cust_orders.remove(_o)

    drift_fair = drift_delta    # will be damped if resistance > 0
    if drift_delta != 0.0 and cust_orders:
        cur_fair     = dyn["fair_mid"]
        prop_fair    = cur_fair + drift_delta
        hidden_fair  = board["stock_num"]
        ref_size     = max(float(board["stock_size"]), 1.0)
        total_resist = 0.0
        for _o in cust_orders:
            if _o["remaining"] <= 0:
                continue
            p = _o["price"]
            # Floor order resists downward movement; ceiling resists upward
            in_path = (
                (_o["side"] == "bid"   and drift_delta < 0 and prop_fair < p <= cur_fair) or
                (_o["side"] == "offer" and drift_delta > 0 and cur_fair <= p < prop_fair)
            )
            if not in_path:
                continue
            ratio        = _o["remaining"] / ref_size
            resist       = ratio / (ratio + 1.0)        # smooth approach to 1
            total_resist = max(total_resist, resist)
            # Work through the order a fraction at a time
            is_good = (
                (_o["side"] == "bid"   and p <= hidden_fair) or  # bid at/below fair
                (_o["side"] == "offer" and p >= hidden_fair)      # offer at/above fair
            )
            fill_rate   = 0.015 if is_good else 0.1
            fill_chunk  = max(1, int(_o["remaining"] * fill_rate))
            _o["remaining"] = max(0, _o["remaining"] - fill_chunk)
        drift_fair = drift_delta * (1.0 - total_resist)

    dyn["fair_mid"]    += drift_fair
    board["stock_num"] += drift_delta   # hidden fair always drifts at full speed

    # Very slow automatic convergence of the quoted price toward the hidden fair.
    # Rate 0.003/s → half-life ~231 s; the gap is ~96 % intact after 15 s, giving
    # the user ample time to act before the market self-corrects.
    gap = board["stock_num"] - dyn["fair_mid"]
    dyn["fair_mid"] += gap * 0.003 * dt

    new_fair      = dyn["fair_mid"]
    half_spread   = dyn["half_spread"]
    new_best_bid  = round_to_cent(new_fair - math.floor(half_spread / MIN_TICK + 0.5) * MIN_TICK)
    new_best_offer = round_to_cent(new_best_bid + round(half_spread * 2 / MIN_TICK) * MIN_TICK)

    old_best_bid   = board["best_bid"]
    old_best_offer = board["best_offer"]

    if new_best_bid == old_best_bid and new_best_offer == old_best_offer:
        return   # price hasn't moved a full tick yet

    levels = board["ladder_levels"]

    # ── Clear market quotes on levels that fell into the spread gap ───────────
    for price, data in levels.items():
        if new_best_bid < price < new_best_offer:
            data["market_bid"]   = 0
            data["market_offer"] = 0

    # ── Clear stale crossed levels ────────────────────────────────────────────
    # When the market moves, old offer entries can end up at bid-side prices
    # and old bid entries at offer-side prices.  Leaving them causes passive
    # orders placed in the bid/offer zone to fill instantly against ghost volume.
    for price, data in levels.items():
        if price <= new_best_bid and data["market_offer"] > 0:
            data["market_offer"] = 0
        if price >= new_best_offer and data["market_bid"] > 0:
            data["market_bid"] = 0

    # ── Ensure inside bid has volume ──────────────────────────────────────────
    if new_best_bid not in levels:
        lvl = _empty_level()
        lvl["market_bid"] = _sparse_level_size() or _random_lot()
        levels[new_best_bid] = lvl
    elif levels[new_best_bid]["market_bid"] == 0:
        levels[new_best_bid]["market_bid"] = _sparse_level_size() or _random_lot()

    # ── Ensure inside offer has volume ────────────────────────────────────────
    if new_best_offer not in levels:
        lvl = _empty_level()
        lvl["market_offer"] = _sparse_level_size() or _random_lot()
        levels[new_best_offer] = lvl
    elif levels[new_best_offer]["market_offer"] == 0:
        levels[new_best_offer]["market_offer"] = _sparse_level_size() or _random_lot()

    # ── Generate any new outer levels as the book shifts ─────────────────────
    N_LEVELS = 30
    for i in range(N_LEVELS):
        bp = round_to_cent(new_best_bid  - i * MIN_TICK)
        if bp not in levels:
            lvl = _empty_level()
            lvl["market_bid"] = _sparse_level_size()
            levels[bp] = lvl
        op = round_to_cent(new_best_offer + i * MIN_TICK)
        if op not in levels:
            lvl = _empty_level()
            lvl["market_offer"] = _sparse_level_size()
            levels[op] = lvl

    # ── Direction-aware resting order fills ──────────────────────────────────
    # Two fill mechanisms are unified here, both keyed to the hidden true fair
    # (stock_num) rather than the quoted ladder centre.
    #
    # Fills are always capped to a chunk anchored on stock_size so that larger
    # user orders are absorbed over many ticks rather than in one event.
    # This mirrors the customer-resting-order resistance system.
    #
    # Chunk formulas (per 500 ms tick):
    #   bad-cross  : stock_size × min(0.50, 0.10 + ticks_bad × 0.10)
    #   bad-spont  : stock_size × min(0.25, 0.03 + ticks_bad × 0.06)
    #   good-cross : stock_size × 0.05   (market makers nibble, never lift whole)
    #
    # GOOD-DIRECTION orders (buy ≤ fair, sell ≥ fair):
    #   Market makers back off.  Only filled when the quoted price reaches the
    #   level AND a 12 % per-tick probability fires.  Chunk is small (~5 % of
    #   stock_size), so a large well-priced order takes many ticks to fill.
    #
    # BAD-DIRECTION orders (buy > fair, sell < fair):
    #   (a) Market crosses the order → chunk fill, sized by adverseness.
    #   (b) Spontaneous adverse-selection by informed algos → probability gate
    #       (25 % per tick of adverse distance) then a smaller chunk fill.
    hidden_fair = board["stock_num"]
    ref_size    = max(1.0, float(board["stock_size"]))

    for price, data in list(levels.items()):

        # ---- user resting buys ----
        if data["user_buy"] > 0:
            remaining = data["user_buy"]
            if price > hidden_fair + 1e-9:
                ticks_bad = (price - hidden_fair) / MIN_TICK
                # (a) Market moved to/through this price → chunk fill, scaled by adverseness.
                if price >= new_best_offer:
                    cross_rate = min(0.50, 0.10 + ticks_bad * 0.10)
                    fill_qty   = max(1, min(remaining, int(ref_size * cross_rate)))
                    levels[price]["market_offer"] = max(
                        0, levels[price]["market_offer"] - fill_qty)
                    data["filled_buy"] += fill_qty
                    data["user_buy"]   -= fill_qty
                # (b) Spontaneous adverse selection by informed algos.
                elif random.random() < min(1.0, ticks_bad * 0.25):
                    spont_rate = min(0.25, 0.03 + ticks_bad * 0.06)
                    fill_qty   = max(1, min(remaining, int(ref_size * spont_rate)))
                    data["filled_buy"] += fill_qty
                    data["user_buy"]   -= fill_qty
            else:
                # Good trade: buying at or below fair.
                # Market makers back off; small chance of a nibble-sized fill.
                if price >= new_best_offer and random.random() < 0.12:
                    fill_qty = max(1, min(remaining, int(ref_size * 0.05)))
                    levels[price]["market_offer"] = max(
                        0, levels[price]["market_offer"] - fill_qty)
                    data["filled_buy"] += fill_qty
                    data["user_buy"]   -= fill_qty

        # ---- user resting sells ----
        if data["user_sell"] > 0:
            remaining = data["user_sell"]
            if price < hidden_fair - 1e-9:
                ticks_bad = (hidden_fair - price) / MIN_TICK
                # (a) Market moved to/through this price → chunk fill, scaled by adverseness.
                if price <= new_best_bid:
                    cross_rate = min(0.50, 0.10 + ticks_bad * 0.10)
                    fill_qty   = max(1, min(remaining, int(ref_size * cross_rate)))
                    levels[price]["market_bid"] = max(
                        0, levels[price]["market_bid"] - fill_qty)
                    data["filled_sell"] += fill_qty
                    data["user_sell"]   -= fill_qty
                # (b) Spontaneous adverse selection.
                elif random.random() < min(1.0, ticks_bad * 0.25):
                    spont_rate = min(0.25, 0.03 + ticks_bad * 0.06)
                    fill_qty   = max(1, min(remaining, int(ref_size * spont_rate)))
                    data["filled_sell"] += fill_qty
                    data["user_sell"]   -= fill_qty
            else:
                # Good trade: selling at or above fair.
                if price <= new_best_bid and random.random() < 0.12:
                    fill_qty = max(1, min(remaining, int(ref_size * 0.05)))
                    levels[price]["market_bid"] = max(
                        0, levels[price]["market_bid"] - fill_qty)
                    data["filled_sell"] += fill_qty
                    data["user_sell"]   -= fill_qty

    # ── Respect user resting orders before committing BBO ────────────────────
    # User resting bids/offers define hard constraints on the book: no market
    # offer may rest at or below a user bid, and no market bid may rest at or
    # above a user offer.  Without this clamp, a downward fair_mid drift would
    # seed phantom offers below a resting user bid, producing a crossed ladder.
    user_buy_prices  = [p for p, d in levels.items() if d["user_buy"]  > 0]
    user_sell_prices = [p for p, d in levels.items() if d["user_sell"] > 0]

    commit_bid   = new_best_bid
    commit_offer = new_best_offer

    if user_buy_prices:
        user_top_bid = max(user_buy_prices)
        if user_top_bid > commit_bid:
            # Remove any market offers that now sit at or inside the user's bid.
            for price, data in levels.items():
                if data["market_offer"] > 0 and price <= user_top_bid:
                    data["market_offer"] = 0
            commit_bid = user_top_bid
            if commit_offer <= commit_bid:
                commit_offer = round_to_cent(commit_bid + MIN_TICK)
                if commit_offer not in levels:
                    levels[commit_offer] = _empty_level()
                if levels[commit_offer]["market_offer"] == 0:
                    levels[commit_offer]["market_offer"] = _sparse_level_size() or _random_lot()

    if user_sell_prices:
        user_top_offer = min(user_sell_prices)
        if user_top_offer < commit_offer:
            # Remove any market bids that now sit at or inside the user's offer.
            for price, data in levels.items():
                if data["market_bid"] > 0 and price >= user_top_offer:
                    data["market_bid"] = 0
            commit_offer = user_top_offer
            if commit_bid >= commit_offer:
                commit_bid = round_to_cent(commit_offer - MIN_TICK)
                if commit_bid not in levels:
                    levels[commit_bid] = _empty_level()
                if levels[commit_bid]["market_bid"] == 0:
                    levels[commit_bid]["market_bid"] = _sparse_level_size() or _random_lot()

    # ── Commit the new book state ─────────────────────────────────────────────
    board["best_bid"]   = commit_bid
    board["best_offer"] = commit_offer
    board["stock_spread"]["bid"]   = commit_bid
    board["stock_spread"]["offer"] = commit_offer

    # stock_num (hidden fair) and fair_mid (quoted ladder center) are kept in
    # sync via the shared drift_delta above.  Do NOT overwrite stock_num here —
    # options/combo impact writes to stock_num directly to create the gap that
    # user stock trading is meant to close.


def _market_update_worker():
    """Background thread: advances simulated market every 50 ms."""
    while True:
        time.sleep(0.05)
        with _board_lock:
            try:
                _apply_market_update(BOARD)
            except Exception as exc:
                print(f"[market-update] {exc}")


def safe_positive_int(value):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def safe_price(value):
    try:
        return abs(round_to_cent(float(value)))
    except Exception:
        return None


def normal_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1 + math.erf(z))


def generate_level_liquidity(board, level_price, direction):
    sigma = board["impact_function"] * board["stock_size"] / 5
    # Centre liquidity on the quoted ladder price (fair_mid), not the hidden fair
    # (stock_num), so book depth reflects the current displayed market, not the
    # yet-to-be-discovered target.
    quoted_fair = board.get("dynamics", {}).get("fair_mid", board["stock_num"])
    cdf = normal_cdf(level_price, quoted_fair, sigma)
    area = cdf if direction == "buy" else (1.0 - cdf)
    if area > 0.5:
        base = board["stock_size"] * 1.5 * (math.tan(area * math.pi / 2.0) - 1.0)
    else:
        base = 0.0
    noise = float(np.random.normal(loc=0.0, scale=max(1e-9, board["stock_size"])))
    qty = int(round(base + noise))
    return max(0, qty)


def find_next_nonzero_level(board, start_price, step, direction, max_steps=5000):
    price = start_price
    for _ in range(max_steps):
        price = round_to_cent(price + step)
        qty = generate_level_liquidity(board, price, direction=direction)
        if qty > 0:
            return price, qty
    return round_to_cent(price + step), 1


def adjust_opposite_side_after_trade(board, trigger):
    bid = board["stock_spread"]["bid"]
    offer = board["stock_spread"]["offer"]

    current_spread = offer - bid
    if current_spread <= MIN_TICK:
        board["stock_spread"]["bid"] = min(bid, round_to_cent(offer - MIN_TICK))
        board["stock_spread"]["offer"] = max(offer, round_to_cent(board["stock_spread"]["bid"] + MIN_TICK))
        return

    target_spread = board.get("target_spread", 0.02)
    if trigger == "buy":
        desired_bid = offer - target_spread
        mean_move = desired_bid - bid
        move = float(np.random.normal(loc=mean_move, scale=MIN_TICK))
        new_bid = round_to_cent(bid + move)
        board["stock_spread"]["bid"] = min(new_bid, round_to_cent(offer - MIN_TICK))
    elif trigger == "sell":
        desired_offer = bid + target_spread
        mean_move = desired_offer - offer
        move = float(np.random.normal(loc=mean_move, scale=MIN_TICK))
        new_offer = round_to_cent(offer + move)
        board["stock_spread"]["offer"] = max(new_offer, round_to_cent(bid + MIN_TICK))
    else:
        raise ValueError("trigger must be buy or sell")


def execute_stock_trade(board, side, qty, limit):
    if side == "buy":
        if limit < board["stock_spread"]["offer"]:
            return {
                "ok": False,
                "message": f"Buy rejected: limit {limit:.2f} below offer {board['stock_spread']['offer']:.2f}"
            }
        remaining = qty
        traded = 0
        last_price = None
        level_price = board["stock_spread"]["offer"]
        level_qty = int(board["stock_spread"]["offer_size"])
        while remaining > 0 and level_price <= limit:
            fill = min(remaining, level_qty)
            if fill > 0:
                remaining -= fill
                level_qty -= fill
                traded += fill
                last_price = level_price
            if remaining == 0 or level_qty > 0:
                break
            level_price, level_qty = find_next_nonzero_level(board, level_price, step=MIN_TICK, direction="buy")

        board["stock_spread"]["offer"] = level_price
        board["stock_spread"]["offer_size"] = level_qty
        adjust_opposite_side_after_trade(board, trigger="buy")
        board["stock_size"] = int(max(1, round((board["stock_spread"]["bid_size"] + board["stock_spread"]["offer_size"]) / 2.0)))

        return {
            "ok": True,
            "message": f"Bought {traded} stock to {last_price:.2f}" if traded > 0 else "Buy did not trade",
            "traded": traded
        }

    if side == "sell":
        if limit > board["stock_spread"]["bid"]:
            return {
                "ok": False,
                "message": f"Sell rejected: limit {limit:.2f} above bid {board['stock_spread']['bid']:.2f}"
            }
        remaining = qty
        traded = 0
        last_price = None
        level_price = board["stock_spread"]["bid"]
        level_qty = int(board["stock_spread"]["bid_size"])
        while remaining > 0 and level_price >= limit:
            fill = min(remaining, level_qty)
            if fill > 0:
                remaining -= fill
                level_qty -= fill
                traded += fill
                last_price = level_price
            if remaining == 0 or level_qty > 0:
                break
            level_price, level_qty = find_next_nonzero_level(board, level_price, step=-MIN_TICK, direction="sell")

        board["stock_spread"]["bid"] = level_price
        board["stock_spread"]["bid_size"] = level_qty
        adjust_opposite_side_after_trade(board, trigger="sell")
        board["stock_size"] = int(max(1, round((board["stock_spread"]["bid_size"] + board["stock_spread"]["offer_size"]) / 2.0)))

        return {
            "ok": True,
            "message": f"Sold {traded} stock to {last_price:.2f}" if traded > 0 else "Sell did not trade",
            "traded": traded
        }

    return {"ok": False, "message": "Unknown stock side"}

# Spread-relative edge multipliers.  edge = k * half_spread
#   |k| < 1  → implied stock lands *inside* the current spread (passive/resting)
#   |k| ≈ 1  → implied stock touches the spread boundary
#   |k| > 1  → implied stock crosses the spread (immediately actionable)
# Negative k = house edge; positive k = customer advantage.
# k < 0 → aggressive (bid above fair / offer below fair); k > 0 → passive.
# 18 negative + 6 positive = 24 values → 75 % aggressive / 25 % passive.
# Of the 18 negative: 14 have k ≤ -1 (crossing) → ~58 % of all orders cross.
_COMBO_K_LIST = [-4.0, -3.0, -2.5, -2.0, -1.8, -1.5, -1.5, -1.3, -1.2, -1.1,
                 -1.1, -1.0, -1.0, -1.0, -0.9, -0.7, -0.5, -0.3,
                  0.1,  0.3,  0.5,  0.7,  0.9,  0.9]
# OTM customers are more aggressive: the distribution is shifted toward more
# negative k values (i.e. they cross or nearly cross more often).
# OTM orders always price at fair or through fair (k ≤ 0): positive k would
# place a bid below fair / offer above fair, worsening the market.
_OTM_K_LIST   = [-3.5, -2.5, -2.0, -1.8, -1.5, -1.5, -1.3, -1.2, -1.1, -1.0,
                 -0.9, -0.9, -0.8, -0.7, -0.6, -0.5, -0.3, -0.2, -0.1,  0.0]
# Middle-strike options (K±tick, ATM): 75 % aggressive / 25 % passive.
# 15 negative + 5 positive = 20 values. Magnitudes kept moderate (max -1.5).
_MIDDLE_OPTIONS_K_LIST = [-1.5, -1.2, -1.1, -1.0, -0.9, -0.9, -0.8, -0.7,
                          -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, -0.1,
                           0.1,  0.3,  0.5,  0.7,  0.9]
# Opening order: always very aggressive so the user must immediately trade stock.
_OPENING_K_LIST = [-3.0, -2.5, -2.0, -1.8, -1.5]

#_COMBO_K_LIST = _COMBO_K_LIST + [_k * -1 for _k in _COMBO_K_LIST]
# Jacob's lot-size multiplier pool: starting_size * mult, mult in [1.0, 1.5, ..., 10.0]
_COMBO_MULTIPLIERS = np.arange(1.0, 10.5, 0.5)


def _add_customer_resting_order(board, price, side, size):
    """Register a large customer resting order for market-microstructure resistance.

    A 'bid' at price X creates a *floor*: fair_mid resists moving below X.
    An 'offer' at price X creates a *ceiling*: fair_mid resists moving above X.

    Resistance magnitude = size / stock_size, clipped smoothly to [0, 1).
    The order is gradually worked through (filled) each tick it is being tested;
    fill rate is slower for good-to-fair orders and faster for adverse ones.
    Orders expire after ~120 s regardless.

    Only orders with stock-equivalent size >= 0.5 × stock_size are registered;
    smaller orders have negligible effect and are silently ignored.
    """
    if float(size) < board["stock_size"] * 0.5:
        return
    board.setdefault("customer_resting_orders", []).append({
        "price":     round_to_cent(float(price)),
        "side":      side,       # 'bid' = floor, 'offer' = ceiling
        "size":      int(size),
        "remaining": int(size),
        "max_ticks": 480,        # expire after 480 × 250 ms ≈ 120 s
        "age_ticks": 0,
    })


def _clip_stock_fair(board):
    """Clamp stock_num within ±25 ticks of the quoted ladder center (fair_mid).
    The hidden fair is allowed to diverge from the ladder to create price-discovery
    opportunities, but we cap the gap to prevent runaway options pricing."""
    fair   = board["dynamics"]["fair_mid"]
    window = 25 * MIN_TICK
    board['stock_num'] = max(fair - window, min(fair + window, board['stock_num']))


def _apply_combo_impact(board, combo_size, stock_dir):
    """Adjust stock fair when a combo order arrives.

    stock_dir is the stock-equivalent directional signal, NOT the raw customer
    side.  Callers must pre-compute stock_dir from orig_side and fair_combo sign:

      calls-over (fair_combo >= 0):  stock_dir = orig_side
          orig bid  (long call/short put)  → bullish  → 'bid'  → fair UP
          orig offer (short call/long put) → bearish  → 'offer'→ fair DOWN

      puts-over  (fair_combo < 0):   stock_dir = opposite(orig_side)
          orig bid  (long put/short call)  → bearish  → 'offer'→ fair DOWN
          orig offer (short put/long call) → bullish  → 'bid'  → fair UP
    """
    normal_draw = float(np.random.normal(loc=0.5, scale=0.15))
    delta = (combo_size / board['stock_size']) * board['impact_function'] * normal_draw
    if stock_dir == 'bid':      # bullish stock-equivalent → fair moves up
        board['stock_num'] = round_to_cent(board['stock_num'] + delta)
    else:                       # bearish stock-equivalent → fair moves down
        board['stock_num'] = round_to_cent(board['stock_num'] - delta)


def _combo_customer_price(board, strike, side):
    """
    Spread-relative customer price.
      edge = k * half_spread   (k drawn from _COMBO_K_LIST)
      price = base - edge  (bid: customer buys)
              base + edge  (offer: customer sells)
    |k| < 1 → implied stock is inside the spread (passive resting order).
    If price goes negative, flip side and take absolute value.
    """
    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )
    k = float(np.random.choice(_COMBO_K_LIST)) + np.random.normal(loc=-0.3, scale=0.15)
    edge = round_to_cent(k * half_spread)
    base = board['stock_num'] - strike + board['rc_num']
    price = round_to_cent(base - edge) if side == 'bid' else round_to_cent(base + edge)
    if price < 0:
        price = abs(price)
        side = 'offer' if side == 'bid' else 'bid'
    return side, price


def _biased_side(board, key):
    """Return 'bid' or 'offer' weighted by the instrument's flow bias.

    buying  → 80 % bid  / 20 % offer
    selling → 20 % bid  / 80 % offer
    random  → 50 % bid  / 50 % offer  (fallback for unknown keys)
    """
    bias = board.get("flow_bias", {}).get(key, "random")
    r = random.random()
    if bias == "buying":
        return "bid" if r < 0.8 else "offer"
    elif bias == "selling":
        return "offer" if r < 0.8 else "bid"
    else:
        return "bid" if r < 0.5 else "offer"


def generate_combo_order(board):
    _clip_stock_fair(board)
    strike = random.choice(board['strikes'])

    # Jacob's lot size: starting_size * random multiplier, rounded to 10s above 100
    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    combo_size = int(round(board['stock_size'] * mult))
    if combo_size > 100:
        combo_size = int(round(combo_size / 10) * 10)

    side = _biased_side(board, f"{int(strike)} combo")

    # Compute fair and price BEFORE any impact
    fair_combo = board['stock_num'] - strike + board['rc_num']
    orig_side  = side                                # save BEFORE any price-flip
    side, combo_price = _combo_customer_price(board, strike, side)

    # Derive stock_dir (bullish/bearish signal for _apply_combo_impact) from the
    # ORIGINAL side (pre-flip) and the sign of fair_combo.  We must use orig_side
    # rather than the post-flip 'side' because _combo_customer_price only flips
    # when price < 0: for a barely puts-over combo the price may stay positive,
    # leaving 'side' == orig_side even in puts-over territory.
    #
    # calls-over (fair_combo >= 0, strike <= stock approximately):
    #   orig bid  → long call + short put  → synthetic long  → bullish → stock UP
    #   orig offer → short call + long put  → synthetic short → bearish → stock DOWN
    #   stock_dir = orig_side
    #
    # puts-over (fair_combo < 0, strike > stock approximately):
    #   orig bid  → long put + short call   → synthetic short → bearish → stock DOWN
    #   orig offer → short put + long call   → synthetic long  → bullish → stock UP
    #   stock_dir = INVERTED orig_side
    if fair_combo >= 0:
        _stock_dir = orig_side
    else:
        _stock_dir = 'offer' if orig_side == 'bid' else 'bid'

    # Aggressiveness check: for calls-over compare against fair_combo directly;
    # for puts-over both side and price have been normalised to positive so we
    # compare against abs(fair_combo) with inverted inequalities.
    if fair_combo >= 0:
        _aggressive = (side == 'bid' and combo_price > fair_combo) or \
                      (side == 'offer' and combo_price < fair_combo)
    else:
        _abs_fair   = abs(fair_combo)
        _aggressive = (side == 'bid' and combo_price < _abs_fair) or \
                      (side == 'offer' and combo_price > _abs_fair)
    if _aggressive:
        _apply_combo_impact(board, combo_size, _stock_dir)

    fair_combo = board['stock_num'] - strike + board['rc_num']
    combo_price_shift = abs(round(abs(fair_combo) - abs(combo_price), 2))

    if fair_combo < 0:
        implied_stock = strike - combo_price - board['rc_num']
        implied_side = 'bid' if side == 'offer' else 'offer'
    else:
        implied_stock = strike + combo_price - board['rc_num']
        implied_side = side

    if side == 'offer':
        speak = f"Customer offers {combo_size} lots of {int(strike)} combos at {combo_price}"
    else:
        speak = f"Customer bids {combo_price} for {combo_size} lots of {int(strike)} combos"

    return {
        "strike": strike,
        "price": combo_price,
        "size": combo_size,
        "side": side,
        "combo_price_shift": combo_price_shift,
        "sentence": f"{combo_size}x {strike} combo order",
        "implied_stock": round(implied_stock, 2),
        "implied_side": implied_side,
        "speak": speak
    }


def generate_customer_combo_price(board, strike):
    """Price generator for the make-market combo flow.
    Impact is NOT applied here; it is deferred to submit_market so the market
    only reacts after the user has given a quote and a trade occurs.

    Returns (side, price, combo_size, orig_side) where orig_side is the
    customer's intended side BEFORE any price-flip normalisation.  submit_market
    uses orig_side together with the fair_combo sign to derive the correct
    stock-equivalent impact direction (see _apply_combo_impact)."""
    _clip_stock_fair(board)
    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    combo_size = int(round(board['stock_size'] * mult))
    if combo_size > 100:
        combo_size = int(round(combo_size / 10) * 10)

    side = _biased_side(board, f"{int(strike)} combo")
    orig_side = side                               # save before potential flip
    side, price = _combo_customer_price(board, strike, side)
    return side, price, combo_size, orig_side


def _apply_options_impact(board, opt_size, delta, side):
    """
    Adjust stock fair when an options order arrives.
    Impact is scaled by the stock-equivalent: opt_size * |delta|.
    Direction: buying a call (delta>0) or selling a put (delta<0) → fair up.
    """
    stock_equiv = opt_size * abs(delta)
    normal_draw = float(np.random.normal(loc=0.5, scale=0.15))
    impact = (stock_equiv / board['stock_size']) * board['impact_function'] * normal_draw
    # signed_equiv = delta * (+1 if buying, -1 if selling)
    signed = delta * (1.0 if side == 'bid' else -1.0)
    if signed > 0:
        board['stock_num'] = round_to_cent(board['stock_num'] + impact)
    else:
        board['stock_num'] = round_to_cent(board['stock_num'] - impact)


def generate_options_market(board, apply_impact=True):
    """
    Generate a customer options market request for one of the two ITM options:
      - bw_strike call    price = implied_stock - strike + B/W
      - p_and_s_strike put  price = strike - implied_stock + P&S
    When apply_impact=False (make-market flow) the stock fair is not moved;
    impact is deferred to submit_options_market so the market only reacts after
    the user gives a quote and the customer actually trades.
    """
    _clip_stock_fair(board)
    is_call = random.choice([True, False])

    if is_call:
        strike = board['bw_strike']
        delta  = board['bw_delta']
        option_label = f"{int(strike)} call"
    else:
        strike = board['p_and_s_strike']
        delta  = board['p_and_s_delta']
        option_label = f"{int(strike)} put"

    # Size: same multiplier pool as combos
    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    opt_size = int(round(board['stock_size'] * mult))
    if opt_size > 100:
        opt_size = int(round(opt_size / 10) * 10)

    side = _biased_side(board, option_label)

    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )

    # ITM fair via parity (delta ≈ ±1)
    if is_call:
        fair = round_to_cent(board['stock_num'] - strike + board['bw'])
    else:
        fair = round_to_cent(strike - board['stock_num'] + board['p_and_s'])

    # Edge in stock space scaled by |delta|, plus uniform noise
    k           = float(np.random.choice(_COMBO_K_LIST))
    option_edge = round_to_cent(k * half_spread * abs(delta))
    noise       = round_to_cent(float(np.random.uniform(-0.06, 0.02)))
    total_edge  = option_edge + noise
    price       = round_to_cent(fair - total_edge) if side == 'bid' else round_to_cent(fair + total_edge)

    # Recover implied stock via delta approximation
    if abs(delta) > 1e-6:
        implied_stock = round_to_cent(board['stock_num'] + (price - fair) / delta)
    else:
        implied_stock = round_to_cent(board['stock_num'])

    # Normalise: flip side if price goes negative
    if price < 0:
        price = abs(price)
        side = 'offer' if side == 'bid' else 'bid'

    # Apply impact only when aggressive and the caller wants immediate impact
    if apply_impact and ((side == 'bid' and price > fair) or (side == 'offer' and price < fair)):
        _apply_options_impact(board, opt_size, delta, side)

    if side == 'offer':
        speak = f"Customer offers {opt_size} lots of {option_label} at {price}"
    else:
        speak = f"Customer bids {price} for {opt_size} lots of {option_label}"

    return {
        "strike":         strike,
        "option_label":   option_label,
        "customer_price": price,
        "implied_stock":  implied_stock,
        "size":           opt_size,
        "side":           side,
        "sentence":       f"{opt_size}x {option_label} – make a market",
        "speak":          speak,
        "order_kind":     "options",
    }


def generate_otm_order_data(board):
    """
    Generate a customer order for one of the two OTM options:
      - p_and_s_strike call  price = fair ± edge  (fair = P&S + rc)
      - bw_strike put        price = fair ± edge  (fair = B/W  - rc)

    OTM customers use the aggressive _OTM_K_LIST edge distribution.
    Price is set directly from fair value; no market-making prompt is shown.
    """
    _clip_stock_fair(board)
    is_call = random.choice([True, False])

    if is_call:
        strike = board['p_and_s_strike']
        delta  = board['p_and_s_call_delta']
        option_label = f"{int(strike)} call"
    else:
        strike = board['bw_strike']
        delta  = board['bw_put_delta']
        option_label = f"{int(strike)} put"

    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    opt_size = int(round(board['stock_size'] * mult))
    if opt_size > 100:
        opt_size = int(round(opt_size / 10) * 10)

    side = _biased_side(board, option_label)

    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )
    # OTM: delta-adjusted fair (BS price at open + delta × stock move)
    stock_move = board['stock_num'] - board['initial_stock_num']
    if is_call:
        bs_fair = board['answers'][board['p_and_s_strike']]['call']
        fair = max(round_to_cent(bs_fair + delta * stock_move), MIN_TICK)
    else:
        bs_fair = board['answers'][board['bw_strike']]['put']
        fair = max(round_to_cent(bs_fair + delta * stock_move), MIN_TICK)

    # Edge in stock space scaled by |delta|, plus uniform noise
    k           = float(np.random.choice(_OTM_K_LIST))
    option_edge = round_to_cent(k * half_spread * abs(delta))
    noise       = round_to_cent(float(np.random.uniform(-0.06, 0.02)))
    total_edge  = option_edge + noise
    price       = round_to_cent(fair - total_edge) if side == 'bid' else round_to_cent(fair + total_edge)

    implied_stock = round(board['stock_num'], 2)

    # Normalise: flip side if price goes negative
    if price < 0:
        price = abs(price)
        side = 'offer' if side == 'bid' else 'bid'

    # Apply impact only when the order is aggressive vs fair
    if (side == 'bid' and price > fair) or (side == 'offer' and price < fair):
        _apply_options_impact(board, opt_size, delta, side)

    if side == 'offer':
        speak = f"Customer offers {opt_size} lots of {option_label} at {price}"
    else:
        speak = f"Customer bids {price} for {opt_size} lots of {option_label}"

    return {
        "strike":         strike,
        "option_label":   option_label,
        "customer_price": price,
        "implied_stock":  implied_stock,
        "size":           opt_size,
        "side":           side,
        "sentence":       f"{opt_size}x {option_label} – make a market",
        "speak":          speak,
        "order_kind":     "options",
    }


def generate_middle_options_market(board, apply_impact=True):
    """
    Generate a customer market request for one of the six middle-strike options:
      - inside_low_strike  call/put  (K - tick)
      - atm_strike         call/put  (K)
      - inside_high_strike call/put  (K + tick)

    Pricing: customer_price = BS_fair ± (k * half_spread)
    where k is drawn from _COMBO_K_LIST (same semantics: k<0 = house edge).
    implied_stock is recovered via the linear delta approximation:
      implied_stock = stock_num + (price - fair) / delta
    """
    _clip_stock_fair(board)
    atm_strike = board['strikes'][2]
    strike  = random.choice([board['inside_low_strike'], atm_strike, board['inside_high_strike']])
    is_call = random.choice([True, False])

    if strike == board['inside_low_strike']:
        delta = board['inside_low_call_delta']  if is_call else board['inside_low_put_delta']
    elif strike == atm_strike:
        delta = board['atm_call_delta'] if is_call else board['atm_put_delta']
    else:
        delta = board['inside_high_call_delta'] if is_call else board['inside_high_put_delta']

    option_label = f"{int(strike)} {'call' if is_call else 'put'}"

    mult     = float(np.random.choice(_COMBO_MULTIPLIERS))
    opt_size = int(round(board['stock_size'] * mult))
    if opt_size > 100:
        opt_size = int(round(opt_size / 10) * 10)

    side = _biased_side(board, option_label)

    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )
    # Delta-adjusted fair: BS price at open + delta × (current stock − initial stock)
    bs_fair_at_open = board['answers'][strike]['call' if is_call else 'put']
    stock_move      = board['stock_num'] - board['initial_stock_num']
    fair            = round_to_cent(bs_fair_at_open + delta * stock_move)
    fair            = max(fair, MIN_TICK)

    # Edge in stock space scaled by |delta|, plus uniform noise
    k           = float(np.random.choice(_MIDDLE_OPTIONS_K_LIST))
    option_edge = round_to_cent(k * half_spread * abs(delta))
    noise       = round_to_cent(float(np.random.uniform(-0.06, 0.02)))
    total_edge  = option_edge + noise
    price       = round_to_cent(fair - total_edge) if side == 'bid' else round_to_cent(fair + total_edge)

    # Recover implied stock via first-order delta approximation
    if abs(delta) > 1e-6:
        implied_stock = round_to_cent(board['stock_num'] + (price - fair) / delta)
    else:
        implied_stock = round_to_cent(board['stock_num'])

    # Keep price positive
    if price < 0:
        price = abs(price)
        side  = 'offer' if side == 'bid' else 'bid'

    # Apply impact only when aggressive and the caller wants immediate impact
    if apply_impact and ((side == 'bid' and price > fair) or (side == 'offer' and price < fair)):
        _apply_options_impact(board, opt_size, delta, side)

    if side == 'offer':
        speak = f"Customer offers {opt_size} lots of {option_label} at {price}"
    else:
        speak = f"Customer bids {price} for {opt_size} lots of {option_label}"

    return {
        "strike":         strike,
        "option_label":   option_label,
        "customer_price": price,
        "implied_stock":  implied_stock,
        "fair":           fair,
        "delta":          delta,
        "size":           opt_size,
        "side":           side,
        "sentence":       f"{opt_size}x {option_label} – make a market",
        "speak":          speak,
        "order_kind":     "middle_options",
    }


def generate_directed_option_order_data(board, strike_f, option_type, preferred_side,
                                          apply_impact=True):
    """
    Generate a customer option order for any board strike with a preferred side.
    Uses delta-adjusted BS fair + edge pricing (same model as middle options).
    preferred_side is honoured with 85 % probability.
    When apply_impact=False impact is deferred to the submit handler.
    """
    _clip_stock_fair(board)
    is_call = (option_type == 'call')

    atm_strike = board['strikes'][2]
    delta_map = {
        board['bw_strike']:          {'call': board['bw_delta'],             'put': board['bw_put_delta']},
        board['inside_low_strike']:  {'call': board['inside_low_call_delta'], 'put': board['inside_low_put_delta']},
        atm_strike:                  {'call': board['atm_call_delta'],        'put': board['atm_put_delta']},
        board['inside_high_strike']: {'call': board['inside_high_call_delta'],'put': board['inside_high_put_delta']},
        board['p_and_s_strike']:     {'call': board['p_and_s_call_delta'],    'put': board['p_and_s_delta']},
    }

    delta = 0.5
    for k, v in delta_map.items():
        if abs(k - strike_f) < 0.01:
            delta = v.get(option_type, 0.5)
            break

    ans_key = None
    for k in board['answers']:
        if abs(k - strike_f) < 0.01:
            ans_key = k
            break
    bs_fair_at_open = board['answers'][ans_key]['call' if is_call else 'put'] if ans_key is not None else 1.0

    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    opt_size = int(round(board['stock_size'] * mult))
    if opt_size > 100:
        opt_size = int(round(opt_size / 10) * 10)

    side = preferred_side if random.random() < 0.85 else ('offer' if preferred_side == 'bid' else 'bid')

    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )

    stock_move = board['stock_num'] - board['initial_stock_num']
    fair = round_to_cent(bs_fair_at_open + delta * stock_move)
    fair = max(fair, MIN_TICK)

    # Edge in stock space scaled by |delta|, plus uniform noise
    k           = float(np.random.choice(_MIDDLE_OPTIONS_K_LIST))
    option_edge = round_to_cent(k * half_spread * abs(delta))
    noise       = round_to_cent(float(np.random.uniform(-0.06, 0.02)))
    total_edge  = option_edge + noise
    price       = round_to_cent(fair - total_edge) if side == 'bid' else round_to_cent(fair + total_edge)

    if abs(delta) > 1e-6:
        implied_stock = round_to_cent(board['stock_num'] + (price - fair) / delta)
    else:
        implied_stock = round_to_cent(board['stock_num'])

    if price < 0:
        price = abs(price)
        side = 'offer' if side == 'bid' else 'bid'

    if apply_impact and ((side == 'bid' and price > fair) or (side == 'offer' and price < fair)):
        _apply_options_impact(board, opt_size, delta, side)

    option_label = f"{int(strike_f)} {option_type}"
    speak = (f"Customer offers {opt_size} lots of {option_label} at {price}"
             if side == 'offer' else
             f"Customer bids {price} for {opt_size} lots of {option_label}")

    return {
        "strike":         strike_f,
        "option_label":   option_label,
        "customer_price": price,
        "implied_stock":  implied_stock,
        "fair":           fair,
        "delta":          delta,
        "size":           opt_size,
        "side":           side,
        "sentence":       f"{opt_size}x {option_label} – make a market",
        "speak":          speak,
        "order_kind":     "middle_options",
    }


# ─── Spread helpers ───────────────────────────────────────────────────────────

def _get_strike_delta_map(board):
    atm = board['strikes'][2]
    return {
        board['bw_strike']:          {'call': board['bw_delta'],             'put': board['bw_put_delta']},
        board['inside_low_strike']:  {'call': board['inside_low_call_delta'],'put': board['inside_low_put_delta']},
        atm:                         {'call': board['atm_call_delta'],        'put': board['atm_put_delta']},
        board['inside_high_strike']: {'call': board['inside_high_call_delta'],'put': board['inside_high_put_delta']},
        board['p_and_s_strike']:     {'call': board['p_and_s_call_delta'],    'put': board['p_and_s_delta']},
    }


def _valid_spread_pairs(board, strike_pool=None):
    """All (k1, k2) pairs from strike_pool where gap <= 10 (max 2 ticks).

    strike_pool defaults to all board strikes.
    """
    strikes = sorted(strike_pool if strike_pool is not None else board['strikes'])
    return [(k1, k2) for i, k1 in enumerate(strikes)
            for k2 in strikes[i + 1:] if k2 - k1 <= 10 + 1e-9]


def _spread_fair_delta_label(board, k1, k2, spread_type):
    """
    Compute (fair, net_delta, label) normalised so fair > 0.
      call_spread   : long k1 call / short k2 call
      put_spread    : long k2 put  / short k1 put
      risk_reversal : long k1 put  / short k2 call  (bearish; flipped if fair < 0)
    """
    dm = _get_strike_delta_map(board)
    stock_move = board['stock_num'] - board['initial_stock_num']
    k1i, k2i = int(k1), int(k2)

    if spread_type == 'call_spread':
        bs_open   = board['answers'][k1]['call'] - board['answers'][k2]['call']
        net_delta = dm[k1]['call'] - dm[k2]['call']
        label     = f"{k1i}/{k2i} call spread"
    elif spread_type == 'put_spread':
        bs_open   = board['answers'][k2]['put'] - board['answers'][k1]['put']
        net_delta = dm[k2]['put'] - dm[k1]['put']
        label     = f"{k1i}/{k2i} put spread"
    else:  # risk_reversal
        bs_open   = board['answers'][k1]['put'] - board['answers'][k2]['call']
        net_delta = dm[k1]['put'] - dm[k2]['call']
        label     = f"{k1i}/{k2i} RR (long put/short call)"

    fair = round_to_cent(bs_open + net_delta * stock_move)
    if fair < 0:
        fair      = -fair
        net_delta = -net_delta
        if spread_type == 'risk_reversal':
            label = f"{k1i}/{k2i} RR (long call/short put)"

    return fair, net_delta, label


def _generate_spread_data(board, spread_types=None, strike_pool=None, apply_impact=True):
    """Core spread order generator shared by all spread market/order flows.

    spread_types: list of allowed spread kinds to draw from.  Defaults to all
    three: ['call_spread', 'put_spread', 'risk_reversal'].
    strike_pool: optional list of strikes to restrict pair selection.
    When apply_impact=False impact is deferred to the submit handler.
    """
    if spread_types is None:
        spread_types = ['call_spread', 'put_spread', 'risk_reversal']
    _clip_stock_fair(board)
    pairs = _valid_spread_pairs(board, strike_pool=strike_pool)
    k1, k2 = random.choice(pairs)
    spread_type = random.choice(spread_types)

    fair, net_delta, label = _spread_fair_delta_label(board, k1, k2, spread_type)
    fair = max(fair, MIN_TICK)

    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    opt_size = int(round(board['stock_size'] * mult))
    if opt_size > 100:
        opt_size = int(round(opt_size / 10) * 10)

    side = random.choice(['bid', 'offer'])
    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )
    k    = float(np.random.choice(_MIDDLE_OPTIONS_K_LIST))
    edge = round_to_cent(k * half_spread)

    price = round_to_cent(fair - edge) if side == 'bid' else round_to_cent(fair + edge)
    if price < 0:
        price = abs(price)
        side  = 'offer' if side == 'bid' else 'bid'

    if apply_impact and ((side == 'bid' and price > fair) or (side == 'offer' and price < fair)):
        _apply_options_impact(board, opt_size, net_delta, side)

    speak = (f"Customer offers {opt_size} lots of {label} at {price}"
             if side == 'offer' else
             f"Customer bids {price} for {opt_size} lots of {label}")

    return {
        'k1':             k1,
        'k2':             k2,
        'spread_type':    spread_type,
        'spread_label':   label,
        'fair':           fair,
        'net_delta':      net_delta,
        'customer_price': price,
        'size':           opt_size,
        'side':           side,
        'sentence':       f"{opt_size}x {label} {'offered at' if side == 'offer' else 'bid at'} {price}",
        'speak':          speak,
        'order_kind':     'spread',
        'announce':       f"{opt_size} lots of {label}.",
    }


def generate_opening_order_data(board):
    """
    Generate the board's first order: an aggressive ITM option or ATM combo
    that clearly crosses the stock spread, forcing the user to trade stock
    and estimate the impact function from the resulting price move.
    k is drawn from _OPENING_K_LIST (all very negative → always crossing).
    Size is deliberately large (3–8× stock_size) to make impact visible.
    """
    _clip_stock_fair(board)
    is_combo = random.choice([True, False])
    side = random.choice(['bid', 'offer'])
    k = float(np.random.choice(_OPENING_K_LIST))
    mult = float(np.random.choice([3.0, 4.0, 5.0, 6.0, 7.0, 8.0]))

    half_spread = max(
        (board['stock_spread']['offer'] - board['stock_spread']['bid']) / 2.0,
        MIN_TICK
    )
    edge = round_to_cent(k * half_spread)

    if is_combo:
        strike = board['strikes'][2]  # ATM combo
        opt_size = int(round(board['stock_size'] * mult))
        if opt_size > 100:
            opt_size = int(round(opt_size / 10) * 10)

        fair_combo = board['stock_num'] - strike + board['rc_num']
        price = round_to_cent(fair_combo - edge) if side == 'bid' else round_to_cent(fair_combo + edge)
        if price < 0:
            price = abs(price)
            side = 'offer' if side == 'bid' else 'bid'

        implied_stock = (round_to_cent(strike + price - board['rc_num']) if fair_combo >= 0
                         else round_to_cent(strike - price - board['rc_num']))
        combo_price_shift = abs(round(abs(fair_combo) - abs(price), 2))
        speak = (f"Customer offers {opt_size} lots of {int(strike)} combos at {price}"
                 if side == 'offer' else
                 f"Customer bids {price} for {opt_size} lots of {int(strike)} combos")
        return {
            "strike":            strike,
            "price":             price,
            "size":              opt_size,
            "side":              side,
            "combo_price_shift": combo_price_shift,
            "sentence":          (f"{opt_size}x {int(strike)} combo offered at {price}"
                                  if side == 'offer' else
                                  f"{opt_size}x {int(strike)} combo bid at {price}"),
            "implied_stock":     round(implied_stock, 2),
            "implied_side":      side,
            "speak":             speak,
        }
    else:
        # ITM option: bw_strike call or p_and_s_strike put
        is_call = random.choice([True, False])
        if is_call:
            strike = board['bw_strike']
            delta  = board['bw_delta']
            option_label = f"{int(strike)} call"
            fair = round_to_cent(board['stock_num'] - strike + board['bw'])
            implied_stock = (round_to_cent(board['stock_num'] - edge) if side == 'bid'
                             else round_to_cent(board['stock_num'] + edge))
            price = round_to_cent(implied_stock - strike + board['bw'])
        else:
            strike = board['p_and_s_strike']
            delta  = board['p_and_s_delta']
            option_label = f"{int(strike)} put"
            fair = round_to_cent(strike - board['stock_num'] + board['p_and_s'])
            implied_stock = (round_to_cent(board['stock_num'] + edge) if side == 'bid'
                             else round_to_cent(board['stock_num'] - edge))
            price = round_to_cent(strike - implied_stock + board['p_and_s'])

        opt_size = int(round(board['stock_size'] * mult))
        if opt_size > 100:
            opt_size = int(round(opt_size / 10) * 10)

        if price < 0:
            price = abs(price)
            side = 'offer' if side == 'bid' else 'bid'

        speak = (f"Customer offers {opt_size} lots of {option_label} at {price}"
                 if side == 'offer' else
                 f"Customer bids {price} for {opt_size} lots of {option_label}")
        return {
            "strike":         strike,
            "option_label":   option_label,
            "customer_price": price,
            "implied_stock":  implied_stock,
            "size":           opt_size,
            "side":           side,
            "sentence":       (f"{opt_size}x {option_label} offered at {price}"
                               if side == 'offer' else
                               f"{opt_size}x {option_label} bid at {price}"),
            "speak":          speak,
            "order_kind":     "options",
        }


BOARD = generate_opening_board()

@app.route("/board_params")
def board_params():
    with _board_lock:
        dyn      = BOARD.get("dynamics", {})
        fair_mid = dyn.get("fair_mid", BOARD["stock_num"])
    return jsonify({
        "stock_fair":      BOARD["stock_num"],
        "fair_mid":        round(fair_mid, 2),
        "initial_fair":    BOARD["initial_stock_num"],
        "starting_size":   BOARD["stock_size"],
        "impact_function": BOARD["impact_function"],
        "rand_factor":     BOARD["rand_factor"],
        "start_width_raw": BOARD["start_width_raw"],
        "start_width":     BOARD["start_width"],
        "rc":              BOARD["rc_num"],
        "initial_bid":     BOARD["initial_bid"],
        "initial_offer":   BOARD["initial_offer"],
    })

@app.route("/set_drift", methods=["POST"])
def set_drift():
    """Adjust market movement speed live (0 = frozen, 1 = max) without resetting the board.

    Uses exponential interpolation across three dynamics so that every part of
    the scale feels meaningful:
      tick_vol   : 0.001 → 2.0   (random-walk speed, ticks/√s)
      drift_sigma: 0.0001 → 3.0  (OU drift innovation)
      drift_alpha: 10.0 → 0.1    (mean-reversion; lower = longer-lasting trends)
    At level=0.5 these land near the original random board defaults.
    At level=1.0 the stock moves several ticks per second with persistent trends.
    At level=0.0 the stock is completely frozen.
    """
    data  = request.get_json(silent=True) or {}
    level = float(data.get("level", 0.5))
    level = max(0.0, min(1.0, level))

    # Exponential interpolation: param = base * (ratio ** level)
    new_tick_vol    = 0.001  * (2000.0 ** level)   # 0.001 at 0 → 2.0 at 1
    new_drift_sigma = 0.0001 * (30000.0 ** level)  # 0.0001 at 0 → 3.0 at 1
    new_drift_alpha = 10.0   * (0.01   ** level)   # 10.0  at 0 → 0.1 at 1

    with _board_lock:
        dyn = BOARD.get("dynamics", {})
        if dyn:
            dyn["tick_vol"]    = new_tick_vol
            dyn["drift_sigma"] = new_drift_sigma
            dyn["drift_alpha"] = new_drift_alpha
            if level == 0.0:
                dyn["drift"] = 0.0   # kill any accumulated drift immediately

    return jsonify({
        "status":      "ok",
        "tick_vol":    round(new_tick_vol, 4),
        "drift_sigma": round(new_drift_sigma, 4),
        "drift_alpha": round(new_drift_alpha, 4),
    })


@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    text = data.get("text", "")

    if text:
        speak_text(text)

    return jsonify({"status": "ok"})


@app.route("/speech_status")
def speech_status():
    return jsonify({"speaking": speech_active or not speech_queue.empty()})


@app.route("/generate_order")
def generate_order():
    order = generate_combo_order(BOARD)
    price = order["price"]
    size  = order["size"]
    strike = int(order["strike"])
    if order["side"] == "offer":
        order["sentence"] = f"{size}x {strike} combo offered at {price}"
    else:
        order["sentence"] = f"{size}x {strike} combo bid at {price}"
    return jsonify(order)


@app.route("/generate_options_order")
def generate_options_order():
    order = generate_options_market(BOARD)
    price = order["customer_price"]
    size  = order["size"]
    label = order["option_label"]
    if order["side"] == "offer":
        order["sentence"] = f"{size}x {label} offered at {price}"
    else:
        order["sentence"] = f"{size}x {label} bid at {price}"
    return jsonify(order)


@app.route("/generate_otm_order")
def generate_otm_order():
    order = generate_otm_order_data(BOARD)
    price = order["customer_price"]
    size  = order["size"]
    label = order["option_label"]
    if order["side"] == "offer":
        order["sentence"] = f"{size}x {label} offered at {price}"
    else:
        order["sentence"] = f"{size}x {label} bid at {price}"
    return jsonify(order)

@app.route("/trade_stock", methods=["POST"])
def trade_stock_route():
    data = request.json or {}
    side = data.get("side")
    qty = safe_positive_int(data.get("size"))
    limit = safe_price(data.get("price"))

    if side not in ["buy", "sell"] or qty is None or limit is None:
        return jsonify({
            "ok": False,
            "message": "Invalid stock order. Provide side=buy/sell, positive integer size, and numeric price.",
            "stock": BOARD["stock_spread"]
        }), 400

    result = execute_stock_trade(BOARD, side, qty, limit)
    result["stock"] = BOARD["stock_spread"]
    return jsonify(result)



@app.route("/get_ladder")
def get_ladder():
    with _board_lock:
        best_bid   = BOARD["best_bid"]
        best_offer = BOARD["best_offer"]
        levels     = {p: dict(d) for p, d in BOARD["ladder_levels"].items()}
    mid = (best_bid + best_offer) / 2
    # Snap to nearest cent so the mid indicator always lands on an existing tick
    # row. Using the raw sub-cent mid caused it to render identically (via
    # JS .toFixed(2)) to an adjacent gap-price row, producing a duplicate.
    display_mid = round_to_cent(mid)
    N = 15

    offer_prices = sorted([p for p in levels if p >= best_offer])[:N]
    bid_prices   = sorted([p for p in levels if p <= best_bid], reverse=True)[:N]

    # Prices strictly between best_bid and best_offer (the spread gap)
    gap_prices = []
    p = round_to_cent(best_offer - MIN_TICK)
    while p > best_bid + MIN_TICK / 2:
        gap_prices.append(p)
        p = round_to_cent(p - MIN_TICK)

    def _make_row(price, side, d=None):
        if d is None:
            d = levels.get(price, {
                "market_bid": 0, "market_offer": 0,
                "user_buy": 0, "user_sell": 0,
                "filled_buy": 0, "filled_sell": 0,
            })
        is_mid_row = abs(price - display_mid) < 1e-9
        if side == "offer":
            vol = d["market_offer"] + d["user_sell"]
            bid_val, offer_val = None, (vol if vol > 0 else None)
        elif side == "bid":
            vol = d["market_bid"] + d["user_buy"]
            bid_val, offer_val = (vol if vol > 0 else None), None
        else:
            bid_val, offer_val = None, None
        return {
            "price":       round(price, 2),
            "bid":         bid_val,
            "offer":       offer_val,
            "you_buy":     d["user_buy"]    if d["user_buy"]    > 0 else None,
            "you_sell":    d["user_sell"]   if d["user_sell"]   > 0 else None,
            "filled_buy":  d["filled_buy"]  if d["filled_buy"]  > 0 else None,
            "filled_sell": d["filled_sell"] if d["filled_sell"] > 0 else None,
            "is_mid":      is_mid_row,
            "side":        "mid" if is_mid_row else side,
        }

    # Build all prices in descending order; insert virtual mid row when needed
    all_prices = sorted(set(offer_prices) | set(gap_prices) | set(bid_prices), reverse=True)

    rows = []
    # If display_mid falls exactly on a tick already in the list, _make_row will
    # mark it; pre-set mid_inserted so the fallback block doesn't add a duplicate.
    mid_inserted = any(abs(p - display_mid) < 1e-9 for p in all_prices)

    for p in all_prices:
        # Insert a virtual mid row just before the first price that falls below display_mid
        if not mid_inserted and p < display_mid - 1e-9:
            mid_inserted = True
            rows.append({
                "price": display_mid, "bid": None, "offer": None,
                "you_buy": None, "you_sell": None,
                "filled_buy": None, "filled_sell": None,
                "is_mid": True, "side": "mid",
            })
        if p >= best_offer:
            rows.append(_make_row(p, "offer", levels.get(p)))
        elif p <= best_bid:
            rows.append(_make_row(p, "bid", levels.get(p)))
        else:
            rows.append(_make_row(p, "spread"))

    if not mid_inserted:
        rows.append({
            "price": display_mid, "bid": None, "offer": None,
            "you_buy": None, "you_sell": None,
            "filled_buy": None, "filled_sell": None,
            "is_mid": True, "side": "mid",
        })

    return jsonify({
        "rows":       rows,
        "best_bid":   best_bid,
        "best_offer": best_offer,
        "mid":        round(mid, 4),
    })


@app.route("/cancel_ladder_orders", methods=["POST"])
def cancel_ladder_orders():
    with _board_lock:
        levels = BOARD["ladder_levels"]
        cancelled_buy = cancelled_sell = 0
        for d in levels.values():
            cancelled_buy  += d["user_buy"]
            cancelled_sell += d["user_sell"]
            d["user_buy"]  = 0
            d["user_sell"] = 0
        _update_ladder_best_prices(BOARD)
        stock = dict(BOARD["stock_spread"])
    parts = []
    if cancelled_buy  > 0: parts.append(f"{cancelled_buy:,} buy")
    if cancelled_sell > 0: parts.append(f"{cancelled_sell:,} sell")
    msg = "Cancelled " + " / ".join(parts) if parts else "No resting orders to cancel"
    return jsonify({"ok": True, "message": msg, "stock": stock})


@app.route("/place_ladder_order", methods=["POST"])
def place_ladder_order():
    data  = request.json or {}
    side  = data.get("side")
    qty   = safe_positive_int(data.get("qty"))
    price = safe_price(data.get("price"))

    if side not in ("buy", "sell") or qty is None or price is None:
        return jsonify({"ok": False, "message": "Invalid order parameters"}), 400

    with _board_lock:
        result = execute_ladder_order(BOARD, side, qty, price)
        result["stock"] = dict(BOARD["stock_spread"])
    return jsonify(result)


@app.route("/")
def index():
    return render_template(
        "index.html",
        stock_spread=BOARD["stock_spread"],
        rc=BOARD["rc"],
        strikes=BOARD["strikes"],
        info=BOARD["info"],
        highlight=BOARD["highlight"],
        stock_size=BOARD["stock_size"],
        stock_ref=BOARD["initial_stock_num"]
    )

@app.route("/reveal")
def reveal():
    stock_move = BOARD['stock_num'] - BOARD['initial_stock_num']
    atm_strike = BOARD['strikes'][2]

    # Map every strike to its board-open call/put delta
    strike_deltas = {
        BOARD['bw_strike']:          {'call': BOARD['bw_delta'],            'put': BOARD['bw_put_delta']},
        BOARD['inside_low_strike']:  {'call': BOARD['inside_low_call_delta'],'put': BOARD['inside_low_put_delta']},
        atm_strike:                  {'call': BOARD['atm_call_delta'],       'put': BOARD['atm_put_delta']},
        BOARD['inside_high_strike']: {'call': BOARD['inside_high_call_delta'],'put': BOARD['inside_high_put_delta']},
        BOARD['p_and_s_strike']:     {'call': BOARD['p_and_s_call_delta'],   'put': BOARD['p_and_s_delta']},
    }

    adjusted = {}
    for strike, opts in BOARD['answers'].items():
        d = strike_deltas.get(float(strike), {'call': 0.5, 'put': -0.5})
        adjusted[strike] = {
            'call': max(round(opts['call'] + d['call'] * stock_move, 2), MIN_TICK),
            'put':  max(round(opts['put']  + d['put']  * stock_move, 2), MIN_TICK),
        }

    return jsonify(adjusted)

@app.route("/reveal_deltas")
def reveal_deltas():
    atm_strike = BOARD['strikes'][2]
    deltas = {
        BOARD['bw_strike']:          {'call': BOARD['bw_delta'],             'put': BOARD['bw_put_delta']},
        BOARD['inside_low_strike']:  {'call': BOARD['inside_low_call_delta'],'put': BOARD['inside_low_put_delta']},
        atm_strike:                  {'call': BOARD['atm_call_delta'],        'put': BOARD['atm_put_delta']},
        BOARD['inside_high_strike']: {'call': BOARD['inside_high_call_delta'],'put': BOARD['inside_high_put_delta']},
        BOARD['p_and_s_strike']:     {'call': BOARD['p_and_s_call_delta'],    'put': BOARD['p_and_s_delta']},
    }
    return jsonify({str(k): v for k, v in deltas.items()})

@app.route("/reveal_at")
def reveal_at():
    """Return BS prices and deltas for all board strikes at a custom stock level."""
    try:
        S_custom = float(request.args.get("stock"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid stock"}), 400

    T   = BOARD['T']
    r   = BOARD['r']
    vol = BOARD['vol']

    answers = {}
    deltas  = {}
    for strike in BOARD['strikes']:
        answers[strike] = {
            'call': max(black_scholes_price(S_custom, strike, T, r, vol, 'call'), MIN_TICK),
            'put':  max(black_scholes_price(S_custom, strike, T, r, vol, 'put'),  MIN_TICK),
        }
        deltas[strike] = {
            'call': black_scholes_delta(S_custom, strike, T, r, vol, 'call'),
            'put':  black_scholes_delta(S_custom, strike, T, r, vol, 'put'),
        }

    return jsonify({
        'answers': {str(k): v for k, v in answers.items()},
        'deltas':  {str(k): v for k, v in deltas.items()},
    })


@app.route("/new_board")
def new_board():
    global BOARD
    new = generate_opening_board()
    with _board_lock:
        BOARD = new
    return redirect(url_for("index"))

@app.route("/make_market")
def make_market():
    strike = random.choice(BOARD['strikes'])
    side, customer_price, size, orig_side = generate_customer_combo_price(BOARD, strike)
    fair_combo = BOARD["stock_num"] - float(strike) + BOARD["rc_num"]

    order = {
        "strike":       strike,
        "size":         size,
        "side":         side,
        "orig_side":    orig_side,           # pre-flip side for correct impact direction
        "is_puts_over": fair_combo < 0,      # tells submit_market to invert direction
        "customer_price": customer_price,
        "sentence": f"{size}x {int(strike)} combo – make a market",
        "announce": f"{size} lots of {int(strike)} combos.",
    }

    return jsonify(order)



@app.route("/submit_market", methods=["POST"])
def submit_market():
    data = request.json

    bid = float(data["bid"])
    offer = float(data["offer"])
    strike = data["strike"]
    size = data["size"]

    customer_side = data["side"]
    customer_price = float(data["customer_price"])

    # Derive stock_dir (bullish/bearish signal for _apply_combo_impact) from the
    # pre-flip original side and the fair_combo sign (passed from make_market).
    # Must use orig_side, not customer_side: _combo_customer_price only flips when
    # price < 0, so a barely puts-over combo may not flip, leaving customer_side
    # equal to orig_side even in puts-over territory.
    #
    # calls-over (is_puts_over=False):  stock_dir = orig_side (bid→UP, offer→DOWN)
    # puts-over  (is_puts_over=True):   stock_dir = INVERTED orig_side
    #   orig bid  (long put/short call)  = bearish → stock_dir='offer' → stock DOWN
    #   orig offer (short put/long call) = bullish → stock_dir='bid'   → stock UP
    orig_side    = data.get("orig_side", customer_side)
    is_puts_over = data.get("is_puts_over", False)
    stock_dir    = ('offer' if orig_side == 'bid' else 'bid') if is_puts_over else orig_side

    # ---------- FAIR VALUE ----------
    fair_combo = BOARD["stock_num"] - strike + BOARD["rc_num"]

    # ---------- CHECK FOR CROSS ----------

    def _combo_implied(trade_price):
        fc = BOARD["stock_num"] - float(strike) + BOARD["rc_num"]
        if fc >= 0:
            return round(float(strike) + trade_price - BOARD["rc_num"], 2)
        else:
            return round(float(strike) - trade_price - BOARD["rc_num"], 2)

    if customer_side == "bid":
        # Customer wants to buy
        if offer <= customer_price:
            _apply_combo_impact(BOARD, int(size), stock_dir)
            return jsonify({
                "type": "trade",
                "side": "offer",
                "price": offer,
                "strike": strike,
                "size": size,
                "speak": f"Customer buys {size} at {offer}",
                "implied_stock": _combo_implied(offer),
                "stock": BOARD["stock_spread"]
            })

    else:
        # Customer wants to sell
        if bid >= customer_price:
            _apply_combo_impact(BOARD, int(size), stock_dir)
            return jsonify({
                "type": "trade",
                "side": "bid",
                "price": bid,
                "strike": strike,
                "size": size,
                "speak": f"Customer sells {size} at {bid}",
                "implied_stock": _combo_implied(bid),
                "stock": BOARD["stock_spread"]
            })

    # ---------- NO CROSS: customer rests at their pre-computed price ----------

    if customer_side == "bid":
        speak = f"Customer bids {customer_price} for {size} lots of {int(strike)} combos"
        sentence = f"{size}x {int(strike)} combo bid @ {customer_price}"
    else:
        speak = f"Customer offers {size} lots of {int(strike)} combos at {customer_price}"
        sentence = f"{size}x {int(strike)} combo offered @ {customer_price}"

    fair_combo = BOARD["stock_num"] - float(strike) + BOARD["rc_num"]
    combo_price_shift = abs(round(abs(fair_combo) - abs(customer_price), 2))
    if fair_combo >= 0:
        implied_stock = round(float(strike) + customer_price - BOARD['rc_num'], 2)
    else:
        implied_stock = round(float(strike) - customer_price - BOARD['rc_num'], 2)

    # Use stock_dir (not customer_side) for the resting-order floor/ceiling so
    # a puts-over bid correctly registers as a ceiling, not a floor.
    _add_customer_resting_order(BOARD, implied_stock, stock_dir, int(size))

    return jsonify({
        "type": "order",
        "strike": strike,
        "price": customer_price,
        "size": size,
        "combo_price_shift": combo_price_shift,
        "implied_stock": implied_stock,
        "sentence": sentence,
        "speak": speak
    })


@app.route("/make_options_market")
def make_options_market():
    order = generate_options_market(BOARD, apply_impact=False)
    order["announce"] = f"{order['size']} lots of {order['option_label']}."
    return jsonify(order)


@app.route("/submit_options_market", methods=["POST"])
def submit_options_market():
    data = request.json

    bid          = float(data["bid"])
    offer        = float(data["offer"])
    strike       = data["strike"]
    size         = data["size"]
    option_label = data["option_label"]
    customer_side  = data["side"]
    customer_price = float(data["customer_price"])

    # ---------- CHECK FOR CROSS ----------

    is_call  = option_label.endswith("call")
    strike_f = float(strike)

    def _opt_implied(trade_price):
        if is_call:
            if abs(strike_f - BOARD["bw_strike"]) < 0.01:
                # ITM call at bw_strike
                return round(trade_price + strike_f - BOARD["bw"], 2)
            else:
                # OTM call at p_and_s_strike (price ≈ p_and_s + rc, stock-independent)
                return round(BOARD["stock_num"], 2)
        else:
            if abs(strike_f - BOARD["p_and_s_strike"]) < 0.01:
                # ITM put at p_and_s_strike
                return round(strike_f - trade_price + BOARD["p_and_s"], 2)
            else:
                # OTM put at bw_strike (price ≈ bw - rc, stock-independent)
                return round(BOARD["stock_num"], 2)

    # Look up delta for impact (negative for puts)
    _dm = _get_strike_delta_map(BOARD)
    _opt_delta = 0.5
    for _k, _v in _dm.items():
        if abs(_k - strike_f) < 0.01:
            _opt_delta = _v.get('call' if is_call else 'put', 0.5)
            break

    if customer_side == "bid":
        if offer <= customer_price:
            _apply_options_impact(BOARD, int(size), _opt_delta, customer_side)
            return jsonify({
                "type":          "trade",
                "side":          "offer",
                "price":         offer,
                "strike":        strike,
                "size":          size,
                "option_label":  option_label,
                "speak":         f"Customer buys {size} {option_label} at {offer}",
                "implied_stock": _opt_implied(offer),
                "stock":         BOARD["stock_spread"],
            })
    else:
        if bid >= customer_price:
            _apply_options_impact(BOARD, int(size), _opt_delta, customer_side)
            return jsonify({
                "type":          "trade",
                "side":          "bid",
                "price":         bid,
                "strike":        strike,
                "size":          size,
                "option_label":  option_label,
                "speak":         f"Customer sells {size} {option_label} at {bid}",
                "implied_stock": _opt_implied(bid),
                "stock":         BOARD["stock_spread"],
            })

    # ---------- NO CROSS: customer rests at their pre-computed price ----------

    if customer_side == "bid":
        speak = f"Customer bids {customer_price} for {size} lots of {option_label}"
        sentence = f"{size}x {option_label} bid @ {customer_price}"
    else:
        speak = f"Customer offers {size} lots of {option_label} at {customer_price}"
        sentence = f"{size}x {option_label} offered @ {customer_price}"

    opt_implied_stock = _opt_implied(customer_price)

    # Register resting order: delta sign × side sign gives the stock-equivalent direction
    _signed_d = _opt_delta * (1.0 if customer_side == 'bid' else -1.0)
    _add_customer_resting_order(BOARD, opt_implied_stock,
                                'bid' if _signed_d > 0 else 'offer',
                                int(round(int(size) * abs(_opt_delta))))

    return jsonify({
        "type":          "order",
        "strike":        strike,
        "option_label":  option_label,
        "price":         customer_price,
        "implied_stock": opt_implied_stock,
        "size":          size,
        "side":          customer_side,
        "sentence":      sentence,
        "speak":         speak,
        "order_kind":    "options",
    })


# ── Middle-strike options routes ─────────────────────────────────────────────

@app.route("/make_middle_options_market")
def make_middle_options_market():
    order = generate_middle_options_market(BOARD, apply_impact=False)
    order["announce"] = f"{order['size']} lots of {order['option_label']}."
    return jsonify(order)


@app.route("/generate_middle_option_order")
def generate_middle_option_order():
    order = generate_middle_options_market(BOARD)
    price = order["customer_price"]
    size  = order["size"]
    label = order["option_label"]
    if order["side"] == "offer":
        order["sentence"] = f"{size}x {label} offered at {price}"
    else:
        order["sentence"] = f"{size}x {label} bid at {price}"
    return jsonify(order)


@app.route("/submit_middle_options_market", methods=["POST"])
def submit_middle_options_market():
    data = request.json

    bid            = float(data["bid"])
    offer          = float(data["offer"])
    strike         = data["strike"]
    size           = data["size"]
    option_label   = data["option_label"]
    customer_side  = data["side"]
    customer_price = float(data["customer_price"])
    fair           = float(data["fair"])
    delta          = float(data["delta"])

    def _opt_implied(trade_price):
        if abs(delta) > 1e-6:
            return round(BOARD["stock_num"] + (trade_price - fair) / delta, 2)
        return round(BOARD["stock_num"], 2)

    if customer_side == "bid":
        if offer <= customer_price:
            _apply_options_impact(BOARD, int(size), delta, customer_side)
            return jsonify({
                "type":          "trade",
                "side":          "offer",
                "price":         offer,
                "strike":        strike,
                "size":          size,
                "option_label":  option_label,
                "speak":         f"Customer buys {size} {option_label} at {offer}",
                "implied_stock": _opt_implied(offer),
                "stock":         BOARD["stock_spread"],
            })
    else:
        if bid >= customer_price:
            _apply_options_impact(BOARD, int(size), delta, customer_side)
            return jsonify({
                "type":          "trade",
                "side":          "bid",
                "price":         bid,
                "strike":        strike,
                "size":          size,
                "option_label":  option_label,
                "speak":         f"Customer sells {size} {option_label} at {bid}",
                "implied_stock": _opt_implied(bid),
                "stock":         BOARD["stock_spread"],
            })

    # No cross: customer rests at their pre-computed price
    if customer_side == "bid":
        speak    = f"Customer bids {customer_price} for {size} lots of {option_label}"
        sentence = f"{size}x {option_label} bid @ {customer_price}"
    else:
        speak    = f"Customer offers {size} lots of {option_label} at {customer_price}"
        sentence = f"{size}x {option_label} offered @ {customer_price}"

    _mid_implied = _opt_implied(customer_price)
    _signed_d    = delta * (1.0 if customer_side == 'bid' else -1.0)
    _add_customer_resting_order(BOARD, _mid_implied,
                                'bid' if _signed_d > 0 else 'offer',
                                int(round(int(size) * abs(delta))))

    return jsonify({
        "type":          "order",
        "strike":        strike,
        "option_label":  option_label,
        "price":         customer_price,
        "implied_stock": _mid_implied,
        "size":          size,
        "side":          customer_side,
        "sentence":      sentence,
        "speak":         speak,
        "order_kind":    "middle_options",
    })


@app.route("/generate_opening_order")
def generate_opening_order_route():
    order = generate_opening_order_data(BOARD)
    return jsonify(order)


@app.route("/generate_directed_option_order")
def generate_directed_option_order_route():
    try:
        strike_f      = float(request.args.get("strike"))
        option_type   = request.args.get("option_type")
        preferred_side = request.args.get("preferred_side")
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid parameters"}), 400

    if option_type not in ("call", "put") or preferred_side not in ("bid", "offer"):
        return jsonify({"error": "Invalid option_type or preferred_side"}), 400

    if not any(abs(strike_f - s) < 0.01 for s in BOARD['strikes']):
        return jsonify({"error": "Strike not on board"}), 400

    order = generate_directed_option_order_data(BOARD, strike_f, option_type, preferred_side)
    price = order["customer_price"]
    size  = order["size"]
    label = order["option_label"]
    if order["side"] == "offer":
        order["sentence"] = f"{size}x {label} offered at {price}"
    else:
        order["sentence"] = f"{size}x {label} bid at {price}"
    return jsonify(order)


@app.route("/make_directed_options_market")
def make_directed_options_market():
    try:
        strike_f       = float(request.args.get("strike"))
        option_type    = request.args.get("option_type")
        preferred_side = request.args.get("preferred_side")
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid parameters"}), 400

    if option_type not in ("call", "put") or preferred_side not in ("bid", "offer"):
        return jsonify({"error": "Invalid option_type or preferred_side"}), 400

    if not any(abs(strike_f - s) < 0.01 for s in BOARD['strikes']):
        return jsonify({"error": "Strike not on board"}), 400

    order = generate_directed_option_order_data(BOARD, strike_f, option_type, preferred_side,
                                                apply_impact=False)
    order["announce"] = f"{order['size']} lots of {order['option_label']}."
    return jsonify(order)


# ─── Spread routes ────────────────────────────────────────────────────────────

@app.route("/generate_spread_order")
def generate_spread_order():
    order = _generate_spread_data(BOARD)
    price = order["customer_price"]
    size  = order["size"]
    label = order["spread_label"]
    if order["side"] == "offer":
        order["sentence"] = f"{size}x {label} offered at {price}"
    else:
        order["sentence"] = f"{size}x {label} bid at {price}"
    return jsonify(order)


@app.route("/make_spread_market")
def make_spread_market():
    order = _generate_spread_data(BOARD, apply_impact=False)
    return jsonify(order)


@app.route("/make_rr_market")
def make_rr_market():
    middle_strikes = BOARD['strikes'][1:4]  # inside_low, ATM, inside_high
    order = _generate_spread_data(BOARD, spread_types=['risk_reversal'],
                                  strike_pool=middle_strikes, apply_impact=False)
    return jsonify(order)


@app.route("/make_cs_ps_market")
def make_cs_ps_market():
    order = _generate_spread_data(BOARD, spread_types=['call_spread', 'put_spread'],
                                  apply_impact=False)
    return jsonify(order)


@app.route("/submit_spread_market", methods=["POST"])
def submit_spread_market():
    data           = request.json
    bid            = float(data["bid"])
    offer          = float(data["offer"])
    k1             = float(data["k1"])
    k2             = float(data["k2"])
    spread_type    = data["spread_type"]
    spread_label   = data["spread_label"]
    size           = data["size"]
    customer_side  = data["side"]
    customer_price = float(data["customer_price"])
    fair           = float(data["fair"])
    net_delta      = float(data["net_delta"])

    def _implied(trade_price):
        if abs(net_delta) > 1e-6:
            return round(BOARD["stock_num"] + (trade_price - fair) / net_delta, 2)
        return round(BOARD["stock_num"], 2)

    if customer_side == "bid":
        if offer <= customer_price:
            _apply_options_impact(BOARD, int(size), net_delta, customer_side)
            return jsonify({
                "type":          "trade",
                "side":          "offer",
                "price":         offer,
                "size":          size,
                "spread_label":  spread_label,
                "speak":         f"Customer buys {size} {spread_label} at {offer}",
                "implied_stock": _implied(offer),
                "stock":         BOARD["stock_spread"],
            })
    else:
        if bid >= customer_price:
            _apply_options_impact(BOARD, int(size), net_delta, customer_side)
            return jsonify({
                "type":          "trade",
                "side":          "bid",
                "price":         bid,
                "size":          size,
                "spread_label":  spread_label,
                "speak":         f"Customer sells {size} {spread_label} at {bid}",
                "implied_stock": _implied(bid),
                "stock":         BOARD["stock_spread"],
            })

    if customer_side == "bid":
        speak    = f"Customer bids {customer_price} for {size} lots of {spread_label}"
        sentence = f"{size}x {spread_label} bid @ {customer_price}"
    else:
        speak    = f"Customer offers {size} lots of {spread_label} at {customer_price}"
        sentence = f"{size}x {spread_label} offered @ {customer_price}"

    _sprd_implied = _implied(customer_price)
    _signed_d     = net_delta * (1.0 if customer_side == 'bid' else -1.0)
    _add_customer_resting_order(BOARD, _sprd_implied,
                                'bid' if _signed_d > 0 else 'offer',
                                int(round(int(size) * abs(net_delta))))

    return jsonify({
        "type":           "order",
        "k1":             k1,
        "k2":             k2,
        "spread_type":    spread_type,
        "spread_label":   spread_label,
        "price":          customer_price,
        "customer_price": customer_price,
        "implied_stock":  _sprd_implied,
        "size":           size,
        "side":           customer_side,
        "sentence":       sentence,
        "speak":          speak,
        "order_kind":     "spread",
        "fair":           fair,
        "net_delta":      net_delta,
    })


# Create the queue at the module level so all routes can see it
speech_queue = queue.Queue()

if __name__ == "__main__":
    # Speech worker
    t = threading.Thread(target=speech_worker, daemon=True)
    t.start()

    # Market dynamics worker (updates ladder every 50 ms)
    t_market = threading.Thread(target=_market_update_worker, daemon=True)
    t_market.start()

    # use_reloader=False is important! 
    # If True, Flask starts two processes and the threads will break.
    app.run(debug=True, use_reloader=False, threaded=True)









