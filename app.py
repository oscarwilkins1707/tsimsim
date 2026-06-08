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
import pythoncom

speech_active = False

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
    impact_function = round(float(np.random.uniform(0.01, 0.05) * 0.8), 4)
    rand_factor = float(np.random.uniform(0.5, 1.5))
    start_width_raw = impact_function * rand_factor + float(np.random.choice([0.03, 0.05, 0.07]))
    start_width = max(round(round(start_width_raw / MIN_TICK) * MIN_TICK, 2), 0.04)
    bid = round(S - start_width, 2)
    offer = round(S + start_width, 2)
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

    return board


def round_to_cent(value):
    return round(round(value / MIN_TICK) * MIN_TICK, 2)


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
    cdf = normal_cdf(level_price, board["stock_num"], sigma)
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


def _clip_stock_fair(board):
    """Clamp stock_num so it never sits outside the quoted bid-ask spread."""
    ceiling = board['stock_spread']['offer']
    floor   = board['stock_spread']['bid']
    board['stock_num'] = max(floor, min(ceiling, board['stock_num']))


def _apply_combo_impact(board, combo_size, side):
    """Adjust stock fair via Jacob's impact function when a combo order arrives."""
    normal_draw = float(np.random.normal(loc=0.5, scale=0.15))
    delta = (combo_size / board['stock_size']) * board['impact_function'] * normal_draw
    if side == 'bid':   # customer buying → fair moves up
        board['stock_num'] = round_to_cent(board['stock_num'] + delta)
    else:               # customer selling → fair moves down
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
    k = float(np.random.choice(_COMBO_K_LIST)) + np.random.normal(loc=0.0, scale=0.03)
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
    side, combo_price = _combo_customer_price(board, strike, side)

    # Apply impact only when the order is aggressive vs fair
    if (side == 'bid' and combo_price > fair_combo) or (side == 'offer' and combo_price < fair_combo):
        _apply_combo_impact(board, combo_size, side)

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
    """Same impact + price logic as generate_combo_order, for the make-market flow."""
    _clip_stock_fair(board)
    mult = float(np.random.choice(_COMBO_MULTIPLIERS))
    combo_size = int(round(board['stock_size'] * mult))
    if combo_size > 100:
        combo_size = int(round(combo_size / 10) * 10)

    side = _biased_side(board, f"{int(strike)} combo")
    fair_combo = board['stock_num'] - strike + board['rc_num']
    side, price = _combo_customer_price(board, strike, side)
    if (side == 'bid' and price > fair_combo) or (side == 'offer' and price < fair_combo):
        _apply_combo_impact(board, combo_size, side)
    return side, price, combo_size


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


def generate_options_market(board):
    """
    Generate a customer options market request for one of the two ITM options:
      - bw_strike call    price = implied_stock - strike + B/W
      - p_and_s_strike put  price = strike - implied_stock + P&S
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
    noise       = round_to_cent(float(np.random.uniform(-0.02, 0.04)))
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
    noise       = round_to_cent(float(np.random.uniform(-0.02, 0.04)))
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


def generate_middle_options_market(board):
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
    noise       = round_to_cent(float(np.random.uniform(-0.02, 0.04)))
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
        "fair":           fair,
        "delta":          delta,
        "size":           opt_size,
        "side":           side,
        "sentence":       f"{opt_size}x {option_label} – make a market",
        "speak":          speak,
        "order_kind":     "middle_options",
    }


def generate_directed_option_order_data(board, strike_f, option_type, preferred_side):
    """
    Generate a customer option order for any board strike with a preferred side.
    Uses delta-adjusted BS fair + edge pricing (same model as middle options).
    preferred_side is honoured with 85 % probability.
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
    noise       = round_to_cent(float(np.random.uniform(-0.02, 0.04)))
    total_edge  = option_edge + noise
    price       = round_to_cent(fair - total_edge) if side == 'bid' else round_to_cent(fair + total_edge)

    if abs(delta) > 1e-6:
        implied_stock = round_to_cent(board['stock_num'] + (price - fair) / delta)
    else:
        implied_stock = round_to_cent(board['stock_num'])

    if price < 0:
        price = abs(price)
        side = 'offer' if side == 'bid' else 'bid'

    if (side == 'bid' and price > fair) or (side == 'offer' and price < fair):
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


def _generate_spread_data(board, spread_types=None, strike_pool=None):
    """Core spread order generator shared by all spread market/order flows.

    spread_types: list of allowed spread kinds to draw from.  Defaults to all
    three: ['call_spread', 'put_spread', 'risk_reversal'].
    strike_pool: optional list of strikes to restrict pair selection.
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

    if (side == 'bid' and price > fair) or (side == 'offer' and price < fair):
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
    return jsonify({
        "stock_fair":      BOARD["stock_num"],
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



@app.route("/")
def index():
    return render_template(
        "index.html",
        stock_spread=BOARD["stock_spread"],
        rc=BOARD["rc"],
        strikes=BOARD["strikes"],
        info=BOARD["info"],
        highlight=BOARD["highlight"],
        stock_size=BOARD["stock_size"]
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
    BOARD = generate_opening_board()
    return redirect(url_for("index"))

@app.route("/make_market")
def make_market():
    strike = random.choice(BOARD['strikes'])
    side, customer_price, size = generate_customer_combo_price(BOARD, strike)

    order = {
        "strike": strike,
        "size": size,
        "side": side,
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
    order = generate_options_market(BOARD)
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

    if customer_side == "bid":
        if offer <= customer_price:
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
    order = generate_middle_options_market(BOARD)
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

    return jsonify({
        "type":          "order",
        "strike":        strike,
        "option_label":  option_label,
        "price":         customer_price,
        "implied_stock": _opt_implied(customer_price),
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

    order = generate_directed_option_order_data(BOARD, strike_f, option_type, preferred_side)
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
    order = _generate_spread_data(BOARD)
    return jsonify(order)


@app.route("/make_rr_market")
def make_rr_market():
    middle_strikes = BOARD['strikes'][1:4]  # inside_low, ATM, inside_high
    order = _generate_spread_data(BOARD, spread_types=['risk_reversal'], strike_pool=middle_strikes)
    return jsonify(order)


@app.route("/make_cs_ps_market")
def make_cs_ps_market():
    order = _generate_spread_data(BOARD, spread_types=['call_spread', 'put_spread'])
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

    return jsonify({
        "type":           "order",
        "k1":             k1,
        "k2":             k2,
        "spread_type":    spread_type,
        "spread_label":   spread_label,
        "price":          customer_price,
        "customer_price": customer_price,
        "implied_stock":  _implied(customer_price),
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
    # Start the worker thread
    t = threading.Thread(target=speech_worker, daemon=True)
    t.start()

    # use_reloader=False is important! 
    # If True, Flask starts two processes and the thread will break.
    app.run(debug=True, use_reloader=False, threaded=True)









