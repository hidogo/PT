import time, pickle, csv
from datetime import timedelta

STRATEGY_VERSION = "v1.10"

def _warn(msg):

    _lb = getattr(log, "warning", None) or getattr(log, "warn", None)
    try:
        if _lb is not None:
            _lb(msg)
        else:
            log.info("[WARN] " + str(msg))
    except Exception:
        try:
            log.info("[WARN] " + str(msg))
        except Exception:
            pass

def _skip_log(tag, sec, reason, msg, throttle_sec=None):

    try:
        d = getattr(g, 'skip_log_ts', None)
        if not isinstance(d, dict):
            d = {}; g.skip_log_ts = d
        key = '%s|%s|%s' % (tag, sec, reason)
        now = time.time()
        _sec = float(throttle_sec if throttle_sec is not None else BLS.get('skip_log_throttle_sec', 30.0) or 30.0)
        if now - float(d.get(key, 0.0) or 0.0) < _sec:
            return False
        d[key] = now
    except Exception:
        pass
    log.info(msg)
    return True

BLS = {
    'DO_ORDER': True,
    'universe': ['600570.XSHG', '603528.XSHG', '601188.XSHG'],
    'buy_score_min': 55.0,
    'ma5_pullback': True, 'ma5_loose_high': 1.00, 'ma5_core_only': True,
    'ma5_second_low_enabled': True,
    'ma5_touch_band': 0.02,
    'ma5_require_bs': False,
    'ma5_first_5d': False,
    'ma5_buy_score_min': 50.0,
    'ma5_buy_ratio': 0.10,
    'cold_secs': 60, 'daily_max_buy': 3,

    'EXPECT_ORDER': True,
    'tick_exp_enabled': True,
    'exp_order_pct': 0.10,
    'buy_chase_pct': 0.008,
    'price_precision': 2,
    'green_open_drop': -5.0,
    'debug_score': True,
    'debug_interval': 4,

    'scan_enabled': True,
    'max_watch': 50,
    'scan_batch': 600,
    'per_stock_cap': 60,
    'scan_min_chg': 3.0,
    'skip_st_pool': True,
    'state_save_interval': 60.0,
    'first_zt_rebuild_cap': 5,
    'first_zt_rebuild_tx_count': 200,
    'first_zt_rebuild_retry_sec': 30.0,
    'first_zt_rebuild_heartbeat_sec': 60.0,
    'first_zt_rebuild_timeout_min': 30.0,
    'first_zt_rebuild_max_attempts': 8,
    'restart_rebuild_1m_enabled': True,
    'sim_cash_base': 0.0,
    'sim_min_lot': 100,
    'skip_log_throttle_sec': 30.0,

    'scan_near_chg': 7.0,
    'scan_near_cap': 20,
    'scan_near_keep_rounds': 3,
    'tick_near_cap': 12,
    'scan_hot_first': True,

    'fast_up_ratio': 0.01,
    'seal_exceed_ratio': 1.2,
    'sell_half_ratio': 0.5,
    'sell_cold_secs': 30.0,
    'sell_urgent_floor': 1,
    'limit_down_main': 0.10,
    'limit_down_chinext': 0.20,
    'limit_down_bse': 0.30,
    'sell_pending_timeout': 120.0,
    'seal_fail_ratio': 0.333,
    'board_queue_cancel_seal_ratio': 0.333,
    'board_queue_cancel_bid_ratio': 0.5,
    'firstzt_min_seal': 200000.0,
    'firstzt_min_bids': 5,

    'break_sell_bid_level': 3,
    'break_sell_floor_ratio': 0.95,
    'seal_fail_ratio_unique': 0.25,
    'break2_half_ratio': 0.5,
    'reboard_buy_enabled': True,
    'reboard_until_minute': 30,
    'reboard_max_lianban': 2,
    'reboard_seal_min': 200000.0,
    'reboard_l2_big_min': 0.10,
    'tick_full_sell_enabled': True,
    'frame_sellscan_limit': 8,

    'p7_sell_enabled': True,
    'p7a_vol_ratio': 1.10,
    'p7a_half_ratio': 0.5,
    'p7b_board_min': 1.0,
    'p7b_surge_min': 1.5,
    'p7b_half_ratio': 0.5,
    'p7c_until_minute': 30,
    'p7c_surge_min': 1.5,
    'p7c_batch_cold_secs': 10.0,
    'p7c_active_threshold': 0.5,
    'hold_stand_cache_sec': 15.0,
    'hold_stand_log_sec': 60.0,

    'expectation_suffix': '.csv',
    'scan_interval': 1,
    'score_sell_clear': 30, 'score_sell_half': 50,

    'stop_loss_pct': 0.05, 'stop_loss_chinext': 0.07, 'stop_loss_star': 0.08, 'stop_loss_bse': 0.10,
    'elastic_max_buy_pct': 0.10,
    'elastic_max_buy_pct_bse': 0.15,
    'exp_sell_on_pending_miss': False,

    'p2e_sell_enabled': True,
    'p2e_theme_sell_enabled': True,
    'p2e_theme_drop_min': -2.0,
    'p2e_auction_drop_min': -2.0,
    'p2e_confirm_at': '09:24:45',
    'single_stock_cap': 0.30,
    'ordinary_buy_ratio': 0.10,
    'board_buy_budget_ratio': 0.20,
    'red_gate_enabled': False,
    'sentiment_enabled': False,
    'sentiment_warm_base': 0.55,
    'sentiment_warm_decay': 0.02,
    'sentiment_warm_min': 0.45,
    'sentiment_ice_ratio': 0.40,
    'sentiment_pos_cap_enabled': True,
    'ice_pos_pct': 0.40,
    'warm_pos_pct': 0.80,
    'warm_taper_start': 3,
    'warm_taper_step': 0.10,
    'warm_taper_min': 0.50,
    'red_ratio_buy_min': 0.55,

    'market_batch': 300,
    'market_red_ttl': 60.0,
    'market_red_ttl_fast': 30.0,
    'frame_market_limit': 2,
    'frame_market_limit_fast': 4,

    'emotion_cap_ice': 0.40,
    'emotion_cap_warm': 0.80,
    'emotion_cap_taper': 0.50,

    'core_buy_enabled': True,
    'core_max_lianban': 6,
    'core_sealed_skip': True,
    'core_buy_window_min': 30,
    'ma5_buy_window_min': 60,
    'exp_buy_window_min': 30,
    'pool_expect_enabled': True,
    'pool_expect_skip_st': True,
    'vwap_weak_grace_sec': 30,
    'vwap_weak_confirm_sec': 6,
    'vwap_weak_at_limit_exempt': True,
    'exp_entry_type_resync': True,
    'exp_meet_score_ready': True,
    'first_board_buy_enabled': True,
    'first_board_minute': 10,
    'first_board_seal_min': 200000.0,
    'dyn_unq_mid_skip': True,
    'dyn_unq_require_board_map': True,
    'dyn_unq_auction_member_cap': 15,
    'l2_big_enabled': True,
    'l2_big_amt_min': 1000000.0,
    'l2_big_amt_unit': 'shares',
    'l2_big_dir_enabled': True,
    'l2_big_dir_map': {'0': 'sell', '1': 'buy', '2': 'un', '3': 'un'},
    'l2_tickdir_enabled': True,
    'l2_tickdir_pages': 3,
    'l2_tickdir_pages_restart': 10,
    'l2_big_seed_onjoin_enabled': True,
    'l2_tickdir_pages_onjoin': 5,
    'l2_big_seed_onjoin_interval_sec': 60,
    'l2_big_seed_onjoin_px_sec': 0,
    'l2_big_seed_onjoin_max_per_frame': 5,
    'l2_big_seed_on_firstzt': True,
    'l2_big_seed_log': True,
    'l2_big_log_sec': 300,
    'l2_big_ratio_min': 0.10,
    'l2_big_bonus': 5.0,
    'l2_big_seen_cap': 20000,
    'tick_board_scan': True,
    'tick_board_member_cap': 10,

    'elastic_arb_enabled': True,
    'elastic_arb_window_minute': 20,
    'elastic_arb_min_yizi': 2,
    'elastic_arb_min_1m_surge': 3.0,
    'elastic_arb_min_change': 6.0,
    'elastic_arb_max_change': 10.0,
    'elastic_arb_min_change_bse': 8.0,
    'elastic_arb_max_change_bse': 15.0,
    'elastic_arb_max_open_change': 12.0,
    'elastic_arb_max_open_change_bse': 15.0,
    'elastic_arb_cache_ttl': 60.0,
    'gear_cache_ttl': 3.0,
    'm1_surge_cache_ttl': 30.0,

    'firsttx_enabled': True,
    'firsttx_near_px': 0.98,
    'firsttx_data_count': 200,

    'board_rank_enabled': True,
    'board_rank_top_n': 3,
    'board_rank_cache_ttl': 60.0,
    'board_rank_ttl_fast': 3.0,
    'board_rank_fast_until_minute': 30,

    'budget_log_enabled': True,
    'budget_log_heartbeat_sec': 60.0,
    'budget_log_event_sec': 30.0,
    'budget_log_on_over': True,
    'budget_log_on_degraded': True,
    'frame_snapshot_limit': 2,
    'frame_snapshot_fallback_cap': 5,
    'frame_tx_limit': 2,
    'l2_tx_fallback_enabled': True,
    'l2_tx_fallback_cap': 5,
    'frame_gear_limit': 15,
    'frame_m1_limit': 20,
    'frame_hist1d_limit': 10,
    'frame_board_limit': 6,
    'frame_blocks_limit': 10,
    'frame_bcode_limit': 20,

    'frame_board_limit_fast': 24,
    'frame_m1_limit_fast': 30,
    'frame_m1_prio_limit': 15,
    'frame_blocks_limit_fast': 20,
    'frame_day_limit': 8,
    'frame_day_limit_fast': 16,

    'elastic_top_enabled': True,
    'elastic_top_window_minute': 20,
    'elastic_top_min_strength': 2.0,
    'elastic_top_min_1m_surge': 2.0,
    'elastic_top_buy_before_pct': 10.0,
    'elastic_top_buy_before_pct_bse': 15.0,
    'elastic_top_cache_ttl': 30.0,
    'elastic_top_surge_top_n': 5,
    'elastic_top_member_cap': 20,
    'frame_snap_batch': 100,
    'board_concept_unified': True,

    'elastic_top_breakout_min_open': 1.0,
    'elastic_top_breakout_min_boost': 2.0,
    'elastic_top_max_trigger_per_day': 2,

    'elastic_top_stable_frames': 3,
    'elastic_top_lead_min': 0.5,
    'board_probe_enabled': True,

    'tick_sell_enabled': True,
    'break_sell_enabled': True,
    'seal_low_sell_enabled': True,
    'sealed_fresh_secs': 5.0,
    'sealed_offerqty_enabled': True,

    'score_base': 40,
    'vwap_penalty_per_30s': 1.0, 'vwap_daily_limit': 12,

    'sell_policy': {
        'hold_higher_tolerance': {'green_tol': 2.5, 'stop_adj': 1.3, 'score_clear_adj': 0.6, 'score_half_adj': 0.8},
        'fast_exit_on_weak':     {'green_tol': 0.5, 'stop_adj': 0.8, 'score_clear_adj': 1.05, 'score_half_adj': 1.0},
        'watch_break_sell':      {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 0.9, 'score_half_adj': 1.0},
        'break_weak_escape':     {'green_tol': 0.6, 'stop_adj': 0.7, 'score_clear_adj': 1.1, 'score_half_adj': 1.0},
        'vwap_follow':           {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0},
        'none':                  {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0},
    },

    'dyn_unq_enabled': True,
    'dyn_unq_window_minute': 30,
    'dyn_unq_follow_win_sec': 300,
    'dyn_unq_member_cap': 15,
    'dyn_unq_surge_top_n': 5,
    'dyn_unq_follower_min': 2,
    'dyn_unq_surge_pct': 1.5,
    'dyn_unq_sort_bonus': 2.0,
    'dyn_sweep_enabled': True,
    'dyn_sweep_window_minute': 15,
    'dyn_sweep_budget_ratio': 0.20,

    'zt_theme_dyn_enabled': True,
    'zt_theme_dyn_cache_sec': 15,
    'zt_theme_leader_sort_bonus': 1.5,
    'zt_theme_rank_bonus_step': 0.3,

    'zt_theme_ferment_enabled': True,
    'zt_theme_ferment_window_min': 25,
    'zt_theme_ferment_assist_min': 2,
    'zt_theme_ferment_hot_assist': 5,
    'zt_theme_ferment_front_bonus': 0.8,
    'zt_theme_ferment_sort_bonus': 0.5,
    'zt_theme_ferment_seal_min': 50000.0,

    'lb_senti_enabled': True,
    'lb_senti_cache_sec': 15.0,
    'lb_senti_cache_sec_after': 60.0,
    'lb_senti_high_min': 2,
    'lb_senti_high_max': 5,
    'lb_senti_promo_min': 0.60,
    'lb_senti_break_max': 0.20,
    'lb_senti_rotation_promo': 0.40,
    'lb_senti_rotation_break': 0.30,
    'lb_senti_new_dir_min': 2,
    'lb_senti_red_cold': 0.40,
    'lb_senti_t100_freeze': True,
    'lb_senti_participate_scale': 0.5,
    'lb_senti_cut_enabled': True,
    'lb_senti_cut_half_ratio': 0.5,
    'lb_senti_min_touch_ratio': 0.5,
    'lb_senti_hysteresis_sec': 60.0,

    'lb_senti_min_touch_ratio_before': 0.3,
    'lb_senti_min_touch_floor': 3,
    'lb_senti_hysteresis_sec_before': 30.0,
    'lb_senti_auction_ready_min': 0.6,
    'lb_senti_gate_all_buys_enabled': True,

    'unq_space_gate_enabled': True,
    'unq_space_min': 0.15,
    'lb_senti_rotate_low_bonus': 1.2,
    'lb_senti_rotate_mid_pen': -0.8,
    'lb_senti_rotate_high_pen': -0.6,
    'lb_senti_ice_low_bonus': 0.3,
    'lb_senti_high_bonus': 0.6,

    'exp_direction_enabled': True,
    'exp_direction_attack_bonus': 0.8,
    'exp_direction_avoid_hard_skip': True,
    'exp_direction_hot_front_only': True,
    'exp_direction_rotate_leader_exception': True,
    'exp_direction_log': True,
}

BONUS = {
    'auction_beat_history': 5, 'touched_limit_up_early': 6, 'volume_ratio_shrink': 2,
    'is_100day_high': 10, 'tag_bs': 5, 'tag_core': 5, 'tag_lb': 5,
}
PENALTY = {
    'open_low_5': 15, 'open_low_2': 8, 'open_low_0': 3, 'board_weak': 8,
}
ATK = {'a1': 6.0, 'a2': 3.0, 'a3': 2.0, 'main_threshold': 0.08}

def _sn(sec):

    sec = str(sec or '')
    if not sec:
        return sec
    nm = getattr(g, '_name_map', None)
    if nm is None:
        nm = {}; g._name_map = nm
    if sec not in nm:
        try:
            _got = get_stock_name(sec)
            nm[sec] = str(_got or '').strip()
        except Exception:
            nm[sec] = ''
    return ('%s(%s)' % (nm[sec], sec)) if nm[sec] else sec

def _snl(codes):

    return [_sn(c) for c in (codes or [])]

class DataHub(object):

    def __init__(self):
        self.cache = {}
        self.degraded = set()
        self._day = ''
        self.frame = {'token': -1, 'used': {}, 'over': {}}

    def reset(self, day=None):
        self.cache.clear(); self.degraded.clear()
        self.frame = {'token': -1, 'used': {}, 'over': {}}
        if day is not None:
            self._day = day

    def _maybe_reset(self):
        try:
            day = str(get_trading_day())
        except Exception:
            day = ''
        if day and day != self._day:
            self.cache.clear(); self.degraded.clear(); self._day = day
        token = int(time.time() / 3.0)
        if token != self.frame['token']:
            self.frame['token'] = token
            self.frame['used'] = {}
            self.frame['over'] = {}

    def spend(self, source, n=1, prio=0):

        self._maybe_reset()
        key = '%s_p' % source if prio else source
        limit = _source_limit(source, prio)
        used = self.frame['used'].get(key, 0) + n
        if used > limit:
            self.frame['over'][key] = self.frame['over'].get(key, 0) + 1
            return False
        self.frame['used'][key] = used
        return True

    def frame_report(self):

        parts = []
        for src, used in sorted(self.frame['used'].items()):
            base = src[:-2] if src.endswith('_p') else src
            if src.endswith('_p'):
                lim = BLS.get('frame_%s_prio_limit' % base, BLS.get('frame_%s_limit' % base, 'inf'))
            else:
                lim = BLS.get('frame_%s_limit' % base, 'inf')
            parts.append('%s=%d/%s' % (src, used, lim))
        over = self.frame.get('over') or {}
        if over:
            parts.append('over:%s' % ','.join('%s=%d' % (k, v) for k, v in sorted(over.items())))
        return ' '.join(parts)

    def cached(self, source, sec, ttl, fetch, budget=None, stale_ok=False, prio=0, single=False):

        self._maybe_reset()
        if single and isinstance(source, tuple):
            prefix = source[0]
            for k in [k for k in self.cache
                      if isinstance(k[0], tuple) and k[0][0] == prefix and k != (source, sec)]:
                del self.cache[k]
        key = (source, sec)
        hit = self.cache.get(key)
        if hit is not None and (time.time() - hit[0]) < ttl:
            return hit[1]
        if budget and not self.spend(budget, prio=prio):
            if stale_ok and hit is not None:
                return hit[1]
            return None
        try:
            v = fetch()
            self.cache[key] = (time.time(), v)
            return v
        except Exception:
            self.degraded.add(source)
            return None

    def tx_zt_batch(self, secs, frame_data):

        self._maybe_reset()
        secs = [s for s in (secs or []) if s]
        if not secs:
            return {}
        out = {}
        miss = []
        for sec in secs:
            ms = _tx_frame_zt_ms(sec, frame_data)
            if ms is not None:
                out[sec] = ms
            else:
                miss.append(sec)
        raw = self._tx_pull_raw(secs) or {}
        fields = raw.get('fields') or []
        for sec in miss:
            ms = _parse_tx_zt_ms(sec, raw.get(sec) or [], fields)
            if ms is not None:
                out[sec] = ms
        for sec in [s for s in out if raw.get(s)]:
            raw_ms = _parse_tx_zt_ms(sec, raw.get(sec) or [], fields)
            if raw_ms is not None and raw_ms < out[sec]:
                out[sec] = raw_ms
        try:
            _tx_big_feed(secs, fields, raw)
        except Exception:
            pass
        return out

    def _tx_pull_raw(self, secs):

        token = int(time.time() / 3.0)
        raw = self.cached(('tx_pull', token), '_frame_', 3.0,
                          lambda: get_individual_transaction(secs,
                                                             data_count=int(BLS.get('firsttx_data_count', 200)),
                                                             is_dict=True) or {}, budget='tx') or {}
        if not raw or not raw.get('fields'):
            return raw
        if not BLS.get('l2_tx_fallback_enabled', True):
            return raw
        try:
            miss = [s for s in secs if not raw.get(s)]
            if not miss:
                return raw
            cap = int(BLS.get('l2_tx_fallback_cap', 5))
            fields = list(raw.get('fields') or [])
            _fb = 0
            for c in miss:
                if _fb >= cap or not self.spend('tx'):
                    break
                _fb += 1
                try:
                    one = get_individual_transaction([c],
                                                     data_count=int(BLS.get('firsttx_data_count', 200)),
                                                     is_dict=True) or {}
                    rows = one.get(c) if isinstance(one, dict) else one
                    if not rows:
                        continue
                    f2 = one.get('fields') if isinstance(one, dict) else None
                    if f2 and fields and list(f2) != fields:
                        _i2 = {n: i for i, n in enumerate(f2)}
                        rows = [[row[_i2[n]] if n in _i2 and _i2[n] < len(row) else None
                                 for n in fields] for row in rows if isinstance(row, (list, tuple))]
                    elif f2 and not fields:
                        fields = list(f2)
                        raw['fields'] = fields
                    raw[c] = rows
                except Exception:
                    self.degraded.add('tx')
            if _fb:
                log.info('[tx-pull] req=%d got=%d missing=%d (fallback=%d)' % (len(secs), len(secs) - len(miss), len(miss), _fb))
        except Exception as e:
            _warn('tx_pull fallback fail %r' % e)
        return raw

    def snapshot(self, secs):

        self._maybe_reset()
        secs = [s for s in (secs or []) if s]
        if not secs:
            return {}
        got = {}
        if self.spend('snapshot'):
            try:
                sn = get_snapshot(secs)
                if isinstance(sn, dict):
                    got = sn
            except Exception:
                self.degraded.add('snapshot')
        fb_cap = int(BLS.get('frame_snapshot_fallback_cap', 5))
        _fb = 0
        for c in secs:
            d = got.get(c)
            if isinstance(d, dict):
                g.spot[c] = d
            else:
                if _fb >= fb_cap or not self.spend('snapshot'):
                    g.spot[c] = {}
                    continue
                _fb += 1
                try:
                    one = get_snapshot(c) or {}
                    if isinstance(one, dict) and one:
                        g.spot.update(one)
                    else:
                        g.spot[c] = {}
                except Exception:
                    g.spot[c] = {}
                    self.degraded.add('snapshot')
        return g.spot

def _source_limit(source, prio=0):

    if prio:
        return float(BLS.get('frame_%s_prio_limit' % source,
                             BLS.get('frame_%s_limit' % source, 1e9)))
    fast = False
    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            fast = True
    except Exception:
        pass
    if fast:
        k = 'frame_%s_limit_fast' % source
        if k in BLS and BLS[k]:
            return float(BLS[k])
        if source == 'gear':
            try:
                return float(min(len(_tick_targets()), 25))
            except Exception:
                pass
    return float(BLS.get('frame_%s_limit' % source, 1e9))

_DS = None

def _get_ds():
    global _DS
    if _DS is None:
        _DS = DataHub()
    return _DS

def initialize(context):
    set_universe(BLS['universe'])
    g.buy_log = {}; g.sold_log = {}
    g.daily = {'bought': [], 'sold': []}
    g.state_day = None
    g.spot = {}; g.last_ma5 = {}
    g.ma5_touch_day = None; g.ma5_touched = set()
    g.ma5_lifecycle_day = None; g.ma5_lows = {}
    _get_ds()
    g.one_word_open = set()
    g.one_word_marked_open = False
    g.rt_stats = {}
    g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}
    g.hist = {}
    g.bs_codes = {}
    g.first_board_fired = set()
    g.elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}
    g.elastic_top = {'day': '', 'top': '', 'ts': 0.0, 'tracked': set()}
    g.gear_cache = {}
    g.m1_surge_cache = {}
    g.now_dt = None
    g.bar_counter = 0
    g.vwap_below_since = {}

    g.pool_all = []
    g.pool_day = None
    g.watch = []
    g.near_scan = {}
    g.scan_order = []
    g.scan_order_day = None
    g.scan_round = 0
    g.selfwatch = []
    g.pool_static = []
    g.last_scan = 0
    g.scan_offset = 0
    g.auction_c = {}
    g.exp = {}
    g.exp_day = None
    g.seal_base = {}
    g.seal_bid_base = {}
    g.first_zt = {}
    g.first_zt_rebuild_pending = []
    g.first_zt_rebuild_retry_ts = {}
    g.first_zt_rebuild_ts = {}
    g.first_zt_rebuild_attempts = {}
    g.restart_rebuild_hb_ts = 0.0
    g.skip_log_ts = {}
    g.last_save_ts = 0.0
    g.st_set = set(); g.st_day = None
    g.st_skip_log_ts = 0.0
    g.dyn_unq = None
    g.break_sold = set()
    g.seal_sold = set()
    g.break2_sold = set()
    g.board_cancel_log = set()
    g.reboard_fired = False
    g.sealed_since = {}
    g.zt_lianban = {}
    g.zt_theme_authoritative = False
    g.zt_theme = {}
    g.zt_themes_of = {}
    g.zt_dyn_cache = {}
    g.zt_new_cache = {}
    g.zt_ferment_cache = {}
    g.zt_ferment_stage = {}
    g.zt_unmapped_n = 0
    g.lb_senti = {}
    g.lb_senti_cache = {}
    g.exp_file = {}
    g.exp_fired = set()
    g.pending = {}
    g.buy_commit = {}
    g.p7a_sold = set()
    g.p7b_sold = set()
    g.p7c_part = {}
    g.p7c_sold = set()
    g.hold_stand_cache = {}
    g.hold_stand_log = {}
    run_daily(context, auction_pre_confirm, time='09:25')
    run_daily(context, after_open_probe, time='09:31')
    run_daily(context, lb_senti_t100_freeze, time='10:00')
    run_daily(context, mid_probe, time='11:00')
    run_interval(context, p2e_auction_core_sell, seconds=3, interval_timer_ranges='09:15-09:25')
    log.info('buysell_core init version=%s universe=%s DO_ORDER=%s EXPECT_ORDER=%s sim_cash=%s' % (STRATEGY_VERSION, _snl(BLS['universe']), BLS['DO_ORDER'], BLS.get('EXPECT_ORDER', False), BLS.get('sim_cash_base', 0.0)))

def before_trading_start(context, data):
    _set_now(context)
    load_state()
    _today = str(get_trading_day())
    _restart_same_day = False
    if getattr(g, 'state_day', None) == _today:
        _restart_same_day = True

        g.daily = {'bought': [x for x in (g.daily.get('bought') or [])], 'sold': []}
        log.info('before_trading_start restore same-day daily=%s (restart)' % (_snl(g.daily.get('bought')),))
    else:
        g.daily = {'bought': [], 'sold': []}
        g.exp_fired = set()
        g.buy_commit = {}

    _fz_now = getattr(g, 'first_zt', None) or {}
    _stale_fz = [c for c, r in _fz_now.items() if str((r or {}).get('day') or '') != _today]
    if _stale_fz:
        log.info('[restart-guard] before_trading_start 发现跨日 first_zt %d 家 -> 清空重建' % len(_stale_fz))
        g.first_zt = {}
        g.auction_c = {}
    elif not _restart_same_day and _fz_now:
        log.info('[restart-guard] 跨日分支内存残留 first_zt %d 家 -> 清空' % len(_fz_now))
        g.first_zt = {}
        g.auction_c = {}
    g.sealed_warn = set()
    g.state_day = _today
    try:
        _reconcile_pending()
    except Exception:
        pass
    if _restart_same_day:
        try:
            _reconcile_daily_bought_slots()
        except Exception:
            pass
    _save_state()
    _load_expectation(merge=_restart_same_day)
    _load_zt_lianban()
    _load_sentiment()
    try:
        _load_boards()
    except Exception:
        pass
    if BLS.get('sentiment_pos_cap_enabled', False):
        _s = getattr(g, 'sentiment', None)
        _sm = '无'
        if _s:
            _sm = 'ice=%d warm_days=%d phase=%s' % (int(_s.get('ice') or 0), int(_s.get('warm_days') or 0), _s.get('phase') or '-')
        log.info('[pos-cap] 已启用：冰点上限=%.2f 回暖上限=%.2f 连续回暖>=%d 起递减%.2f/日 下限=%.2f；当前情绪基线：%s'
                 % (float(BLS.get('ice_pos_pct', 0.40)), float(BLS.get('warm_pos_pct', 0.80)),
                    int(BLS.get('warm_taper_start', 3)), float(BLS.get('warm_taper_step', 0.10)),
                    float(BLS.get('warm_taper_min', 0.50)), _sm))
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _sync_pool_static()
    try:
        _board_probe()
    except Exception:
        pass
    if _restart_same_day:
        if _hhmm() >= '09:25':
            g.exp_day = _today
        try:
            _synth_pool_expect()
            _synth_selfwatch_expect()
            _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
        except Exception:
            pass
        try:
            _mark_one_word_open()
            _l2_big_seed(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])), pages=int(BLS.get('l2_tickdir_pages_restart', 10)))
            _rebuild_first_zt_queue()
        except Exception:
            pass
    for sec in list(dict.fromkeys(BLS['universe'] + list(get_positions()))):
        _ma5_base4(sec)
    log.info('before_trading_start done positions=%s' % list(get_positions()))

def _maybe_roll_day():

    day = str(get_trading_day())
    if getattr(g, 'exp_day', None) == day:
        return False
    g.exp_day = day
    g.ma5_touch_day = day; g.ma5_touched = set()
    g.ma5_lifecycle_day = day; g.ma5_lows = {}
    g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.break_sold = set(); g.seal_sold = set(); g.break2_sold = set(); g.board_cancel_log = set(); g.reboard_fired = False; g.sealed_since = {}; g.gear_cache = {}; g.m1_surge_cache = {}; _get_ds().reset(); g.one_word_open = set(); g.one_word_marked_open = False; g.rt_stats = {}; g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}; g.zt_ferment_stage = {}; g.zt_unmapped_n = 0; g.lb_senti = {}; g.lb_senti_cache = {}
    g.near_scan = {}; g.scan_order = []; g.scan_order_day = None; g.scan_round = 0; g.scan_offset = 0
    g.first_zt_rebuild_pending = []; g.first_zt_rebuild_retry_ts = {}; g.first_zt_rebuild_ts = {}; g.first_zt_rebuild_attempts = {}; g.restart_rebuild_hb_ts = 0.0; g.last_save_ts = 0.0; g.st_skip_log_ts = 0.0; g.skip_log_ts = {}; g.budget_log_ts = 0.0; g.budget_over_acc = {}; g.budget_deg_logged = set()
    return True

def _budget_log():

    try:
        if not BLS.get('budget_log_enabled', True):
            return
        _dh = _get_ds()
        rep = _dh.frame_report()
        over = _dh.frame.get('over') or {}
        deg = list(_dh.degraded)
        acc = getattr(g, 'budget_over_acc', None)
        if not isinstance(acc, dict):
            acc = {}; g.budget_over_acc = acc
        for _k, _n in over.items():
            acc[_k] = float(acc.get(_k, 0.0) or 0.0) + float(_n or 0)
        ev = False
        if BLS.get('budget_log_on_over', True) and over:
            ev = True
            _skip_log('budget', 'over', 'frame', '[budget] %s' % rep, throttle_sec=BLS.get('budget_log_event_sec', 30.0))
        if BLS.get('budget_log_on_degraded', True) and deg:
            logged = getattr(g, 'budget_deg_logged', None)
            if logged is None:
                logged = set(); g.budget_deg_logged = logged
            new_deg = [x for x in deg if x not in logged]
            if new_deg:
                logged.update(new_deg)
                ev = True
                _skip_log('budget', 'degraded', 'frame', '[budget] %s degraded:%s' % (rep, ','.join(str(x) for x in new_deg[:5])), throttle_sec=BLS.get('budget_log_event_sec', 30.0))
        if ev:
            g.budget_log_ts = time.time()
            return
        hb = float(BLS.get('budget_log_heartbeat_sec', 60.0) or 0.0)
        if hb <= 0:
            return
        now = time.time()
        if now - float(getattr(g, 'budget_log_ts', 0.0) or 0.0) < hb:
            return
        g.budget_log_ts = now
        extra = ''
        if acc:
            extra = ' over_w%.0fs:%s' % (hb, ','.join('%s=%d' % (k, int(v)) for k, v in sorted(acc.items())))
            acc.clear()
        log.info('[budget] %s%s' % (rep, extra))
    except Exception:
        pass

def handle_data(context, data):
    _set_now(context)
    g.bar_counter += 1
    refresh_spot(context)
    if not getattr(g, 'one_word_marked_open', False):
        g.one_word_marked_open = True
        try:
            _mark_one_word_open()
        except Exception:
            pass
    if not getattr(g, 'l2_probed', False):
        try:
            _l2_probe(context)
        except Exception:
            pass
    if BLS.get('debug_score') and (g.bar_counter % BLS.get('debug_interval', 4)) == 0:
        dump_scores(context)
    if BLS.get('scan_enabled') and (g.bar_counter % BLS.get('scan_interval', 4)) == 0:
        _sync_watch(context)
    if BLS.get('selfwatch_enabled', True) and (g.bar_counter % BLS.get('selfwatch_sync_interval', 8)) == 0:
        _load_selfwatch(); _sync_pool_static()
    if _maybe_roll_day():
        for sec in list(get_positions()):
            _hold_exp_init(sec, force=True)
    try:
        if BLS.get('restart_rebuild_1m_enabled', True):
            _rebuild_first_zt_tick()
    except Exception as _e:
        _warn('restart-rebuild(1m) fail: %r' % _e)
    sell_manager(context)
    try:
        _board_queue_cancel_scan()
    except Exception as _e:
        _warn('board queue cancel(1m) fail: %r' % _e)
    _try_expected_buys(context)
    _now = time.time()
    if _now - float(getattr(g, 'last_save_ts', 0.0) or 0.0) >= float(BLS.get('state_save_interval', 60.0)):
        g.last_save_ts = _now
        _save_state()
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if BLS['ma5_pullback']:
        try_ma5_buy(context)
    try_core_buy(context)
    _try_first_board_buy_1m(context)
    _try_elastic_arb_buy(context)
    try:
        _try_elastic_top_buy(context)
    except Exception as e:
        _warn('elastic_top buy fail: %r' % e)
    try:
        _try_dyn_unq(context)
    except Exception as e:
        _warn('dyn_unq(1m) fail: %r' % e)
    try:
        _lb_senti_mid()
    except Exception as e:
        _warn('lb_senti(1m) fail: %r' % e)

def _hist_1d(sec):

    try:
        dh = _get_ds()
        return dh.cached('hist1d', sec, 60.0,
                         lambda: get_price(sec, start_date=None, end_date=None, count=120, frequency='1d'), budget='hist1d')
    except Exception:
        return None

def _date_key(v):

    try:
        fn = getattr(v, 'date', None)
        if callable(fn):
            v = fn()
        s = str(v)
        if len(s) >= 10 and s[4:5] == '-' and s[7:8] == '-':
            return s[:10]
        if len(s) >= 8 and s[:8].isdigit():
            return '%s-%s-%s' % (s[:4], s[4:6], s[6:8])
    except Exception:
        pass
    return ''

def _ma5_base4(sec):

    day = str(get_trading_day())
    cache = getattr(g, 'last_ma5', None)
    if not isinstance(cache, dict):
        cache = {}; g.last_ma5 = cache
    rec = cache.get(sec)
    if isinstance(rec, dict) and rec.get('day') == day:
        return float(rec.get('base4') or 0.0)
    df = _hist_1d(sec)
    if df is None:
        return None
    try:
        closes = [float(x) for x in list(df['close'])]
    except Exception:
        return None
    if len(closes) < 5:
        return None
    last_is_today = False
    try:
        last_is_today = (_date_key(df.index[-1]) == day)
    except Exception:
        pass
    vals = closes[-5:-1] if last_is_today else closes[-4:]
    if len(vals) < 4 or any(v <= 0 for v in vals):
        return None
    base4 = sum(vals) / 4.0
    cache[sec] = {'day': day, 'base4': base4}
    return base4

def _ensure_ma5(sec):

    base4 = _ma5_base4(sec)
    px = last_px(sec)
    if not base4 or not px or px <= 0:
        return None
    return (base4 * 4.0 + float(px)) / 5.0

def _ma5_at_price(sec, px):

    base4 = _ma5_base4(sec)
    try:
        px = float(px)
    except Exception:
        return None
    if not base4 or px <= 0:
        return None
    return (float(base4) * 4.0 + px) / 5.0

def _ma5_second_low(sec, px):

    cache = getattr(g, 'ma5_lows', None)
    if not isinstance(cache, dict):
        cache = {}; g.ma5_lows = cache
    try:
        px = float(px)
    except Exception:
        return None
    if px <= 0:
        return None
    vals = []
    for v in (cache.get(sec) or []):
        try:
            v = float(v)
            if v > 0:
                vals.append(v)
        except Exception:
            pass
    vals.append(px)
    vals.sort()
    vals = vals[:2]
    cache[sec] = vals
    return vals[1] if len(vals) >= 2 else None

def refresh_spot(context):

    secs = list(dict.fromkeys([x for x in (_pool() + list(get_positions())) if x]))
    if not secs:
        return
    try:
        snap_all = _get_snapshot_many(secs, len(secs))
    except Exception:
        snap_all = {}
    for c in snap_all:
        d = snap_all[c]
        if d:
            g.spot[c] = d

def last_px(sec):
    s = g.spot.get(sec)
    return float(s['last_px']) if s and s.get('last_px') else None

def pre_close(sec):
    s = g.spot.get(sec)
    return float(s['preclose_px']) if s and s.get('preclose_px') else None

def trade_open(sec):
    s = g.spot.get(sec)
    return not (s and s.get('trade_status') == 'ENDTR')

def my_cost(sec, positions):

    p = positions.get(sec)
    for key in ('cost_basis', 'cost_price', 'hold_cost_price', 'av_cost_price', 'avg_cost', 'cost'):
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is not None and str(v).strip() not in ('', 'None'):
                return float(v)
        except Exception:
            continue
    return 0.0

def get_stop_loss_pct(sec):
    if sec.startswith('300') or sec.startswith('301'):
        return BLS['stop_loss_chinext']
    if sec.startswith('688'):
        return BLS['stop_loss_star']
    if sec[:2] in ('43', '83', '87', '92'):
        return BLS['stop_loss_bse']
    return BLS['stop_loss_pct']

def _spot_ready(sec):

    s = g.spot.get(sec) or {}
    px = float(s.get('last_px') or 0.0)
    pre = float(s.get('preclose_px') or 0.0)
    return px > 0 and pre > 0

def _score_na_log(sec, why):

    try:
        gl = getattr(g, 'score_na_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.score_na_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0.0) < 60.0:
            return
        gl[sec] = now
        log.info('[score-na] %s data_na(%s) -> 评分未就绪(不评估买入)' % (_sn(sec), why))
    except Exception:
        pass

def score_now(sec):

    if not _spot_ready(sec):
        _score_na_log(sec, 'spot')
        return None
    _b_ready = _board_strength_info(sec)[1]
    if not _b_ready:
        _score_na_log(sec, 'board')
        return None
    base = float(BLS['score_base'])
    bonus = _static_bonus(sec)
    penalty = _static_penalty(sec)
    atk = _attack_bonus(sec)
    vp = _vwap_penalty(sec)
    ei = _external_internal(sec)
    raw = base + bonus - penalty + atk - vp + ei
    raw += _l2_big_bonus_pts(sec)
    raw = max(0.0, min(92.0, raw))
    if _is_debug(sec):
        log.info('score %s base=%.0f bonus=%.0f penalty=%.0f atk=%.0f vp=%.0f ei=%.0f -> %.1f' % (
            _sn(sec), base, bonus, penalty, atk, vp, ei, raw))
    return raw

def _is_debug(sec):
    return bool(getattr(g, 'debug_sec', None) == sec)

def _static_bonus(sec):

    b = 0.0
    if _auction_beat_history(sec):
        b += BONUS['auction_beat_history']
    if _touched_limit_early(sec) and not _broken_now(sec):
        b += BONUS['touched_limit_up_early']
    if _volume_ratio(sec) < 0.6:
        b += BONUS['volume_ratio_shrink']
    if _is_100day_high(sec):
        b += BONUS['is_100day_high']
    b += _board_bonus(sec)
    tags = _tags(sec)
    if 'BS' in tags: b += BONUS['tag_bs']
    if 'CORE' in tags: b += BONUS['tag_core']
    if 'LB' in tags: b += BONUS['tag_lb']
    return b

def _static_penalty(sec):
    p = 0.0
    chg = _auction_change(sec)
    if chg < -5.0: p += PENALTY['open_low_5']
    elif chg < -2.0: p += PENALTY['open_low_2']
    elif chg < 0.0: p += PENALTY['open_low_0']
    if _board_strength(sec) < -2.0:
        p += PENALTY['board_weak']
    return p

def _attack_bonus(sec):

    px = last_px(sec); pre = pre_close(sec)
    if not px or not pre or pre <= 0:
        return 0.0
    chg = px / pre - 1.0
    if chg < ATK['main_threshold']:
        return 0.0
    hm = _hhmm()
    if hm < '09:35': return ATK['a1']
    if hm < '09:45': return ATK['a2']
    if hm < '10:00': return ATK['a3']
    return 0.0

def _vwap_penalty(sec):

    px = last_px(sec); s = g.spot.get(sec)
    vwap = float(s.get('wavg_px') or 0.0) if s else 0.0
    if not px or not vwap:
        return 0.0
    if px >= vwap:
        getattr(g, 'vwap_below_since', {}).pop(sec, None)
        return 0.0
    now = _sec_age()
    below = getattr(g, 'vwap_below_since', {})
    start = below.get(sec)
    if start is None:
        start = now
        below[sec] = start
    return min(BLS['vwap_daily_limit'], max(0, (now - start) // 30) * BLS['vwap_penalty_per_30s'])

def _external_internal(sec):
    return 0.0

def _tags(sec):

    lb = _limitup_days(sec)
    tags = []
    if lb >= 2:
        tags.append('LB')
    if _is_100day_high(sec):
        tags.append('BS')
    if lb >= 3:
        tags.append('CORE')
    return tags

def _limit_threshold(sec):

    num = str(sec).split('.')[0]
    if num.startswith(('300', '301', '688', '689')):
        return 0.198
    if num.startswith(('8', '4', '92')):
        return 0.298
    return 0.098

def _today_zt(sec):

    px = last_px(sec); pre = pre_close(sec)
    return bool(px and pre and (px / pre - 1.0) >= _limit_threshold(sec))

def _limitup_days(sec):

    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec)
    if zt:
        return max(0, int(zt.get('board_cnt') or 0) + (1 if _today_zt(sec) else 0))
    df = _hist_1d(sec)
    if df is None or len(df) < 2:
        return 0
    closes = list(df['close'])
    cnt = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i - 1] >= closes[i - 2] and closes[i] >= closes[i - 1] * 1.098:
            cnt += 1
        else:
            break
    return cnt

def _mid_board_avoid(sec):

    en = g.exp_file.get(sec) or {}
    rd = str(en.get('role_detail') or '')
    if rd == 'mid_consecutive_limit_up':
        return True
    if rd in ('unique_high_board_consecutive', 'leading_first_board', 'first_board_arb'):
        return False

    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec)
    if zt:
        cnt = int(zt.get('board_cnt') or 0)
        if 2 <= cnt <= 5:
            if zt.get('unique_high'):
                return False
            if _dyn_theme_leader(sec):
                return False
            return True
    return False

def _is_100day_high(sec):
    df = _hist_1d(sec)
    if df is None or len(df) < 2:
        return False
    closes = list(df['close'])
    now = closes[-1]
    return now >= max(closes[:-1]) * 0.9999

def _volume_ratio(sec):

    try:
        s = g.spot.get(sec) or {}
        vr = float((s or {}).get('vol_ratio') or 0.0)
        if vr and vr > 0:
            return vr
    except Exception:
        pass
    df = _hist_1d(sec)
    if df is None or len(df) < 6:
        return 1.0
    vols = list(df['volume'])
    today = vols[-1] or 0.0
    avg5 = sum(vols[-6:-1]) / 5.0
    return (today / avg5) if avg5 > 0 else 1.0

AW="awaiting_auction"; PX="pending_exceed"; PM="pending_meet"; PS="pending_miss"
CX="confirmed_exceed"; CM="confirmed_meet"; CS="confirmed_miss"

def _overwrite_auction_c(secs):

    day = str(get_trading_day())
    for code in secs:
        try:
            s = g.spot.get(code) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            if pre > 0 and op > 0:
                g.auction_c[code] = (day, (op / pre - 1.0) * 100.0)
        except Exception:
            continue

def _auction_change(sec):

    day = str(get_trading_day())
    c = g.auction_c.get(sec)
    if c and c[0] == day:
        return c[1]
    pre = pre_close(sec)
    if not pre or pre <= 0:
        return 0.0
    chg = 0.0
    try:
        td = get_trend_data(stocks=sec) or {}
        d = td.get(sec) or {}
        hq = float(d.get("hq_px") or 0.0)
        if hq > 0:
            chg = (hq / pre - 1.0) * 100.0
        else:
            s = g.spot.get(sec); op = float(s.get("open_px") or 0.0) if s else 0.0
            if op <= 0:
                return 0.0
            chg = (op / pre - 1.0) * 100.0
    except Exception:
        s = g.spot.get(sec); op = float(s.get("open_px") or 0.0) if s else 0.0
        if op <= 0:
            return 0.0
        chg = (op / pre - 1.0) * 100.0
    g.auction_c[sec] = (day, chg)
    return chg

def _auction_ready(sec):

    day = str(get_trading_day())
    c = g.auction_c.get(sec)
    if c and c[0] == day:
        return True
    pre = pre_close(sec)
    s = g.spot.get(sec) or {}
    op = float(s.get('open_px') or 0.0)
    return bool(pre and pre > 0 and op > 0)

def _hist_window(sec):

    df = _hist_1d(sec)
    if df is None:
        return None, None
    try:
        return list(df["open"]), list(df["close"])
    except Exception:
        return None, None

def _yesterday_open_chg(sec):

    e = g.exp.setdefault(sec, {})
    has = e.get("has_yesterday_open"); val = e.get("yesterday_open_pct")
    if not has:
        en = g.exp_file.get(sec) or {}
        if en.get("has_yesterday_open"):
            has, val = True, en.get("yesterday_open_pct")
    if has:
        return float(val or 0.0), True
    opens, closes = _hist_window(sec)
    if opens and closes and len(opens) >= 2 and len(closes) >= 2 and opens[-1] and closes[-2]:
        return (opens[-1] / closes[-2] - 1.0) * 100.0, True
    return 0.0, False

def _auction_benchmark(sec):

    e = g.exp.setdefault(sec, {})
    if e.get("has_expected_auction"):
        v = float(e.get("expected_auction_change_pct") or 0.0)
        return v, (v > 0.0)
    en = g.exp_file.get(sec) or {}
    if en.get("has_expected_auction"):
        v = float(en.get("expected_auction_change_pct") or 0.0)
        return v, (v > 0.0)
    opens, closes = _hist_window(sec)
    if opens and closes and len(opens) >= 2 and len(closes) >= 2 and opens[-1] and closes[-2]:
        v = (opens[-1] / closes[-2] - 1.0) * 100.0
        return v, (v > 0.0)
    return 0.0, False

def _gear(sec):

    try:
        dh = _get_ds()
        v = dh.cached('gear', sec, float(BLS.get('gear_cache_ttl', 3.0)),
                      lambda: get_gear_price(sec) or {})
        return v if v is not None else {}
    except Exception:
        return {}

def _seal_metrics(sec):

    try:
        gp = _gear(sec)
        b = (gp.get("bid_grp") or {}).get(1) or [0, 0, 0]
        amt = float(b[1] or 0.0)
        cnt = int(b[2] or 0)
        return amt, cnt
    except Exception:
        return 0.0, 0

def _board_queue_cancel(sec, seal, bids):

    try:
        pp = (getattr(g, 'pending', None) or {}).get(sec) or {}
        if str(pp.get('side') or '') != 'buy' or int(pp.get('filled') or 0) > 0:
            return False
        if str(pp.get('status') or '') in ('CANCELLED', 'REJECTED', 'FILLED'):
            return False
        base = float(pp.get('seal_base') or 0.0) or 0.0
        if base <= 0:
            ft = (getattr(g, 'first_zt', None) or {}).get(sec) or {}
            base = float(ft.get('first_seal') or 0.0) or 0.0
        if base <= 0:
            return False
        ratio = float(BLS.get('board_queue_cancel_seal_ratio', 0.333) or 0.333)
        try:
            if _unique_stand(sec):
                ratio = float(BLS.get('seal_fail_ratio_unique', 0.25) or 0.25)
        except Exception:
            pass
        bbase = int(pp.get('seal_bid_base') or 0)
        bid_fail = bbase > 0 and bids < bbase * float(BLS.get('board_queue_cancel_bid_ratio', 0.5) or 0.5)
        if seal > 0 and not bid_fail and seal / base > ratio:
            return False
        ent = str(pp.get('no') or '')
        if not ent:
            return False
        _cc = getattr(g, 'board_cancel_log', None)
        if _cc is None:
            _cc = set(); g.board_cancel_log = _cc
        if sec in _cc:
            return False
        _cc.add(sec)
        try:
            cancel_order(ent)
        except Exception as _e:
            _warn('board queue cancel fail %s: %r' % (_sn(sec), _e))
            return False
        pp['status'] = 'CANCELLED'; pp['cancel_ts'] = time.time()
        _buy_commit_rel(sec, int(pp.get('qty') or 0), float(pp.get('limit') or 0.0))
        log.info('[board-cancel] %s 打板排单封单衰减 seal=%.0f base=%.0f ratio=%.2f bids=%d bbase=%d -> 撤单 ent=%s' % (
            _sn(sec), seal, base, (seal / base if base > 0 else 0.0), bids, bbase, ent))
        _release_buy_slot(sec)
        return True
    except Exception:
        return False

def _board_queue_cancel_scan():

    try:
        for sec, pp in list((getattr(g, 'pending', None) or {}).items()):
            if str(pp.get('side') or '') != 'buy' or int(pp.get('filled') or 0) > 0:
                continue
            if str(pp.get('status') or '') in ('CANCELLED', 'REJECTED', 'FILLED'):
                continue
            seal, bids = _seal_metrics(sec)
            try:
                _board_queue_cancel(sec, seal, bids)
            except Exception:
                continue
    except Exception:
        pass

def _is_elastic_20cm(sec):

    return str(sec).split('.')[0].startswith(('300', '301', '688', '689'))

def _is_bse(sec):

    num = str(sec).split('.')[0]
    return num.startswith(('8', '4', '92'))

def _is_elastic_eligible(sec):

    return _is_elastic_20cm(sec) or _is_bse(sec)

def _elastic_min_change(sec):

    return float(BLS.get('elastic_arb_min_change_bse', 8.0)) if _is_bse(sec) else float(BLS.get('elastic_arb_min_change', 6.0))

def _elastic_max_change(sec):

    return float(BLS.get('elastic_arb_max_change_bse', 15.0)) if _is_bse(sec) else float(BLS.get('elastic_arb_max_change', 10.0))

def _elastic_max_open_change(sec):

    return float(BLS.get('elastic_arb_max_open_change_bse', 15.0)) if _is_bse(sec) else float(BLS.get('elastic_arb_max_open_change', 12.0))

def _elastic_top_buy_before(sec):

    return float(BLS.get('elastic_top_buy_before_pct_bse', 15.0)) if _is_bse(sec) else float(BLS.get('elastic_top_buy_before_pct', 10.0))

def _elastic_big_bonus_pts(sec):

    try:
        return _l2_big_bonus_pts(sec)
    except Exception:
        return 0.0

def _fmt_big_ratio(big):

    return ('%.1f%%' % (big * 100.0)) if big >= 0.0 else 'NA'

def _max_elastic_buy_price(sec):

    if not _is_elastic_eligible(sec):
        return 0.0
    pre = pre_close(sec)
    if not pre or pre <= 0:
        return 0.0
    pct = float(BLS.get('elastic_max_buy_pct_bse', 0.15)) if _is_bse(sec) else float(BLS.get('elastic_max_buy_pct', 0.10))
    return _round_price(pre * (1 + pct))

def _sealed_now(sec):

    s = g.spot.get(sec) or {}
    try:
        gp = _gear(sec)
        ask = gp.get('ask_grp')
        has_book = isinstance(ask, dict)
        _tq = s.get('total_offerqty')
        has_tq = _tq is not None and str(_tq).strip() not in ('', 'None')
        if BLS.get('sealed_offerqty_enabled', True) and has_tq:
            return float(_tq) <= 0.0
        if has_book:
            if not ask:
                return True
            for row in ask.values():
                if isinstance(row, (list, tuple)) and len(row) >= 2 and float(row[1] or 0) > 0:
                    return False
            return True
        return False
    except Exception:
        return False

def _sealed_at_limit(sec):

    s = g.spot.get(sec) or {}
    px = last_px(sec); up = float(s.get('up_px') or 0.0)
    if not px or px <= 0 or up <= 0 or px < up * 0.998:
        return False
    if sec in getattr(g, 'one_word_open', set()):
        return True
    try:
        gp = _gear(sec)
        ask = gp.get('ask_grp')
        has_book = isinstance(ask, dict)
        _tq = s.get('total_offerqty')
        has_tq = _tq is not None and str(_tq).strip() not in ('', 'None')
        sealed_now = False
        if BLS.get('sealed_offerqty_enabled', True) and has_tq:
            sealed_now = (float(_tq) <= 0.0)
        elif has_book:
            if not ask:
                sealed_now = True
            else:
                for row in ask.values():
                    if isinstance(row, (list, tuple)) and len(row) >= 2 and float(row[1] or 0) > 0:
                        sealed_now = False; break
                else:
                    sealed_now = True
        else:
            return False
        if not sealed_now:
            if hasattr(g, 'sealed_since'):
                g.sealed_since.pop(sec, None)
            return False
        since = getattr(g, 'sealed_since', None)
        if since is None:
            since = {}; g.sealed_since = since
        if sec not in since:
            since[sec] = time.time()
            return False
        return (time.time() - since[sec]) >= float(BLS.get('sealed_fresh_secs', 5.0))
    except Exception:
        return False

def _block_sealed_buy(sec):

    if not _sealed_at_limit(sec):
        return False
    warned = getattr(g, 'sealed_warn', None)
    if warned is None:
        g.sealed_warn = set()
    if sec not in g.sealed_warn:
        g.sealed_warn.add(sec)
        log.info('[seal] %s sealed at limit -> no queue buy' % _sn(sec))
    return True

def _mark_one_word_open():

    if not getattr(g, 'one_word_open', None):
        g.one_word_open = set()
    cands = list(dict.fromkeys(
        list(g.watch or []) + list(g.pool_static or []) + list(g.selfwatch or []) +
        list((getattr(g, 'zt_lianban', None) or {}).keys()) + list((g.exp_file or {}).keys())))
    if not cands:
        return
    sn = None
    for sec in cands:
        try:
            if sec in g.one_word_open:
                continue
            s = g.spot.get(sec) or {}
            up = float(s.get('up_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            d = None
            if op <= 0 or up <= 0:
                if sn is None:
                    sn = _get_snapshot_many(cands, 300)
                d = (sn or {}).get(sec) or {}
                if op <= 0:
                    op = float(d.get('open_px') or 0.0)
                if up <= 0:
                    up = float(d.get('up_px') or 0.0)
            if up <= 0 or op < up * 0.998:
                continue

            if d is not None:
                s2 = g.spot.setdefault(sec, {})
                if s2.get('total_offerqty') is None and d.get('total_offerqty') is not None:
                    s2['total_offerqty'] = d['total_offerqty']
                if s2.get('total_bidqty') is None and d.get('total_bidqty') is not None:
                    s2['total_bidqty'] = d['total_bidqty']
                s = s2
            _tq = s.get('total_offerqty')
            _tb = s.get('total_bidqty')
            if _sealed_now(sec):
                g.one_word_open.add(sec)

                if float(g.seal_base.get(sec, 0.0) or 0.0) <= 0 and _tb is not None:
                    try:
                        _amt = float(_tb or 0.0)
                        if _amt > 0:
                            _seal0, _bids0 = _seal_metrics(sec)
                            if _seal0 > 0 and (_amt > _seal0 * 5.0 or _amt < _seal0 * 0.2):
                                log.info('[seal] %s 快照封单口径待核对 tb=%.0f seal=%.0f -> 等 L2 base_init' % (
                                    _sn(sec), _amt, _seal0))
                            else:
                                g.seal_base[sec] = _amt
                    except Exception:
                        pass
                log.info('[seal] %s 一字板(开=涨停价且无卖盘) sell1=%s buy1=%s -> 买入不排队' % (_sn(sec), _tq, _tb))
            else:
                log.info('[seal] %s 开=涨停价 sell1=%s buy1=%s -> playable(非真一字, 可参与)' % (_sn(sec), _tq, _tb))
        except Exception:
            continue

def _two_1m_break(sec):

    try:
        dh = _get_ds()
        v = dh.cached('m1_break', sec, 3.0, lambda: _calc_two_1m_break(sec), budget='m1', prio=1)
        return bool(v)
    except Exception:
        return False

def _calc_two_1m_break(sec):

    try:
        df = get_price(sec, start_date=None, end_date=None, count=8, frequency="1m")
        if df is None or len(df) < 2:
            return False
        open_px = float(df["open"].iloc[0] or 0.0)
        if open_px <= 0:
            return False
        thr = open_px * (1 + float(BLS.get("fast_up_ratio", 0.01)))
        mid = (df["close"] + df["high"]) / 2.0
        q = [bool(x) for x in (mid >= thr)]
        return q.count(True) >= 2 and bool(q) and q[-1]
    except Exception:
        return False

def _limit_up_within_1m(sec):

    s = g.spot.get(sec)
    px = last_px(sec); up = float(s.get("up_px") or 0.0) if s else 0.0
    if not px or px <= 0 or up <= 0 or px < up * 0.998:
        return False
    hm = _hhmm()
    return hm in ("09:30", "09:31", "09:32")

def _below_vwap(sec):
    s = g.spot.get(sec)
    vwap = float(s.get("wavg_px") or 0.0) if s else 0.0
    px = last_px(sec)
    return bool(px and vwap and px < vwap)

def _below_vwap_confirm(sec):

    try:
        s = g.spot.get(sec)
        vwap = float(s.get("wavg_px") or 0.0) if s else 0.0
        up = float(s.get("up_px") or 0.0) if s else 0.0
        px = last_px(sec)
        if not (px and vwap and px < vwap):
            p = getattr(g, 'below_vwap_pending', None)
            if p:
                p.pop(sec, None)
            return False
        pending = getattr(g, 'below_vwap_pending', None)
        if pending is None:
            pending = {}; g.below_vwap_pending = pending
        if BLS.get('vwap_weak_at_limit_exempt', True) and up > 0 and px >= up * 0.998:
            pending.pop(sec, None)
            return False
        age = _sec_age()
        grace = float(BLS.get('vwap_weak_grace_sec', 30))
        confirm = float(BLS.get('vwap_weak_confirm_sec', 6))
        if age <= grace:
            if sec not in pending:
                pending[sec] = age
                log.info('[exp-rt] %s below_vwap 首帧待确认 vwap=%.3f px=%.3f age=%.0fs (不判弱)' % (_sn(sec), vwap, px, age))
            return False
        first_age = float(pending.get(sec) or 0.0)
        if not first_age or age - first_age < confirm:
            return False
        pending.pop(sec, None)
        log.info('[exp-rt] %s below_vwap 连续弱确认 vwap=%.3f px=%.3f age=%.0fs -> 放弃' % (_sn(sec), vwap, px, age))
        return True
    except Exception:
        return False

def _eval_auction(sec):
    e = g.exp.setdefault(sec, {})
    if e.get("entry_type") == "one_word":
        return AW, ["one_word_requires_seal"]
    chg = _auction_change(sec)

    if chg == 0.0 and not _auction_ready(sec):
        return AW, ["auction_data_not_ready"]
    if chg < 0:
        return PS, ["auction_green_open"]
    yopen, has = _yesterday_open_chg(sec)
    if has and chg > yopen:
        return PX, ["auction_higher_than_yesterday"]
    return PM, ["auction_small_open"]

def _calc_intraday_bars_ready(sec):

    try:
        df = get_price(sec, start_date=None, end_date=None, count=8, frequency="1m")
        return bool(df is not None and len(df) >= 2)
    except Exception:
        return False

def _intraday_ready(sec):

    return bool(_intraday_ready_detail(sec))

def _intraday_ready_detail(sec):

    try:
        s = g.spot.get(sec) or {}
        if (float(s.get('last_px') or 0.0) > 0 and float(s.get('open_px') or 0.0) > 0
                and float(s.get('wavg_px') or 0.0) > 0):
            return 'spot'
        dh = _get_ds()
        if dh.cached('m1_ready', sec, 3.0, lambda: _calc_intraday_bars_ready(sec), budget='m1', prio=1):
            return '1m'
        return ''
    except Exception:
        return ''

def _intraday_confirmed_ready(sec):

    try:
        dh = _get_ds()
        if dh.cached('m1_ready2', sec, 3.0, lambda: _calc_intraday_bars_ready(sec), budget='m1', prio=1):
            return True
        if _spot_ready(sec) and BLS.get('exp_meet_score_ready', True):
            try:
                return bool(dh.cached('board_ready2', sec, 5.0,
                                      lambda: _board_strength_info(sec)[1], budget='m1', prio=1))
            except Exception:
                return False
        return False
    except Exception:
        return False

def _eval_intraday(sec, auction_status):
    if auction_status in (PS, CS):
        return CS, ["from_auction"]
    if auction_status == AW:
        return PM, ["auction_data_not_ready"]
    if auction_status in (PM, PX) and not _intraday_ready(sec):
        return PM, ["intraday_data_not_ready"]
    if _two_1m_break(sec) and auction_status in (PX, CX):
        return CX, ["two_1m_break"]
    if _below_vwap_confirm(sec):
        return CS, ["break_vwap"]
    return CM, ["held_vwap"]

def _hold_exp_init(sec, force=False):

    sec = _norm_sec(sec) or sec
    e = g.exp.setdefault(sec, {})
    _en = g.exp_file.get(sec) or {}
    for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct',
               'seal_amount_t0', 'sell_policy_hint'):
        if _en.get(_k) is not None:
            e[_k] = _en[_k]
    if not e.get('entry_type'):
        e['entry_type'] = 'one_word' if _is_one_word_open(sec) else 'normal'
    if not e.get('side'):
        e['side'] = 'hold'
    if force or e.get('auction_status') is None:
        try:
            e['auction_status'] = _eval_auction(sec)[0]
        except Exception:
            e['auction_status'] = PM
    if force or e.get('status') is None:
        try:
            e['status'] = _eval_intraday(sec, e.get('auction_status') or PM)[0]
        except Exception:
            e['status'] = CM
    if force or not e.get('_hold_inited'):
        e['_hold_inited'] = True
        e['_hold_ts'] = time.time()
        log.info('[hold] %s 持仓预期管理初始化 entry_type=%s auction_status=%s status=%s sell_policy=%s' % (
            _sn(sec), e.get('entry_type'), e.get('auction_status'), e.get('status'),
            e.get('sell_policy_hint') or 'none'))
    return e

def _exp_one_word(sec, quiet=False):

    seal, bids = _seal_metrics(sec)
    base = (g.seal_base or {}).get(sec, 0.0)
    bbase = (g.seal_bid_base or {}).get(sec, 0)
    if base <= 0:
        if seal <= 0:

            return AW, ["seal_data_not_ready"]
        g.seal_base[sec] = seal
        g.seal_bid_base[sec] = bids
        return AW, ["seal_base_init"]
    ratio = seal / base if base > 0 else 0.0
    bid_fail = False
    if BLS.get("seal_bid_enabled", True) and bbase > 0 and bids < bbase * float(BLS.get("seal_bid_fail_ratio", 0.5)):
        bid_fail = True
    if ratio <= float(BLS["seal_fail_ratio"]) or bid_fail:
        if not quiet:
            log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d bbase=%d bid_fail=%s -> CS" % (_sn(sec), seal, base, ratio, bids, bbase, bid_fail))
        return CS, ["seal_fail"]
    if ratio >= float(BLS["seal_exceed_ratio"]):
        if not quiet:
            log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CX" % (_sn(sec), seal, base, ratio, bids))
        return CX, ["seal_increase"]
    if not quiet:
        log.info("[seal] %s seal=%.0f base=%.0f ratio=%.2f bids=%d -> CM" % (_sn(sec), seal, base, ratio, bids))
    return CM, ["seal_within"]

def _unique_stand(sec):

    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        if zt.get('unique_high'):
            return True
        return _dyn_unq_confirmed(sec)
    except Exception:
        return False

def _broken_now(sec):

    try:
        return bool(((g.first_zt or {}).get(sec) or {}).get('break'))
    except Exception:
        return False

def _auction_beat_history(sec):

    df = _hist_1d(sec)
    if df is None or len(df) < 21:
        return False
    opens = list(df['open']); closes = list(df['close'])
    opens = opens[-(21):]
    hist_open_chg = sum((opens[i] / opens[i - 1] - 1.0) for i in range(1, len(opens))) / (len(opens) - 1)
    return _auction_change(sec) > hist_open_chg * 100.0 + 0.5

def _touched_limit_early(sec):

    s = g.spot.get(sec)
    px = last_px(sec); up = float(s.get('up_px') or 0.0) if s else 0.0
    return bool(px and up and px >= up * 0.998 and _hhmm() < '10:00')

def _board_bonus(sec):

    st = _board_strength(sec)
    if st > 3.0: return 15.0
    if st > 1.0: return 10.0
    if st > 0.0: return 5.0
    if st == 0.0: return 0.0
    if st > -1.0: return -5.0
    if st > -3.0: return -10.0
    return -15.0

def _board_refresh_ttl():

    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            return float(BLS.get('board_rank_ttl_fast', 3.0))
    except Exception:
        pass
    return float(BLS.get('board_rank_cache_ttl', 60.0))

def _fetch_board_code(sec):

    try:
        blocks = get_stock_blocks(sec) or {}
        for lst in blocks.values():
            if isinstance(lst, list):
                for row in lst:
                    if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                        return str(row[0]).strip()
    except Exception:
        pass
    return None

def _board_code_of(sec):

    try:
        dh = _get_ds()
        return dh.cached('bcode', sec, 3600.0, lambda: _fetch_board_code(sec), budget='bcode')
    except Exception:
        return None

def _fetch_board_chgs(board_code):

    chgs = []
    try:
        mem = [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board_code)) or [])[:20]) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        for m in mem:
            try:
                d = sn.get(m) or {}
                pre = float(d.get('preclose_px') or 0.0)
                px = float(d.get('last_px') or 0.0)
                if pre > 0:
                    chgs.append(px / pre - 1.0)
            except Exception:
                continue
    except Exception:
        chgs = []
    return tuple(chgs)

def _board_strength_by_code(board_code):

    try:
        dh = _get_ds()
        v = dh.cached('board_chgs', str(board_code), _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(board_code), budget='board', stale_ok=True)
        chgs = list(v) if v is not None else []
        return (sum(chgs) / len(chgs)) * 100.0 if chgs else 0.0
    except Exception:
        return 0.0

def _board_member_changes_api(sec):

    b = _board_code_of(sec)
    if not b:
        return []
    try:
        dh = _get_ds()
        v = dh.cached('board_chgs', b, _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(b), budget='board', stale_ok=True)
        return list(v) if v is not None else []
    except Exception:
        return []

def _board_member_changes(sec):

    try:
        if not _concept_active():
            return _board_member_changes_api(sec)
    except Exception:
        return _board_member_changes_api(sec)
    b = _concept_strong_board(sec)
    if b is None:
        return _board_member_changes_api(sec)
    mem = _board_members_file(b, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return []
    snap = _concept_snap_for(b, mem)
    chgs = []
    for m in mem:
        try:
            d = snap.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre > 0 and px > 0:
                chgs.append(px / pre - 1.0)
        except Exception:
            continue
    return chgs

def _board_strength_api(sec):

    b = _board_code_of(sec)
    return _board_strength_by_code(b) if b else 0.0

def _concept_strong_board(sec):

    try:
        if not _concept_active():
            return None
    except Exception:
        return None
    best_b = None; best_st = None
    for b in _concept_boards_of(sec):
        try:
            st = _concept_board_strength(b)
        except Exception:
            continue
        if best_b is None or st > best_st:
            best_b, best_st = b, st
    return best_b

def _board_strength_by_concept(sec):

    try:
        if not _concept_active():
            return _board_strength_api(sec)
    except Exception:
        return _board_strength_api(sec)
    b = _concept_strong_board(sec)
    return _concept_board_strength(b) if b else 0.0

def _board_strength(sec):

    return _board_strength_by_concept(sec)

def _board_strength_by_code_info(board_code):

    try:
        dh = _get_ds()
        v = dh.cached('board_chgs', str(board_code), _board_refresh_ttl(),
                      lambda: _fetch_board_chgs(board_code), budget='board', stale_ok=True)
        chgs = list(v) if v is not None else []
        if not chgs:
            return 0.0, False
        return (sum(chgs) / len(chgs)) * 100.0, True
    except Exception:
        return 0.0, False

def _concept_board_strength_info(board):

    try:
        if not _concept_active():
            return _board_strength_by_code_info(board)
    except Exception:
        return _board_strength_by_code_info(board)
    mem = _board_members_file(board, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return 0.0, False
    snap = _concept_snap_for(board, mem)
    s = 0.0; n = 0
    for m in mem:
        try:
            d = snap.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre > 0 and px > 0:
                s += px / pre - 1.0; n += 1
        except Exception:
            continue
    if n == 0:
        return 0.0, False
    return (s / n) * 100.0, True

def _board_strength_info(sec):

    try:
        if _concept_active():
            b = _concept_strong_board(sec)
            if b is None:
                return (0.0, True) if not _concept_boards_of(sec) else (0.0, False)
            return _concept_board_strength_info(b)
        b = _board_code_of(sec)
        if not b:
            return 0.0, True
        return _board_strength_by_code_info(b)
    except Exception:
        return 0.0, True

def _compute_board_rank(boards):

    sts = []
    for b in boards:
        try:
            sts.append((_board_strength_by_code(b), b))
        except Exception:
            continue
    sts.sort(key=lambda kv: kv[0], reverse=True)
    return {b for _, b in sts[:int(BLS.get('board_rank_top_n', 3))]}

def _compute_concept_board_rank(boards):

    sts = []
    for b in boards:
        try:
            sts.append((_concept_board_strength(b), b))
        except Exception:
            continue
    sts.sort(key=lambda kv: kv[0], reverse=True)
    return {b for _, b in sts[:int(BLS.get('board_rank_top_n', 3))]}

def _board_rank_cand_src(secs):

    try:
        if _concept_active():
            src = _elastic_top_cand_src()
            if src:
                return src
    except Exception:
        pass
    return [s for s in (secs or []) if s]

def _board_rank_top3_set(secs):

    secs = [s for s in (secs or []) if s]
    if not secs:
        return set()
    if not _concept_active():
        boards = sorted({b for b in (_board_code_of(s) for s in secs) if b})
        if not boards:
            return set()
        try:
            dh = _get_ds()
            token = '|'.join(boards)
            v = dh.cached(('board_rank', token), '_', _board_refresh_ttl(),
                          lambda: _compute_board_rank(boards), single=True)
            return v if v is not None else set()
        except Exception:
            return set()
    src = _board_rank_cand_src(secs)
    boards = sorted({b for s in src for b in _concept_boards_of(s) if b})
    if not boards:
        return set()
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('board_rank_c', token), '_', _board_refresh_ttl(),
                      lambda: _compute_concept_board_rank(boards), single=True)
        return v if v is not None else set()
    except Exception:
        return set()

def _compute_board_top1_lead(boards):

    best = None; best_st = None; second_st = None
    for b in boards:
        try:
            st = _board_strength_by_code(b)
        except Exception:
            continue
        if best is None or st > best_st:
            second_st = best_st
            best, best_st = b, st
        elif second_st is None or st > second_st:
            second_st = st
    if best_st is None:
        return (None, 0.0)
    return (best, best_st - (second_st if second_st is not None else 0.0))

def _board_rank_top1(secs):

    secs = [s for s in (secs or []) if s]
    if not secs:
        return (None, 0.0)
    boards = sorted({b for s in secs for b in _boards_of(s) if b})
    if not boards:
        return (None, 0.0)
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('board_top1', token), '_', _board_refresh_ttl(),
                      lambda: _compute_board_top1_lead(boards), single=True)
        if isinstance(v, tuple) and len(v) == 2:
            return v
        return (v, 0.0)
    except Exception:
        return (None, 0.0)

def _board_rank_top3(sec, secs):

    try:
        if not _concept_active():
            b = _board_code_of(sec)
            if not b:
                return False
            return b in _board_rank_top3_set(secs)
        top3 = _board_rank_top3_set(secs)
        if not top3:
            return False
        return any(b in top3 for b in _concept_boards_of(sec))
    except Exception:
        return False

def _near_limit_cands(secs):

    near_px = float(BLS.get('firsttx_near_px', 0.98))
    out = []
    for s in secs:
        try:
            d = g.spot.get(s) or {}
            last = float(d.get('last_px') or 0.0); up = float(d.get('up_px') or 0.0)
            if last > 0 and up > 0 and last >= up * near_px and not _is_one_word_open(s):
                out.append(s)
        except Exception:
            continue
    return out

def _red_ratio(sec):

    chgs = _board_member_changes(sec)
    up = sum(1 for x in chgs if x > 0)
    dn = sum(1 for x in chgs if x < 0)
    denom = up + dn
    return float(up) / denom if denom else 0.5

def _market_red_ttl():

    try:
        if _min_age() <= int(BLS.get('board_rank_fast_until_minute', 30)):
            return float(BLS.get('market_red_ttl_fast', 30.0))
    except Exception:
        pass
    return float(BLS.get('market_red_ttl', 60.0))

def _fetch_market_red(pool):

    batch = max(int(BLS.get('market_batch', 300)), 1)
    up = dn = 0
    t0 = time.time()
    n_batch = 0
    for i in range(0, len(pool), batch):
        chunk = pool[i:i + batch]
        n_batch += 1
        try:
            sn = get_snapshot(chunk)
            if not isinstance(sn, dict):
                continue
        except Exception:
            continue
        for code, d in sn.items():
            try:
                pre = float(d.get('preclose_px') or 0.0)
                px = float(d.get('last_px') or 0.0)
                if pre <= 0 or px <= 0:
                    continue
                if px > pre:
                    up += 1
                elif px < pre:
                    dn += 1
            except Exception:
                continue
    denom = up + dn
    if denom <= 0:
        log.info('[market-red] 无有效样本（全量分片 %d 批）-> None' % n_batch)
        return None
    ratio = float(up) / denom
    log.info('[market-red] 全市场红盘比=%.2f%% up=%d dn=%d 批=%d 样本=%d 耗时=%.1fs'
             % (ratio * 100.0, up, dn, n_batch, denom, time.time() - t0))
    return ratio

def _market_red_ratio():

    try:
        day = str(get_trading_day())
        if getattr(g, 'pool_day', '') != day:
            try:
                g.pool_all = [x for x in (_norm_sec(c) for c in (get_Ashares() or [])) if x]
                g.pool_day = day
            except Exception as e:
                _warn('market-red get_Ashares fail: %r' % e)
                g.pool_all = []
        pool = list(g.pool_all or [])
        if not pool:
            return None
        dh = _get_ds()
        return dh.cached(('mkt_red', day), '_mkt_', _market_red_ttl(),
                         lambda: _fetch_market_red(pool), budget='market', stale_ok=True)
    except Exception as e:
        _warn('market-red fail: %r' % e)
        return None

def _sentiment_warm(sec):

    if not BLS.get('sentiment_enabled', False):
        return None
    s = getattr(g, 'sentiment', None)
    if not s or not s.get('ice'):
        return None
    red = _market_red_ratio()
    if red is None:
        log.info('[sentiment] %s 全市场红盘比缺失 -> 保守不放行' % _sn(sec))
        return False
    ice_ratio = float(BLS.get('sentiment_ice_ratio', 0.40))
    if red < ice_ratio:
        log.info('[sentiment] %s 继续冰点 red=%.2f (<%.2f) 等下一交易日再验证回暖' % (_sn(sec), red, ice_ratio))
        return False
    streak = max(int(s.get('ice_streak') or 1), 1)
    th = max(float(BLS.get('sentiment_warm_min', 0.45)),
             float(BLS.get('sentiment_warm_base', 0.55)) - streak * float(BLS.get('sentiment_warm_decay', 0.02)))
    warm = red >= th
    log.info('[sentiment] %s streak=%d red=%.2f th=%.2f -> %s' % (_sn(sec), streak, red, th, '回暖' if warm else '未回暖'))
    return warm

def _buy_red_ok(sec):

    if not BLS.get('red_gate_enabled', False):
        return True
    if _red_ratio(sec) < BLS.get('red_ratio_buy_min', 0.55):
        return False
    w = _sentiment_warm(sec)
    return True if w is None else w

def _pos_value(p, sec):

    try:
        v = p.get('market_value') if isinstance(p, dict) else getattr(p, 'market_value', None)
        if v:
            return float(v)
        amt = float(p.get('amount') if isinstance(p, dict) else getattr(p, 'amount', 0) or 0)
        last = float(p.get('last_sale_price') if isinstance(p, dict) else getattr(p, 'last_sale_price', 0) or 0)
        if amt and last:
            return amt * last
        px = last_px(sec) or 0.0
        return amt * px
    except Exception:
        return 0.0

def _warm_cap(s):

    warm_days = int(s.get('warm_days') or 0)
    divergence = int(s.get('divergence') or 0)
    taper_start = int(BLS.get('warm_taper_start', 3))
    step = float(BLS.get('warm_taper_step', 0.10))
    cap = float(BLS.get('warm_pos_pct', 0.80)) - max(0, warm_days - taper_start + 1) * step
    cap = max(cap, float(BLS.get('warm_taper_min', 0.50)))
    if warm_days >= taper_start:
        n_taper = max(0, warm_days - taper_start + 1)
    elif divergence:
        n_taper = 1
    else:
        n_taper = 0
    cap = float(BLS.get('warm_pos_pct', 0.80)) - n_taper * step
    cap = max(cap, float(BLS.get('warm_taper_min', 0.50)))
    if n_taper > 0:
        log.info('[pos-cap] 分歧保护：divergence=%d warm_days=%d -> cap=%.2f' % (divergence, warm_days, cap))
    return cap

def _emotion_cap(s):

    emo = str(s.get('emotion') or '').strip()
    if not emo:
        return None
    ice = bool(s.get('ice'))
    cap_ice = float(BLS.get('emotion_cap_ice', 0.40))
    cap_warm = float(BLS.get('emotion_cap_warm', 0.80))
    cap_tap = float(BLS.get('emotion_cap_taper', 0.50))
    if emo in ('冰点', '偏冷'):
        return cap_ice
    if emo in ('回暖', '发酵'):
        if ice:
            log.info('[sentiment] 冲突: emotion=%s 但 ice=%d -> 规则冰点优先(保守)' % (emo, int(ice)))
            return cap_ice
        return cap_warm
    if emo in ('高潮', '过热'):
        return cap_tap
    return None

def _sentiment_pos_cap(context, sec):

    if not BLS.get('sentiment_pos_cap_enabled', False):
        return None
    s = getattr(g, 'sentiment', None)
    if not s:
        return None
    if s.get('ice'):
        red = _market_red_ratio()
        streak = max(int(s.get('ice_streak') or 1), 1)
        th = max(float(BLS.get('sentiment_warm_min', 0.45)),
                 float(BLS.get('sentiment_warm_base', 0.55)) - streak * float(BLS.get('sentiment_warm_decay', 0.02)))
        if red is None:
            cap = float(BLS.get('ice_pos_pct', 0.40))
            note = 'mkt-red=None(降级冰点)'
        else:
            cap = float(BLS.get('ice_pos_pct', 0.40)) if red < th else _warm_cap(s)
            note = 'mkt-red=%.2f th=%.2f' % (red, th)
    else:
        cap = _warm_cap(s)
        note = '无冰点基线'
    ec = _emotion_cap(s)
    if ec is not None and cap > ec:
        log.info('[pos-cap] %s emotion 档位收窄 %s -> %.2f（原 %.2f）' % (_sn(sec), s.get('emotion') or '-', ec, cap))
        cap = ec
    log.info('[pos-cap] %s 情绪仓位上限 cap=%.2f (ice=%d warm_days=%d phase=%s emotion=%s %s)'
             % (_sn(sec), cap, int(s.get('ice') or 0), int(s.get('warm_days') or 0),
                s.get('phase') or '-', s.get('emotion') or '-', note))
    return cap

def _buy_pos_ok(context, sec, qty, limit):

    cap = _sentiment_pos_cap(context, sec)
    if cap is None:
        return True
    pos = getattr(getattr(context, 'portfolio', None), 'positions', {}) or {}
    pv = sum(_pos_value(p, sec) for p in pos.values())
    cash = _size_cash(context)
    total = cash + pv
    if total <= 0:
        return True
    add = qty * (limit or last_px(sec) or 0.0)
    ratio = (pv + add) / total
    if ratio > cap:
        log.info('[pos-cap] %s qty=%d add=%.0f pos_ratio=%.2f > cap=%.2f -> skip' % (_sn(sec), qty, add, ratio, cap))
        return False
    return True

def _set_now(context):
    g.now_dt = getattr(getattr(context, 'blotter', None), 'current_dt', None) or None

def _hhmm():
    nd = getattr(g, 'now_dt', None)
    if nd is not None:
        try:
            return nd.strftime('%H:%M')
        except Exception:
            pass
    return time.strftime('%H:%M')

def _hhmmss():

    nd = getattr(g, 'now_dt', None)
    if nd is not None:
        try:
            return nd.strftime('%H:%M:%S')
        except Exception:
            pass
    return time.strftime('%H:%M:%S')

def _min_age():

    hm = _hhmm()
    try:
        h1, m1 = int(hm[:2]), int(hm[3:5])
    except Exception:
        return 0
    return max(0, (h1 * 60 + m1) - (9 * 60 + 30))

def _sec_age():

    nd = getattr(g, 'now_dt', None)
    if nd is not None:
        try:
            secs = (nd.hour * 3600 + nd.minute * 60 + nd.second) - (9 * 3600 + 30 * 60)
            return max(0, secs)
        except Exception:
            pass
    return _min_age() * 60

def dump_scores(context):

    if not BLS.get('debug_score'):
        return
    for sec in _pool() + list(get_positions()):
        try:
            px = last_px(sec); ma5 = _ensure_ma5(sec) or 0.0
            ma5b4 = _ma5_base4(sec) or 0.0
            chg = _auction_change(sec)
            tags = ','.join(_tags(sec)) or '-'
            st = _board_strength(sec)
            sc = score_now(sec)
            if sc is None:
                _skip_log('score_na', sec, 'data_na', 'score %s bar=%s data_na -> skip' % (_sn(sec), _hhmm()))
                continue
            log.info('score %s bar=%s px=%.2f ma5=%.2f ma5b4=%.2f chg=%.1f%% board=%.1f tags=%s score=%.1f' % (
                _sn(sec), _hhmm(), px if px else 0.0, ma5, ma5b4, chg, st, tags, sc))
        except Exception as e:
            _warn('dump_scores fail %s: %r' % (_sn(sec), e))

def _norm_sec(code):

    s = str(code or '').strip()
    if not s:
        return ''
    num = s.split('.')[0]
    if not num:
        return ''
    low = s.lower()
    suf = low.split('.')[-1] if '.' in low else ''
    if suf in ('xshg', 'sh', 'ss'):
        return num + '.XSHG'
    if suf in ('xshe', 'sz'):
        return num + '.XSHE'
    if suf in ('xbj', 'bj'):
        return num + '.XBJ'
    head = num[:1]
    if head in ('6', '9', '5'):
        return num + '.XSHG'
    if head in ('0', '1', '2', '3'):
        return num + '.XSHE'
    if head in ('4', '8'):
        return num + '.XBJ'
    return num

def _is_st(sec):

    sec = str(sec or '')
    if not sec or not BLS.get('skip_st_pool', True):
        return False
    zt = (getattr(g, 'zt_lianban', None) or {}).get(sec)
    if zt is not None:
        try:
            return bool(zt.get('is_st'))
        except Exception:
            pass
    day = str(get_trading_day())
    st_set = getattr(g, 'st_set', None)
    if st_set is None or getattr(g, 'st_day', None) != day:
        st_set = set(); g.st_set = st_set; g.st_day = day
    if sec in st_set:
        return True
    nm = getattr(g, '_name_map', None)
    if nm is None:
        nm = {}; g._name_map = nm
    if sec not in nm:
        try:
            _got = get_stock_name(sec)
            nm[sec] = str(_got or '').strip()
        except Exception:
            nm[sec] = ''
    _name = (nm.get(sec) or '').strip().upper()
    if _name.startswith('*ST') or _name.startswith('ST') or _name.startswith('S*ST') or _name.startswith('SST'):
        st_set.add(sec)
        return True
    return False

def _warm_name_map(secs):

    secs = [s for s in (_norm_sec(c) for c in (secs or [])) if s]
    if not secs:
        return
    nm = getattr(g, '_name_map', None)
    if nm is None:
        nm = {}; g._name_map = nm
    todo = [s for s in secs if s not in nm]
    if not todo:
        return
    try:
        got = get_stock_name(todo) or {}
        if isinstance(got, dict):
            for _c, _v in got.items():
                _cc = _norm_sec(_c)
                if not _cc:
                    continue
                if isinstance(_v, dict):
                    _v = _v.get('stock_name') or ''
                nm[_cc] = str(_v or '').strip()
        elif isinstance(got, (list, tuple)):
            for _row in got:
                try:
                    if isinstance(_row, dict):
                        _cc = _norm_sec(_row.get('code') or _row.get('security') or '')
                        _v = _row.get('stock_name') or _row.get('name') or ''
                    elif len(_row) >= 2:
                        _cc = _norm_sec(_row[0]); _v = _row[1]
                    else:
                        continue
                    if _cc:
                        nm[_cc] = str(_v or '').strip()
                except Exception:
                    continue
    except Exception:
        pass

def _research_roots():

    base = get_research_path()
    return [base, base + 'upload_file/', base + 'data/', base + 'data/upload_file/']

def _selfwatch_paths():
    return [r + 'selfwatch.csv' for r in _research_roots()]

def _load_selfwatch():

    g.selfwatch = []
    for cand in _selfwatch_paths():
        try:
            with open(cand, 'rt', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
            codes = []
            for ln in lines:
                tok = ln.split(',')[0].strip()
                if tok.lower() in ('code', 'security', 'codes'):
                    continue
                codes.append(tok)
            g.selfwatch = [x for x in (_norm_sec(c) for c in codes) if x]
            log.info('[pool] selfwatch loaded %s -> %d' % (cand, len(g.selfwatch)))
            return len(g.selfwatch)
        except Exception:
            continue
    return 0

def _sync_pool_static():

    sw = list(getattr(g, 'selfwatch', []) or [])
    buy_codes = []
    for code, en in (getattr(g, 'exp_file', {}) or {}).items():
        if str(en.get('side') or '') == 'buy':
            buy_codes.append(code)
    buy_codes.sort(key=lambda c: 0 if 'exceed' in str((getattr(g, 'exp_file', {}).get(c) or {}).get('expected_status') or '') else 1)
    pool = list(dict.fromkeys([x for x in (_norm_sec(c) for c in (sw + buy_codes)) if x]))
    if BLS.get('skip_st_pool', True):
        _warm_name_map(pool)
        pool = [x for x in pool if not _is_st(x)]
    g.pool_static = pool
    log.info('[pool] selfwatch=%d expect_buy=%d pool_static=%d' % (len(sw), len(buy_codes), len(pool)))

def _pool():

    out = [x for x in (_norm_sec(s) for s in (list(g.watch or []) + list(g.pool_static or []))) if x]
    if BLS.get('skip_st_pool', True):
        _warm_name_map(out)
        out = [x for x in out if not _is_st(x)]
    out = list(dict.fromkeys(out))
    if out:
        return out
    uni = [x for x in BLS['universe'] if x]
    if BLS.get('skip_st_pool', True):
        _warm_name_map(uni)
        uni = [x for x in uni if not _is_st(x)]
    return uni or BLS['universe']

def _get_snapshot_many(codes, cap):

    try:
        sn = get_snapshot(codes[:cap])
        if isinstance(sn, dict):
            return sn
    except Exception:
        pass
    out = {}
    pc = int(BLS.get('per_stock_cap', 60))
    for c in codes[:pc]:
        try:
            one = get_snapshot(c) or {}
            out.update(one)
        except Exception:
            continue
    return out

def _hot_scan_set():

    hot = set(getattr(g, 'zt_lianban', None) or {})
    for c in (getattr(g, 'selfwatch', None) or []):
        _c = _norm_sec(c)
        if _c:
            hot.add(_c)
    for c in (getattr(g, 'pool_static', None) or []):
        hot.add(c)
    for c in (getattr(g, 'exp_file', None) or {}):
        hot.add(c)
    return hot

def _scan_market():

    day = str(get_trading_day())
    if g.pool_day != day:
        try:
            g.pool_all = [x for x in (_norm_sec(c) for c in (get_Ashares() or [])) if x]
            g.pool_day = day
        except Exception as e:
            _warn('get_Ashares fail: %r' % e)
            g.pool_all = []
    if not g.pool_all:
        return BLS['universe']
    if getattr(g, 'scan_order_day', None) != day or not g.scan_order:
        order = list(g.pool_all)
        if BLS.get('scan_hot_first', True) and _min_age() <= int(BLS.get('first_board_minute', 10)):
            hot = [c for c in order if c in _hot_scan_set()]
            order = hot + [c for c in order if c not in hot]
        g.scan_order = order
        g.scan_order_day = day
    total = len(g.scan_order)
    cap = min(int(BLS['scan_batch']), total)
    offset = g.scan_offset % max(total, 1)
    window = g.scan_order[offset:offset + cap]
    if len(window) < cap and total:
        window = window + (g.scan_order + g.scan_order)[offset + cap:offset + cap + (cap - len(window))]
    g.scan_offset = (offset + cap) % max(total, 1)
    sn = {}
    try:
        sn = _get_snapshot_many(window, cap)
    except Exception:
        sn = {}
    rows = []
    for code, d in sn.items():
        pre = float(d.get('preclose_px') or 0.0); px = float(d.get('last_px') or 0.0)
        if pre <= 0 or px <= 0:
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg < float(BLS['scan_min_chg']):
            continue
        up = float(d.get('up_px') or 0.0)
        near_limit = 1.0 if (up > 0 and px >= up * 0.998) else 0.0
        rows.append({'code': code, 'chg': chg, 'limit': near_limit,
                     'proxy': chg + 20.0 * near_limit})
    if BLS.get('skip_st_pool', True):
        _warm_name_map([r['code'] for r in rows])
        _pre_st = len(rows)
        rows = [r for r in rows if not _is_st(r['code'])]
        _n_st = _pre_st - len(rows)
        if _n_st and time.time() - float(getattr(g, 'st_skip_log_ts', 0.0) or 0.0) >= 300.0:
            g.st_skip_log_ts = time.time()
            log.info('[st-skip] scan rows=%d skip_st=%d' % (_pre_st, _n_st))
    rows.sort(key=lambda r: r['proxy'], reverse=True)
    watch = [x for x in (_norm_sec(r['code']) for r in rows[:int(BLS['max_watch'])]) if x]

    g.scan_round = int(getattr(g, 'scan_round', 0) or 0) + 1
    cur_round = g.scan_round
    keep_rounds = int(BLS.get('scan_near_keep_rounds', 3))
    near_cap = int(BLS.get('scan_near_cap', 20))
    near = getattr(g, 'near_scan', None)
    if near is None:
        near = {}; g.near_scan = near
    ft = getattr(g, 'first_zt', None) or {}
    if BLS.get('skip_st_pool', True):
        _warm_name_map(list(near))
        for code in [x for x in near if _is_st(x)]:
            near.pop(code, None)
    for code in [x for x in near if x in ft]:
        near.pop(code, None)
    for code in [x for x in near if (near[x].get('round') or 0) < cur_round - keep_rounds]:
        near.pop(code, None)
    near_chg = float(BLS.get('scan_near_chg', 7.0))
    for r in rows:
        code = _norm_sec(r['code'])
        if not code or code in ft:
            continue
        if r['chg'] >= near_chg or r['limit']:
            rec = near.get(code)
            near[code] = {'ts': rec.get('ts') if rec else time.time(),
                          'round': cur_round, 'chg': r['chg']}
    if len(near) > near_cap:
        ranked = sorted(near.items(), key=lambda kv: (-(kv[1].get('chg') or 0.0), kv[1].get('ts') or 0.0))
        near = dict(ranked[:near_cap])
        g.near_scan = near
    near_secs = [c for c in near if c not in ft]
    watch = list(dict.fromkeys(watch + near_secs))
    if watch:
        g.watch = watch
    return (watch or BLS['universe'])

def _sync_watch(context):
    try:
        watch = _scan_market()
        if watch:
            g.watch = list(dict.fromkeys(watch))
        log.info('market_scan bar=%s pool=%d watch=%d near=%d off=%d cap=%d' % (
            _hhmm(), len(g.pool_all or []), len(g.watch),
            len(getattr(g, 'near_scan', None) or {}),
            getattr(g, 'scan_offset', 0), int(BLS.get('scan_batch', 300))))
    except Exception as e:
        _warn('market_scan fail: %r' % e)

def _prev_trade_day():

    try:
        d = get_trading_day()
        for _ in range(10):
            d = d - timedelta(days=1)
            if d.weekday() < 5:
                return d
    except Exception:
        pass
    return None

def _expectation_paths():

    day = str(get_trading_day())
    pd_ = _prev_trade_day()
    prev = str(pd_) if pd_ else ''
    suf = BLS.get("expectation_suffix", ".csv")
    latest = [r + "expectation_latest" + suf for r in _research_roots()]
    today = [r + "expectation_" + day + suf for r in _research_roots()]
    prevs = ([r + "expectation_" + prev + suf for r in _research_roots()] if prev and prev != day else [])
    return latest + today + prevs

def _load_expectation(merge=False):

    if not merge:
        g.exp_file = {}
    fp = None
    rows = None
    for cand in _expectation_paths():
        try:
            with open(cand, "rt", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            fp = cand
            break
        except Exception:
            continue
    if fp is None or not rows:
        if not merge:
            log.info("expectation file not found (tried %s)" % _expectation_paths())
        return len(g.exp_file)
    try:
        hdr = [x.strip().lower() for x in rows[0]]

        if merge and g.exp_file:
            _dat = None
            for _dk in ('date', 'trading_date', 'generated_at'):
                if _dk in hdr:
                    _idx = hdr.index(_dk)
                    for r in rows[1:]:
                        if len(r) > _idx and str(r[_idx]).strip():
                            _dat = str(r[_idx]).strip()
                            break
                    break
            if _dat and _dat != str(get_trading_day()):
                log.info("expectation file skip(date=%s != today) %s keep=%d" % (_dat, fp, len(g.exp_file)))
                return len(g.exp_file)
        _old = set(g.exp_file)
        _new = {}
        for r in rows[1:]:
            rec = dict(zip(hdr, r))
            code = (rec.get("code") or "").strip()
            if not code:
                continue
            _ry = (rec.get("yesterday_open_pct") or "").strip()
            _ra = (rec.get("expected_auction_change_pct") or "").strip()
            _new[code] = {
                "side": (rec.get("side") or "hold").strip(),
                "entry_type": (rec.get("entry_type") or "normal").strip(),
                "expected_status": (rec.get("expected_status") or "").strip(),
                "yesterday_open_pct": _fnum(_ry),
                "has_yesterday_open": bool(_ry),
                "expected_auction_change_pct": _fnum(_ra),
                "has_expected_auction": bool(_ra),
                "seal_amount_t0": _fnum(rec.get("seal_amount_t0")),
                "sell_policy_hint": (rec.get("sell_policy_hint") or "").strip(),
                "role_detail": (rec.get("role_detail") or "").strip(),
            }
        if merge:
            g.exp_file.update(_new)
            _keep = len(_old - set(_new))
            log.info("expectation file merged %s old=%d new=%d total=%d keep_old=%d"
                     % (fp, len(_old), len(_new), len(g.exp_file), _keep))
            return len(g.exp_file)
        g.exp_file = _new
        log.info("expectation file loaded %s -> %d" % (fp, len(g.exp_file)))
        return len(g.exp_file)
    except Exception as e:
        log.info("expectation file skip (none/invalid) %s: %r" % (fp, e))
        return len(g.exp_file)

def _fnum(v):
    try:
        return float(str(v).replace(chr(44), "").strip())
    except Exception:
        return 0.0

def _zt_lianban_paths():

    day = str(get_trading_day())
    pd_ = _prev_trade_day()
    prev = str(pd_) if pd_ else ''
    cands = [r + "zt_lianban_latest.csv" for r in _research_roots()]
    for r in _research_roots():
        cands.append(r + "zt_lianban_" + day + ".csv")
    if prev and prev != day:
        for r in _research_roots():
            cands.append(r + "zt_lianban_" + prev + ".csv")
    return cands

def _load_zt_lianban(merge=False):

    if not merge:
        g.zt_lianban = {}
    elif not getattr(g, 'zt_lianban', None):
        g.zt_lianban = {}
    fp = None; rows = None
    for cand in _zt_lianban_paths():
        try:
            with open(cand, "rt", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            fp = cand
            break
        except Exception:
            continue
    if fp is None or not rows:
        return len(g.zt_lianban)
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        has_unq = 'unique_high' in hdr
        has_flw = 'follower_count' in hdr
        has_theme = 'theme' in hdr
        g.zt_unq_authoritative = has_unq
        g.zt_theme_authoritative = has_theme

        if merge and g.zt_lianban:
            _dat = None
            if 'date' in hdr:
                _di = hdr.index('date')
                for r in rows[1:]:
                    if len(r) > _di and str(r[_di]).strip():
                        _dat = str(r[_di]).strip()
                        break
            if _dat:
                _cur = None
                for _rec in g.zt_lianban.values():
                    if (_rec.get('date') or '').strip():
                        _cur = str(_rec['date']).strip()
                        break
                if _cur and _dat != _cur:
                    log.info("[zt-lianban] merge skip(date=%s != %s) %s keep=%d" % (_dat, _cur, fp, len(g.zt_lianban)))
                    return len(g.zt_lianban)
        _new = {}
        themed = 0
        for r in rows[1:]:
            rec = dict(zip(hdr, r))
            code = (rec.get("code") or "").strip()
            if not code:
                continue
            theme = (rec.get("theme") or "").strip()
            themes = (rec.get("themes") or "").strip()
            if theme:
                themed += 1
            _new[code] = {
                "date": (rec.get("date") or "").strip(),
                "board_cnt": int(_fnum(rec.get("board_cnt"))),
                "limit_up_time": (rec.get("limit_up_time") or "").strip(),
                "seal_money": _fnum(rec.get("seal_money")),
                "chg_pct": _fnum(rec.get("chg_pct")),
                "is_st": bool(int(_fnum(rec.get("is_st"))) or 0),
                "reason": (rec.get("reason") or "").strip(),
                "unique_high": bool(int(_fnum(rec.get("unique_high"))) or 0) if has_unq else False,
                "follower_count": int(_fnum(rec.get("follower_count"))) if has_flw else 0,
                "theme": theme,
                "theme_count": int(_fnum(rec.get("theme_count"))) if has_theme else 0,
                "theme_max_board": int(_fnum(rec.get("theme_max_board"))) if has_theme else 0,
                "theme_rank": int(_fnum(rec.get("theme_rank"))) if has_theme else 0,
                "themes": themes,
            }
        if merge and g.zt_lianban:

            if len(_new) * 2 < len(g.zt_lianban):
                log.info("[zt-lianban] merge skip(shrink %d<50%% of %d) %s keep=%d" % (len(_new), len(g.zt_lianban), fp, len(g.zt_lianban)))
                return len(g.zt_lianban)
            _old = set(g.zt_lianban)
            g.zt_lianban.update(_new)
            _keep = len(_old - set(_new))
            n_unq = _annotate_zt_uniqueness()
            _build_zt_theme_index()
            log.info("[zt-lianban] merged %s old=%d new=%d total=%d keep_old=%d unique_high=%d themed=%d"
                     % (fp, len(_old), len(_new), len(g.zt_lianban), _keep, n_unq, themed))
            return len(g.zt_lianban)
        else:
            g.zt_lianban = _new
            n_unq = _annotate_zt_uniqueness()
            _build_zt_theme_index()
            log.info("[zt-lianban] loaded %s -> %d unique_high=%d themed=%d"
                     % (fp, len(g.zt_lianban), n_unq, themed))
            return len(g.zt_lianban)
    except Exception as e:
        log.info("[zt-lianban] skip(invalid) %s: %r" % (fp, e))
        return len(g.zt_lianban)

def _annotate_zt_uniqueness():

    zt = getattr(g, 'zt_lianban', {}) or {}
    if not zt:
        return 0
    if getattr(g, 'zt_unq_authoritative', False):
        return sum(1 for rec in zt.values() if rec.get('unique_high'))

    use_theme = bool(getattr(g, 'zt_theme_authoritative', False))
    groups = {}
    for code, rec in zt.items():
        if use_theme:
            key = str(rec.get('theme') or '').strip()
        else:
            reason = str(rec.get('reason') or '')
            toks = [t.strip() for t in reason.replace('+', ' ').replace('、', ' ').replace(',', ' ').replace('，', ' ').replace('/', ' ').replace('；', ' ').split() if t.strip()]
            key = toks[0] if toks else ''
        if not key:
            key = '__noboard__' + str(code)
        groups.setdefault(key, []).append(code)
    heights = {c: max(1, int((zt[c] or {}).get('board_cnt') or 1)) for c in zt}
    gmax = max(heights.values(), default=1)
    gtop = {c for c, h in heights.items() if h == gmax}
    n_unq = 0
    for codes in groups.values():
        hs = [heights[c] for c in codes]
        mx = max(hs)
        top = [c for c, h in zip(codes, hs) if h == mx]
        for c in codes:
            rec = zt[c]
            is_leader = (len(top) == 1 and top[0] == c and (
                len(codes) >= 2 or (mx == gmax and len(gtop) == 1 and c in gtop)
            ))
            rec['unique_high'] = bool(is_leader)
            rec['follower_count'] = sum(1 for o, oh in zip(codes, hs) if o != c and oh < mx) if is_leader else 0
            if is_leader:
                n_unq += 1
    return n_unq

def _build_zt_theme_index():

    g.zt_theme = {}
    g.zt_themes_of = {}
    zt = getattr(g, 'zt_lianban', {}) or {}
    for code, rec in zt.items():
        names = [t.strip() for t in str(rec.get('themes') or '').split('|') if t.strip()]
        if not names:
            single = str(rec.get('theme') or '').strip()
            if single:
                names = [single]
        g.zt_themes_of[code] = names
        for name in names:
            b = g.zt_theme.setdefault(name, {'members': set(), 'max_board': 0, 'count': 0, 'rank': 0})
            b['members'].add(code)
    for name, b in g.zt_theme.items():
        hs = [int(zt[c].get('board_cnt') or 0) for c in b['members']]
        b['max_board'] = max(hs) if hs else 0
        b['count'] = len(b['members'])
        rk = [int(zt[c].get('theme_rank') or 0) for c in b['members']]
        b['rank'] = max(rk) if rk else 0

def _zt_themes_of(sec):
    return list((getattr(g, 'zt_themes_of', {}) or {}).get(sec) or [])

def _dyn_theme_status():

    if not BLS.get('zt_theme_dyn_enabled', True):
        return {}
    now = time.time()
    cache = getattr(g, 'zt_dyn_cache', None) or {}
    ttl = float(BLS.get('zt_theme_dyn_cache_sec', 15) or 15)
    if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data'):
        return cache['data']
    zt = getattr(g, 'zt_lianban', {}) or {}
    thememap = getattr(g, 'zt_theme', {}) or {}
    out = {}
    for name, b in thememap.items():
        members = sorted(b['members'])
        lvl_of = {}
        for c in members:
            rec = zt.get(c) or {}
            if not rec or not rec.get('board_cnt'):
                continue
            lvl_of[c] = _limitup_days(c)
        alive = [c for c in lvl_of if _today_zt(c)]
        alive_lvls = [lvl_of[c] for c in alive]
        mx = max(alive_lvls) if alive_lvls else 0
        top = [c for c in alive if lvl_of[c] == mx]
        leader = top[0] if len(top) == 1 else ''
        followers = [c for c in alive if c != leader and lvl_of[c] < mx]
        out[name] = {
            'members': members,
            'max_board_static': int(b.get('max_board') or 0),
            'max_board_dyn': mx,
            'count_static': int(b.get('count') or 0),
            'alive_count': len(alive),
            'rank': int(b.get('rank') or 0),
            'leader': leader,
            'follower_count': len(followers),
        }
    if getattr(g, 'zt_dyn_cache', None) is None:
        g.zt_dyn_cache = {}
    g.zt_dyn_cache['ts'] = now
    g.zt_dyn_cache['data'] = out
    return out

def _dyn_theme_leader(sec):

    st = _dyn_theme_status()
    for name in _zt_themes_of(sec):
        d = st.get(name) or {}
        if d.get('leader') == sec:
            return True

    fm = _dyn_theme_ferment()
    for name in _new_themes_of(sec):
        d = fm.get(name) or {}
        if d.get('front') == sec and d.get('confirmed'):
            return True
    return False

def _zt_theme_sort_bonus(code):

    try:
        st = _dyn_theme_status()
        fm = _dyn_theme_ferment()
        best = 0.0
        for name in _zt_themes_of(code):
            d = st.get(name) or {}
            v = 0.0
            if d.get('leader') == code:
                v += float(BLS.get('zt_theme_leader_sort_bonus', 1.5) or 1.5)
            rk = int(d.get('rank') or 0)
            if rk > 0:
                v += float(BLS.get('zt_theme_rank_bonus_step', 0.3) or 0.3) * (6 - min(rk, 6))
            fd = fm.get(name) or {}
            if fd.get('confirmed'):
                if fd.get('front') == code:
                    v += float(BLS.get('zt_theme_ferment_front_bonus', 0.8) or 0.8)
                else:
                    v += float(BLS.get('zt_theme_ferment_sort_bonus', 0.5) or 0.5)
            best = max(best, v)
        for name in _new_themes_of(code):
            if name in _zt_themes_of(code):
                continue
            d = fm.get(name) or {}
            if not d or not d.get('confirmed'):
                continue
            if d.get('front') == code:
                best = max(best, float(BLS.get('zt_theme_ferment_front_bonus', 0.8) or 0.8))
            else:
                best = max(best, float(BLS.get('zt_theme_ferment_sort_bonus', 0.5) or 0.5))
        return best
    except Exception:
        return 0.0

def _new_themes_of(sec):

    sec = str(sec or '')
    if not sec or not BLS.get('zt_theme_ferment_enabled', True):
        return []
    now = time.time()
    cache = getattr(g, 'zt_new_cache', None) or {}
    ttl = float(BLS.get('zt_theme_dyn_cache_sec', 15) or 15)
    if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data') and sec in cache['data']:
        return list(cache['data'].get(sec) or [])
    thememap = getattr(g, 'zt_theme', {}) or {}
    boards = getattr(g, 'boards', None) or {}
    if not (getattr(g, 'stock_boards', None) or {}):

        return []
    out = []
    for nm in _concept_boards_of(sec):
        nm = str(nm or '').strip()
        if not nm:
            continue
        hit = ''
        for tname, tb in thememap.items():
            members = set(tb.get('members') or [])
            if not members:
                continue
            bm = set(boards.get(nm) or [])
            if bm and (members & bm):
                hit = tname
                break
        if hit:
            if hit not in out:
                out.append(hit)
        else:
            t = 'THS:' + nm
            if t not in out:
                out.append(t)
    if getattr(g, 'zt_new_cache', None) is None:
        g.zt_new_cache = {}
    g.zt_new_cache.setdefault('data', {})[sec] = out
    g.zt_new_cache['ts'] = now
    return out

def _merge_temp_themes(by_theme):

    temp_names = sorted([str(n) for n in by_theme if str(n).startswith('THS:')])
    if len(temp_names) <= 1:
        return
    boards = getattr(g, 'boards', None) or {}
    code_sets = {n: {r[2] for r in by_theme[n]} for n in temp_names}
    parent = {n: n for n in temp_names}
    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def _bmap(nm):
        return set(boards.get(str(nm).split(':', 1)[1]) or [])
    for i in range(len(temp_names)):
        for j in range(i + 1, len(temp_names)):
            a, b = temp_names[i], temp_names[j]
            if (code_sets[a] & code_sets[b]) or (_bmap(a) & _bmap(b)):
                parent[_find(a)] = _find(b)
    groups = {}
    for n in temp_names:
        groups.setdefault(_find(n), []).append(n)
    for names in groups.values():
        if len(names) <= 1:
            continue
        merged = []
        for n in names:
            merged.extend(by_theme.pop(n))
        by_code = {}
        for r in merged:
            cur = by_code.get(r[2])
            if cur is None or (r[0], r[1]) > (cur[0], cur[1]):
                by_code[r[2]] = r
        merged = list(by_code.values())
        best = sorted(names, key=lambda n: (-len(code_sets[n]), n))[0]
        by_theme['THS:' + str(best).split(':', 1)[1]] = merged

def _dyn_theme_ferment():

    if not BLS.get('zt_theme_ferment_enabled', True):
        return {}
    now = time.time()
    cache = getattr(g, 'zt_ferment_cache', None) or {}
    ttl = float(BLS.get('zt_theme_dyn_cache_sec', 15) or 15)
    if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data'):
        return cache['data']
    zt = getattr(g, 'zt_lianban', {}) or {}
    base = _dyn_theme_status()
    by_theme = {}
    n_unmapped = 0
    for c, ft in (getattr(g, 'first_zt', None) or {}).items():
        c = str(c or '')
        if not c or not isinstance(ft, dict) or c in zt:
            continue

        if not _today_zt(c):
            continue
        if _is_one_word_open(c):
            continue
        ms = _first_zt_ms(c)
        if not ms:
            continue
        seal = float(ft.get('first_seal') or 0.0)
        names = _new_themes_of(c)
        if not names:
            n_unmapped += 1
            continue
        for name in names:
            by_theme.setdefault(name, []).append((ms, seal, c))
    if n_unmapped != getattr(g, 'zt_unmapped_n', 0):
        g.zt_unmapped_n = n_unmapped
        log.info('[ferment] unmapped=%d' % n_unmapped)
    _merge_temp_themes(by_theme)
    win_ms = int(float(BLS.get('zt_theme_ferment_window_min', 25) or 25)) * 60 * 1000
    assist_min = int(BLS.get('zt_theme_ferment_assist_min', 2) or 2)
    hot_assist = int(BLS.get('zt_theme_ferment_hot_assist', 5) or 5)
    seal_min = float(BLS.get('zt_theme_ferment_seal_min', 50000.0) or 0.0)
    prev = getattr(g, 'zt_ferment_stage', None) or {}
    out = {}
    for name, rows in by_theme.items():
        alive = [r for r in rows if _today_zt(r[2])]
        if not alive:
            continue
        alive.sort(key=lambda r: (r[0], -(r[1])))
        bd = base.get(name) or {}
        leader = bd.get('leader') or ''
        max_dyn = int(bd.get('max_board_dyn') or 0)
        assist = len(alive)
        span_ms = max(r[0] for r in alive) - min(r[0] for r in alive)
        confirmed = assist >= assist_min and (len(alive) < 2 or span_ms <= win_ms)
        stage = 'hot' if (confirmed and assist >= hot_assist) else ('confirmed' if confirmed else 'watch')
        front = leader
        front_ms = 0
        seal_ok = True
        if not front or not _today_zt(front):

            candidates = [r for r in alive if not _is_one_word_open(r[2])]
            if candidates:

                pool = candidates
                if seal_min > 0:
                    strong = [r for r in candidates if r[1] <= 0 or r[1] >= seal_min]
                    if strong:
                        pool = strong
                    else:
                        seal_ok = False
                pool.sort(key=lambda r: (r[0], -(r[1])))
                front = pool[0][2]
                front_ms = pool[0][0]
                if not leader and not max_dyn:
                    max_dyn = 1
        out[name] = {
            'members': [r[2] for r in alive],
            'assist_count': assist,
            'confirmed': bool(confirmed),
            'stage': stage,
            'front': front,
            'front_first_ms': front_ms,
            'max_board_dyn': max(1, max_dyn),
            'temp': bool(name.startswith('THS:')),
            'span_ms': span_ms,
            'seal_min': seal_min,
            'seal_ok': bool(seal_ok),
        }
        if prev.get(name) != stage:
            log.info('[ferment] %s assist=%d stage=%s front=%s span=%dms' % (
                name, assist, stage, front, span_ms))
        prev[name] = stage
    if getattr(g, 'zt_ferment_stage', None) is None:
        g.zt_ferment_stage = {}
    g.zt_ferment_stage.update({k: v for k, v in prev.items() if k in out})
    if getattr(g, 'zt_ferment_cache', None) is None:
        g.zt_ferment_cache = {}
    g.zt_ferment_cache['ts'] = now
    g.zt_ferment_cache['data'] = out
    return out

def _ferment_front_gate(sec):

    try:
        if sec in (getattr(g, 'zt_lianban', {}) or {}):
            return None
        fm = _dyn_theme_ferment()
        themes = _new_themes_of(sec)
        if not themes:
            return None
        known = False
        base = None
        for name in themes:
            d = fm.get(name) or {}
            if not d:

                if name.startswith('THS:'):
                    return True
                if base is None:
                    base = _dyn_theme_status()
                leader = (base.get(name) or {}).get('leader') or ''
                if leader and _today_zt(leader):
                    return False
                continue
            known = True
            if d.get('front') == sec:
                return True
        return False if known else None
    except Exception:
        return None

def _lb_senti_state():

    try:
        day = str(get_trading_day())
    except Exception:
        day = ''
    st = getattr(g, 'lb_senti', None)
    if not isinstance(st, dict):
        st = {}
    if st.get('day') != day:
        st = {'day': day, 'auction': {}, 'mid': {}, 't100': {}, 'cut_seen': {}, 'gate_seen': {}}
        g.lb_senti = st
    st.setdefault('auction', {})
    st.setdefault('mid', {})
    st.setdefault('t100', {})
    st.setdefault('cut_seen', {})
    st.setdefault('gate_seen', {})
    return st

def _lb_senti_tier(sec):

    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        bc = int(zt.get('board_cnt') or 0)
    except Exception:
        bc = 0
    if not zt or bc <= 1:
        return 'low'
    if bc > int(BLS.get('lb_senti_high_max', 5)) or bool(zt.get('unique_high')):
        return 'high'
    return 'mid'

def _lb_senti_t100_passed():

    return _hhmm() >= '10:00'

def _fill_zt_spot():

    zt = getattr(g, 'zt_lianban', {}) or {}

    def _incomplete(sec):
        s2 = g.spot.get(sec) or {}
        return not (float(s2.get('open_px') or 0.0) > 0 and float(s2.get('preclose_px') or 0.0) > 0)

    _need = [sec for sec in zt if _incomplete(sec)]
    if not _need:
        return 0
    try:
        _sn = _get_snapshot_many(_need, len(_need)) or {}
        _got = 0
        for _cc, _dd in _sn.items():
            if not _dd:
                continue
            _old = g.spot.get(_cc) or {}
            if _old:
                _old = dict(_old)
                for _k, _v in _dd.items():
                    if _old.get(_k) in (None, 0, '', 0.0):
                        _old[_k] = _v
                g.spot[_cc] = _old
            else:
                g.spot[_cc] = dict(_dd)
            if not _incomplete(_cc):
                _got += 1
        if _got:
            log.info('[lb-senti] auction 全池补快照 got=%d/%d' % (_got, len(_need)))
        return _got
    except Exception:
        return 0

def _lb_senti_auction():

    st = _lb_senti_state()
    zt = getattr(g, 'zt_lianban', {}) or {}
    if not zt:
        st['auction'] = {'ts': time.time(), 'note': 'no_zt_lianban'}
        return st['auction']
    day = str(get_trading_day())

    def _stats():
        mid_n = high_n = low_n = mid_open = mid_green = mid_yizi = low_open = low_yizi = 0
        mid_ready = low_ready = 0
        for sec in zt:
            tier = _lb_senti_tier(sec)
            rdy = _auction_ready(sec)
            c = g.auction_c.get(sec)
            chg = 0.0
            if c and c[0] == day:
                chg = float(c[1] or 0.0)
            else:
                s = g.spot.get(sec) or {}
                pre = float(s.get('preclose_px') or 0.0)
                op = float(s.get('open_px') or 0.0)
                chg = (op / pre - 1.0) * 100.0 if pre > 0 and op > 0 else 0.0
            yizi = _is_one_word_open(sec)
            if tier == 'mid':
                mid_n += 1
                if rdy:
                    mid_ready += 1
                if chg > 0:
                    mid_open += 1
                if chg < 0:
                    mid_green += 1
                if yizi:
                    mid_yizi += 1
            elif tier == 'high':
                high_n += 1
            else:
                low_n += 1
                if rdy:
                    low_ready += 1
                if chg > 0:
                    low_open += 1
                if yizi:
                    low_yizi += 1
        ready_min = float(BLS.get('lb_senti_auction_ready_min', 0.6))
        ready = ((mid_ready >= ready_min * mid_n) if mid_n else True) and ((low_ready >= ready_min * low_n) if low_n else True)
        return {
            'mid_n': mid_n, 'high_n': high_n, 'low_n': low_n,
            'mid_open_rate': (float(mid_open) / mid_n) if mid_n else 0.0,
            'mid_green_rate': (float(mid_green) / mid_n) if mid_n else 0.0,
            'mid_yizi': mid_yizi,
            'mid_yizi_rate': (float(mid_yizi) / mid_n) if mid_n else 0.0,
            'low_open_rate': (float(low_open) / low_n) if low_n else 0.0,
            'low_yizi': low_yizi,
            'ready': ready,
            'ready_detail': {'mid': mid_ready, 'low': low_ready},
        }, ready, mid_n, high_n, low_n

    _fill_zt_spot()
    out, ready, mid_n, high_n, low_n = _stats()
    if not ready:
        _got = _fill_zt_spot()
        if _got:
            out, ready, mid_n, high_n, low_n = _stats()
    if not ready:
        _ready_n = out['ready_detail']['mid'] + out['ready_detail']['low']
        out = {
            'ts': time.time(),
            'ready': False,
            'ready_detail': out['ready_detail'],
            'mid_n': mid_n, 'high_n': high_n, 'low_n': low_n,
            'mid_open_rate': None, 'mid_green_rate': None,
            'mid_yizi': out.get('mid_yizi', 0), 'mid_yizi_rate': None,
            'low_open_rate': None, 'low_yizi': out.get('low_yizi', 0),
            'note': 'auction_data_not_ready ready=%.0f%%' % (100.0 * _ready_n / (mid_n + low_n) if (mid_n + low_n) else 100.0),
        }
        st['auction'] = out
        log.info('[lb-senti] auction not_ready mid=%d/%d low=%d/%d -> 不写 open/green/yizi 率'
                 % (out['ready_detail']['mid'], mid_n, out['ready_detail']['low'], low_n))
        return out
    out['ts'] = time.time()
    out['ready'] = True
    st['auction'] = out
    log.info('[lb-senti] auction mid=%d open=%.1f%% green=%.1f%% yizi=%d low=%d open=%.1f%% ready_detail=mid:%d/%d low:%d/%d'
             % (mid_n, out['mid_open_rate'] * 100.0, out['mid_green_rate'] * 100.0,
                out['mid_yizi'], low_n, out['low_open_rate'] * 100.0,
                out['ready_detail']['mid'], mid_n, out['ready_detail']['low'], low_n))
    return out

def _lb_senti_set_phase(st, cand, note, now, force_confirm=False):

    prev = st['mid'].get('phase') or 'watch'
    rank = {'high_continue': 0, 'watch': 1, 'high_diverg': 2, 'rotate_low': 2, 'ice_wait': 3}
    if cand == prev or rank.get(cand, 1) <= rank.get(prev, 1):
        if prev != cand:
            log.info('[lb-senti] phase %s -> %s (%s)' % (prev, cand, note or ''))
        st['mid']['phase'] = cand
        st['mid']['phase_at'] = _hhmm()
        st.pop('risk_pending', None)
        return
    if force_confirm:
        log.info('[lb-senti] phase %s -> %s (%s, force 10:00)' % (prev, cand, note or ''))
        st['mid']['phase'] = cand
        st['mid']['phase_at'] = _hhmm()
        st.pop('risk_pending', None)
        return
    pend = st.get('risk_pending') or {}
    hyst = float(BLS.get('lb_senti_hysteresis_sec_before', 30.0)) if not _lb_senti_t100_passed() else float(BLS.get('lb_senti_hysteresis_sec', 60.0))
    if pend.get('phase') == cand and now - float(pend.get('ts') or 0) < hyst:
        log.info('[lb-senti] phase %s -> %s (%s, 确认)' % (prev, cand, note or ''))
        st['mid']['phase'] = cand
        st['mid']['phase_at'] = _hhmm()
        st.pop('risk_pending', None)
    else:
        st['risk_pending'] = {'phase': cand, 'ts': now}

def _lb_senti_mid(force=False, force_confirm=False):

    if not BLS.get('lb_senti_enabled', True):
        return {}
    now = time.time()
    st = _lb_senti_state()
    if not force:
        cache = getattr(g, 'lb_senti_cache', None) or {}
        ttl = float(BLS.get('lb_senti_cache_sec_after', 60.0) if _lb_senti_t100_passed() else BLS.get('lb_senti_cache_sec', 15.0))
        if cache and now - float(cache.get('ts') or 0) < ttl and cache.get('data'):
            return cache['data']
    zt = getattr(g, 'zt_lianban', {}) or {}
    mid_pool = [c for c in zt if _lb_senti_tier(c) == 'mid']
    ft = getattr(g, 'first_zt', None) or {}
    touched = [c for c in mid_pool if c in ft]
    alive = [c for c in touched if _today_zt(c)]
    break_n = sum(1 for c in touched if bool(ft.get(c, {}).get('break')))
    sealed_alive = sum(1 for c in alive if not bool(ft.get(c, {}).get('break')))
    ferm = _dyn_theme_ferment()
    new_min = int(BLS.get('lb_senti_new_dir_min', 2))
    new_dir = sum(1 for d in ferm.values() if d.get('temp') and d.get('confirmed')
                  and int(d.get('assist_count') or 0) >= new_min)
    low_assist = sum(int(d.get('assist_count') or 0) for d in ferm.values() if d.get('confirmed'))
    try:
        red = _market_red_ratio()
    except Exception:
        red = None
    promo = (float(len(alive)) / len(touched)) if touched else 0.0
    break_rate = (float(break_n) / len(touched)) if touched else 0.0
    out = {
        'ts': now,
        'hhmm': _hhmm(),
        'mid_pool': len(mid_pool),
        'touch_n': len(touched),
        'alive_n': len(alive),
        'promo': promo,
        'break_n': break_n,
        'break_rate': break_rate,
        'seal_retain': (float(sealed_alive) / len(alive)) if alive else 0.0,
        'low_assist': low_assist,
        'new_dir_n': new_dir,
        'red': red,
        'phase': 'watch',
        'note': '',
    }
    if not mid_pool:
        _lb_senti_set_phase(st, 'watch', 'no_mid_pool', now)
        out['note'] = 'no_mid_pool'
    else:
        if _lb_senti_t100_passed():
            min_touch = max(1, int(len(mid_pool) * float(BLS.get('lb_senti_min_touch_ratio', 0.5))))
        else:
            _ratio = float(BLS.get('lb_senti_min_touch_ratio_before', 0.3))
            _floor = int(BLS.get('lb_senti_min_touch_floor', 3))
            _est = max(1, int(len(mid_pool) * _ratio))
            min_touch = max(_est, _floor) if len(mid_pool) >= _floor else _est
        if len(touched) < min_touch:
            _lb_senti_set_phase(st, 'watch', 'sample_insufficient', now)
            out['note'] = 'sample_insufficient touched=%d/%d' % (len(touched), len(mid_pool))
        else:
            promo_min = float(BLS.get('lb_senti_promo_min', 0.60))
            break_max = float(BLS.get('lb_senti_break_max', 0.20))
            red_cold = float(BLS.get('lb_senti_red_cold', 0.40))
            risk_ok = promo >= promo_min and break_rate <= break_max
            low_ok = low_assist >= new_min or new_dir >= new_min
            if risk_ok:
                if red is not None and red < red_cold and not low_ok:
                    _lb_senti_set_phase(st, 'ice_wait', 'red_cold_weak_low', now, force_confirm)
                    out['note'] = 'red_cold_weak_low'
                else:
                    _lb_senti_set_phase(st, 'high_continue', 'promo_ok', now, force_confirm)
                    out['note'] = 'promo_ok'
            else:
                rot_ok = promo < float(BLS.get('lb_senti_rotation_promo', 0.40)) or break_rate > float(BLS.get('lb_senti_rotation_break', 0.30))
                if low_ok and rot_ok:
                    _lb_senti_set_phase(st, 'rotate_low', 'high_break_low_rotate', now, force_confirm)
                    out['note'] = 'high_break_low_rotate'
                elif low_ok:
                    _lb_senti_set_phase(st, 'high_diverg', 'low_ok_but_break_mild', now, force_confirm)
                    out['note'] = 'low_ok_but_break_mild'
                elif red is not None and red < red_cold:
                    _lb_senti_set_phase(st, 'ice_wait', 'red_cold', now, force_confirm)
                    out['note'] = 'red_cold'
                else:
                    _lb_senti_set_phase(st, 'high_diverg', 'high_break', now, force_confirm)
                    out['note'] = 'high_break'
    out['phase'] = st['mid'].get('phase') or 'watch'
    st['mid'].update(out)
    g.lb_senti_cache = {'ts': now, 'data': out}
    if out['phase'] != st.get('last_log_phase'):
        st['last_log_phase'] = out['phase']
        log.info('[lb-senti] %s phase=%s promo=%.0f%%(alive=%d/%d) break=%.1f%%(n=%d) red=%s low_assist=%d new_dir=%d'
                 % (out['hhmm'], out['phase'], promo * 100.0, len(alive), len(touched),
                    break_rate * 100.0, break_n,
                    ('%.2f' % red) if red is not None else '-', low_assist, new_dir))
    return out

def _lb_senti_phase():

    try:
        if BLS.get('lb_senti_enabled', True):
            d = _lb_senti_mid()
            if d:
                return d
        st = _lb_senti_state()
        return st.get('mid') or {'phase': 'watch'}
    except Exception as e:
        _warn('lb_senti_phase fail %r' % e)
        return {'phase': 'watch'}

def lb_senti_t100_freeze(context):

    if not BLS.get('lb_senti_enabled', True):
        return
    _set_now(context)
    st = _lb_senti_state()
    try:
        d = _lb_senti_mid(force=True, force_confirm=True) or {}
    except Exception as e:
        _warn('lb_senti t100 freeze fail %r' % e)
        d = st.get('mid') or {}
    st['t100'] = {
        'ts': time.time(),
        'hhmm': _hhmm(),
        'phase': st['mid'].get('phase') or 'watch',
        'auction': dict(st.get('auction') or {}),
        'mid': dict(d),
    }
    dir_n = {'attack_high': 0, 'attack_low': 0, 'neutral': 0, 'avoid': 0}
    for _c, _en in (getattr(g, 'exp_file', {}) or {}).items():
        if str((_en or {}).get('side') or '') != 'buy':
            continue
        _k = str(_exp_direction_eval(_c).get('kind') or 'neutral')
        dir_n[_k if _k in dir_n else 'neutral'] += 1
    st['t100']['direction'] = dict(dir_n)
    log.info('[lb-senti] t100 freeze phase=%s promo=%.1f%% break=%.1f%% red=%s low=%d new_dir=%d dir_high=%d dir_low=%d dir_avoid=%d'
             % (st['t100']['phase'], float(d.get('promo') or 0.0) * 100.0,
                float(d.get('break_rate') or 0.0) * 100.0,
                ('%.2f' % d['red']) if d.get('red') is not None else '-',
                int(d.get('low_assist') or 0), int(d.get('new_dir_n') or 0),
                dir_n['attack_high'], dir_n['attack_low'], dir_n['avoid']))
    _save_state()

def _lb_senti_direction_bonus(sec):

    try:
        return float(_exp_direction_eval(sec).get('score') or 0.0)
    except Exception:
        return 0.0

def _lb_senti_participate_scale():

    try:
        if not _lb_senti_t100_passed():
            return 1.0
        scale = float(BLS.get('lb_senti_participate_scale', 0.5))
        if _lb_senti_phase().get('phase') == 'ice_wait':
            scale *= 0.5
        return scale
    except Exception:
        return 1.0

def _unq_height_space(sec):

    try:
        st = getattr(g, 'sentiment', None) or {}
        suppress = int(st.get('height_suppress') or 0)
        if suppress <= 0:
            return 1.0
        cnt = _limitup_days(sec)
        if cnt <= 0:
            return 1.0
        return (suppress - cnt) / suppress
    except Exception:
        return 1.0

def _is_unique_lianban(sec):

    try:
        zt = ((getattr(g, 'zt_lianban', {}) or {}).get(sec) or {})
        if zt.get('unique_high'):
            return True
        if _unique_stand(sec):
            return True
        if _exp_original_theme_leader(sec):
            return True
    except Exception:
        pass
    return False

def _lb_senti_buy_gate(sec):

    try:
        ph = _lb_senti_phase().get('phase') or 'watch'
        if ph in ('high_diverg', 'rotate_low', 'ice_wait'):
            if _lb_senti_tier(sec) == 'low':
                return (True, 'low_ok(%s)' % ph)
            if (ph == 'rotate_low' and BLS.get('exp_direction_rotate_leader_exception', True)
                    and _exp_original_theme_leader(sec)):
                return (True, 'origin_unique_leader_ok(rotate_low)')
            return (False, 'mid_high_skip(%s)' % ph)

        if BLS.get('unq_space_gate_enabled', True) and _lb_senti_tier(sec) != 'low':
            if _is_unique_lianban(sec):
                sp = _unq_height_space(sec)
                if sp < float(BLS.get('unq_space_min', 0.15)):
                    sup = ((getattr(g, 'sentiment', None) or {}).get('height_suppress') or 0)
                    return (False, 'unq_space_skip(space=%.1f%%,suppress=%d)' % (sp * 100.0, sup))
        return (True, 'normal(%s)' % ph)
    except Exception:
        return (True, 'normal')

def _exp_original_theme_leader(sec):

    try:
        if _lb_senti_tier(sec) == 'low':
            return ''
        if not ((getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}):
            return ''
        dyn = _dyn_theme_status()
        for name in _zt_themes_of(sec):
            d = dyn.get(name) or {}
            if d.get('leader') == sec and int(d.get('max_board_dyn') or 0) >= 2:
                return name
    except Exception:
        pass
    return ''

def _exp_direction_eval(sec):

    out = {
        'kind': 'neutral', 'score': 0.0, 'hard_skip': False, 'size_mult': 1.0,
        'theme': '', 'role': 'outside', 'stage': 'watch', 'phase': 'watch', 'reason': '',
    }
    if not BLS.get('exp_direction_enabled', True):
        out['reason'] = 'disabled'
        return out
    try:
        ph = _lb_senti_phase().get('phase') or 'watch'
        tier = _lb_senti_tier(sec)
        zt_rec = ((getattr(g, 'zt_lianban', {}) or {}).get(sec) or {})
        static_leader = bool(zt_rec.get('unique_high'))
        old_themes = _zt_themes_of(sec)
        new_themes = _new_themes_of(sec)
        dyn = _dyn_theme_status()
        fm = _dyn_theme_ferment()
        hot_rear = ''
        old_leader = ''
        old_front = ''
        old_front_stage = ''
        new_front = ''
        new_front_stage = ''

        for name in old_themes:
            d = dyn.get(name) or {}
            f = fm.get(name) or {}
            if (d.get('leader') == sec or static_leader) and tier in ('mid', 'high'):
                old_leader = old_leader or name
            if f.get('confirmed') and f.get('front') == sec:
                old_front = old_front or name
                old_front_stage = str(f.get('stage') or 'confirmed')
            elif (BLS.get('exp_direction_hot_front_only', True)
                  and f.get('confirmed') and f.get('stage') == 'hot'):
                hot_rear = hot_rear or name

        for name in new_themes:
            if name in old_themes:
                continue
            f = fm.get(name) or {}
            if f.get('confirmed') and f.get('front') == sec:
                new_front = new_front or name
                new_front_stage = str(f.get('stage') or 'confirmed')
            elif (BLS.get('exp_direction_hot_front_only', True)
                  and f.get('confirmed') and f.get('stage') == 'hot'):
                hot_rear = hot_rear or name

        out['phase'] = ph
        bonus = float(BLS.get('exp_direction_attack_bonus', 0.8) or 0.0)

        leader_ok = (ph == 'high_continue'
                     or (ph == 'rotate_low' and BLS.get('exp_direction_rotate_leader_exception', True))
                     or ph == 'watch')
        front_ok = (ph not in ('high_diverg', 'ice_wait') or tier == 'low')
        if old_leader and leader_ok:
            _reason = ('origin_leader_watch_preconfirm' if ph == 'watch'
                       else 'origin_leader_rotate_exception' if ph == 'rotate_low'
                       else 'origin_leader_high_continue')
            out.update(kind='attack_high', score=bonus, theme=old_leader, role='leader',
                       stage=(fm.get(old_leader) or {}).get('stage') or 'watch',
                       reason=_reason)
        elif new_front and front_ok:
            _reason = 'new_theme_front_watch' if ph == 'watch' else 'new_theme_front'
            out.update(kind='attack_low', score=bonus, theme=new_front, role='front',
                       stage=new_front_stage, reason=_reason)
        elif old_front and front_ok:
            _kind = 'attack_low' if tier == 'low' else 'attack_high'
            _reason = 'theme_ferment_front_watch' if ph == 'watch' else 'theme_ferment_front'
            out.update(kind=_kind, score=bonus, theme=old_front, role='front',
                       stage=old_front_stage, reason=_reason)
        elif hot_rear and BLS.get('exp_direction_hot_front_only', True):
            out.update(kind='avoid', theme=hot_rear, role='rear', stage='hot',
                       reason='hot_rear')
        elif ph in ('rotate_low', 'high_diverg', 'ice_wait') and tier in ('mid', 'high'):
            out.update(kind='avoid', role='follower', reason='mid_high_%s' % ph)
        elif tier in ('mid', 'high'):
            out['role'] = 'follower'

        out['hard_skip'] = bool(out['kind'] == 'avoid'
                                and BLS.get('exp_direction_avoid_hard_skip', True))
        if out['kind'] == 'avoid':
            out['score'] = 0.0
        return out
    except Exception as e:
        out['reason'] = 'fallback:%r' % e
        return out

def _exp_direction_log(sec, ctx, action):

    if not BLS.get('exp_direction_log', True):
        return
    try:
        st = _lb_senti_state()
        key = 'expdir:%s:%s:%s:%s' % (sec, ctx.get('kind'), ctx.get('reason'), action)
        if key in st.setdefault('gate_seen', {}):
            return
        st['gate_seen'][key] = time.time()
        en = ((getattr(g, 'exp_file', {}) or {}).get(sec) or {})
        src = str(en.get('_src') or 'provider')
        log.info('[exp-dir] %s source=%s phase=%s kind=%s score=%.1f size_mult=1.0 role=%s stage=%s theme=%s action=%s reason=%s'
                 % (_sn(sec), src, ctx.get('phase') or '-', ctx.get('kind') or 'neutral',
                    float(ctx.get('score') or 0.0), ctx.get('role') or '-', ctx.get('stage') or '-',
                    ctx.get('theme') or '-', action, ctx.get('reason') or '-'))
    except Exception:
        pass

def _lb_senti_gate_apply(sec, action):

    try:
        if not BLS.get('lb_senti_gate_all_buys_enabled', True):
            return True
        allow, note = _lb_senti_buy_gate(sec)
        if not allow:
            _lb_gate_seen(sec, note, action)
            return False
        st = _lb_senti_state()
        key = 'allow:%s:%s' % (action, sec)
        if key not in st.setdefault('gate_seen', {}):
            st['gate_seen'][key] = time.time()
            log.info('[lb-senti] %s %s allow (%s)' % (_sn(sec), action, note))
        return True
    except Exception:
        return True

def _lb_gate_seen(sec, note, action='expected_buy'):

    try:
        st = _lb_senti_state()
        key = '%s:%s:%s' % (sec, action, note)
        if key in st.setdefault('gate_seen', {}):
            return
        st['gate_seen'][key] = time.time()
        log.info('[lb-senti] %s %s -> skip %s' % (_sn(sec), note, action))
    except Exception:
        pass

def _lb_senti_cut_hold(sec):

    try:
        if not BLS.get('lb_senti_cut_enabled', True):
            return None
        ph = _lb_senti_phase().get('phase') or 'watch'
        if ph not in ('high_diverg', 'rotate_low'):
            return None
        if _lb_senti_tier(sec) != 'mid':
            return None
        if _today_zt(sec):
            return None
        st = _lb_senti_state()
        if sec in st.setdefault('cut_seen', {}):
            return None
        frac = float(BLS.get('lb_senti_cut_half_ratio', 0.5))
        return (frac, 'P8_lb_senti_cut_half phase=%s' % ph)
    except Exception:
        return None

def _mark_lb_cut(sec):

    try:
        st = _lb_senti_state()
        st.setdefault('cut_seen', {})[sec] = time.time()
        _save_state()
    except Exception:
        pass

def _sentiment_paths():

    day = str(get_trading_day())
    pd_ = _prev_trade_day()
    prev = str(pd_) if pd_ else ''
    cands = [r + "sentiment_latest.csv" for r in _research_roots()]
    if prev and prev != day:
        for r in _research_roots():
            cands.append(r + "sentiment_" + prev + ".csv")
    return cands

def _board_file_paths():

    return [r + "boards_latest.csv" for r in _research_roots()]

def _load_boards():

    g.boards = {}
    g.stock_boards = {}
    g.board_type = {}
    for cand in _board_file_paths():
        try:
            with open(cand, 'rt', encoding='utf-8') as f:
                rows = list(csv.reader(f))
        except Exception:
            continue
        if len(rows) < 2:
            continue
        hdr = [x.strip().lower() for x in rows[0]]
        try:
            ni, nt, nc = hdr.index('board_name'), hdr.index('board_type'), hdr.index('member_code')
        except ValueError:
            continue
        for r in rows[1:]:
            if len(r) <= max(ni, nt, nc):
                continue
            nm = r[ni].strip(); typ = r[nt].strip(); code = (r[nc] or '').strip()
            if not nm or not code:
                continue
            g.boards.setdefault(nm, []).append(code)
            g.board_type[nm] = typ
            g.stock_boards.setdefault(code, []).append(nm)
        for nm in g.boards:
            g.boards[nm] = list(dict.fromkeys(g.boards[nm]))
        for code in g.stock_boards:
            g.stock_boards[code] = list(dict.fromkeys(g.stock_boards[code]))
        log.info('[boards] loaded %s -> boards=%d stocks=%d unified=%s' % (
            cand, len(g.boards), len(g.stock_boards), bool(BLS.get('board_concept_unified', True))))
        return len(g.boards)
    return 0

def _load_sentiment():

    g.sentiment = None
    fp = None; rows = None
    for cand in _sentiment_paths():
        try:
            with open(cand, "rt", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            fp = cand
            break
        except Exception:
            continue
    if fp is None or not rows:
        log.info("[sentiment] file not found (tried %s)" % _sentiment_paths())
        return None
    try:
        hdr = [x.strip().lower() for x in rows[0]]
        rec = dict(zip(hdr, rows[1][:len(hdr)])) if len(rows) > 1 else {}
        g.sentiment = {
            "date": (rec.get("date") or "").strip(),
            "limit_up": int(_fnum(rec.get("limit_up"))),
            "break_count": int(_fnum(rec.get("break_count"))),
            "seal_rate": _fnum(rec.get("seal_rate")),
            "advance_rate": _fnum(rec.get("advance_rate")),
            "max_board": int(_fnum(rec.get("max_board"))),
            "lianban_count": int(_fnum(rec.get("lianban_count"))),
            "ice": bool(int(_fnum(rec.get("ice"))) or 0),
            "ice_streak": int(_fnum(rec.get("ice_streak"))),
            "warm_days": int(_fnum(rec.get("warm_days"))),
            "phase": (rec.get("phase") or "").strip(),
            "divergence": bool(int(_fnum(rec.get("divergence"))) or 0),
            "emotion": (rec.get("emotion") or "").strip(),
            "emotion_basis": (rec.get("emotion_basis") or "").strip(),

            "max_board_10d": int(_fnum(rec.get("max_board_10d"))),
            "max_board_10d_path": (rec.get("max_board_10d_path") or "").strip(),
            "height_suppress": int(_fnum(rec.get("height_suppress"))),
        }
        log.info("[sentiment] loaded %s -> ice=%s streak=%d adv=%.1f%% seal=%.0f%% emotion=%s (date=%s)" % (
            fp, g.sentiment["ice"], g.sentiment["ice_streak"], g.sentiment["advance_rate"],
            g.sentiment["seal_rate"] * 100.0, g.sentiment["emotion"] or "-", g.sentiment["date"]))
        return g.sentiment
    except Exception as e:
        log.info("[sentiment] skip(invalid) %s: %r" % (fp, e))
        return None

def _synth_pool_expect():

    if not BLS.get('pool_expect_enabled', True) or not g.zt_lianban:
        return 0
    codes = [c for c in g.zt_lianban if c not in g.exp_file]
    n_st = 0
    if BLS.get('pool_expect_skip_st', True):

        n_st = sum(1 for c in codes if (g.zt_lianban[c] or {}).get('is_st'))
        codes = [c for c in codes if not (g.zt_lianban[c] or {}).get('is_st')]

    n_mid = sum(1 for c in codes if _mid_board_avoid(c))
    codes = [c for c in codes if not _mid_board_avoid(c)]
    if not codes:
        log.info('[exp] 涨停池竞价三态合成 -> exceed=0 meet=0 miss=0 st_skip=%d mid_skip=%d (全过滤)' % (n_st, n_mid))
        return 0
    day = str(get_trading_day())
    try:
        sn = _get_snapshot_many(codes, 400)
        for c, d in sn.items():
            if d and c not in g.spot:
                g.spot[c] = d
    except Exception:
        sn = {}
    n_ex = n_mt = n_ms = 0
    for code in codes:
        try:
            s = g.spot.get(code) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            chg = (op / pre - 1.0) * 100.0 if (pre > 0 and op > 0) else None
            if chg is None:
                chg = _auction_change(code)
            else:
                g.auction_c[code] = (day, chg)
            chg = round(float(chg or 0.0), 2)
            yopen, has = _yesterday_open_chg(code)
            if chg < 0:
                st = 'pending_miss'; n_ms += 1
            elif has and chg > yopen:
                st = 'pending_exceed'; n_ex += 1
            else:
                st = 'pending_meet'; n_mt += 1
            g.exp_file[code] = {
                'side': 'buy', 'entry_type': 'normal', 'expected_status': st,
                'yesterday_open_pct': yopen, 'has_yesterday_open': has,
                'expected_auction_change_pct': yopen if has else 0.0,
                'has_expected_auction': has, 'seal_amount_t0': 0.0, 'sell_policy_hint': '',
                '_src': 'zt_pool',
            }
        except Exception:
            continue
    log.info('[exp] 涨停池竞价三态合成 -> exceed=%d meet=%d miss=%d st_skip=%d mid_skip=%d' % (n_ex, n_mt, n_ms, n_st, n_mid))
    return n_ex + n_mt + n_ms

def _synth_selfwatch_expect():

    if not BLS.get('pool_expect_enabled', True):
        return 0
    sw = [c for c in (getattr(g, 'selfwatch', []) or []) if c not in g.exp_file]
    n_mid = sum(1 for c in sw if _mid_board_avoid(c))
    sw = [c for c in sw if not _mid_board_avoid(c)]
    if not sw:
        log.info('[exp] 自选股竞价三态合成 -> exceed=0 meet=0 miss=0 mid_skip=%d' % n_mid)
        return 0
    day = str(get_trading_day())
    try:
        sn = _get_snapshot_many(sw, 200)
        for c, d in sn.items():
            if d and c not in g.spot:
                g.spot[c] = d
    except Exception:
        sn = {}
    n_ex = n_mt = n_ms = 0
    for code in sw:
        try:
            s = g.spot.get(code) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            chg = (op / pre - 1.0) * 100.0 if (pre > 0 and op > 0) else None
            if chg is None:
                chg = _auction_change(code)
            else:
                g.auction_c[code] = (day, chg)
            chg = round(float(chg or 0.0), 2)
            yopen, has = _yesterday_open_chg(code)
            if chg < 0:
                st = 'pending_miss'; n_ms += 1
            elif has and chg > yopen:
                st = 'pending_exceed'; n_ex += 1
            else:
                st = 'pending_meet'; n_mt += 1
            g.exp_file[code] = {
                'side': 'buy', 'entry_type': 'normal', 'expected_status': st,
                'yesterday_open_pct': yopen, 'has_yesterday_open': has,
                'expected_auction_change_pct': yopen if has else 0.0,
                'has_expected_auction': has, 'seal_amount_t0': 0.0, 'sell_policy_hint': '',
                '_src': 'selfwatch',
            }
        except Exception:
            continue
    log.info('[exp] 自选股竞价三态合成 -> exceed=%d meet=%d miss=%d mid_skip=%d' % (n_ex, n_mt, n_ms, n_mid))
    return n_ex + n_mt + n_ms

def _confirm_expected(code):

    en = g.exp_file.get(code) or {}
    actual = _auction_change(code)
    exp_status = en.get("expected_status") or ""
    if "exceed" in exp_status:
        bm, has_bm = _auction_benchmark(code)
        if not has_bm:
            return PM, actual
        return (CX if actual >= bm else PM), actual
    if "miss" in exp_status:
        return (CS if actual < 0 else PM), actual
    return PM, actual

def _resync_buy_entry_type(code):

    if not BLS.get('exp_entry_type_resync', True):
        return str((g.exp.get(code) or {}).get('entry_type') or 'normal')
    en = g.exp_file.get(code) or {}
    if str(en.get('side') or (g.exp.get(code) or {}).get('side') or 'hold') != 'buy':
        return str((g.exp.get(code) or {}).get('entry_type') or en.get('entry_type') or 'normal')
    e = g.exp.setdefault(code, {})
    cur = str(e.get('entry_type') or en.get('entry_type') or 'normal')
    if str(cur).lower().startswith('one_word'):
        cur = 'one_word'
    ow = _is_one_word_open(code)
    if ow and cur != 'one_word':
        e['entry_type'] = 'one_word'
        en['entry_type'] = 'one_word'
        log.info('[exp-rt] %s entry_type=%s -> one_word(开盘重标)' % (_sn(code), cur))
        return 'one_word'
    if not ow and cur == 'one_word':
        e['entry_type'] = 'normal'
        en['entry_type'] = 'normal'
        log.info('[exp-rt] %s entry_type=one_word -> normal(已开板重标)' % _sn(code))
        return 'normal'
    return cur

def _exp_rt_status(code):

    en = g.exp_file.get(code) or {}
    e = g.exp.setdefault(code, {})
    for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct', 'seal_amount_t0', 'sell_policy_hint'):
        if en.get(_k) is not None:
            e[_k] = en[_k]
    entry = _resync_buy_entry_type(code)
    exp_status = str(e.get("expected_status") or en.get("expected_status") or "")
    au, _ra = _eval_auction(code)
    e["auction_status"] = au
    if entry == "one_word":
        st, _r = _exp_one_word(code)
        if "exceed" in exp_status and st == CM:
            return PM, "seal_wait"
        return st, "seal"
    if "exceed" in exp_status:

        acon, actual = _confirm_expected(code)
        if acon != CX:

            _bm, _has_bm = _auction_benchmark(code)
            _s0 = g.spot.get(code) or {}
            _op0 = float(_s0.get('open_px') or 0.0)

            if (not _has_bm or actual < -90.0
                    or (actual == 0.0 and (_op0 <= 0 or not _auction_ready(code)))):
                return PM, "await_intraday_confirm"
            return CS, "auction_not_met(%.1f%%)" % actual
        if (_two_1m_break(code) or _limit_up_within_1m(code)) and not _below_vwap_confirm(code):
            return CX, "intraday_exceed(%.1f%%)" % actual
        if _below_vwap_confirm(code):
            return CS, "below_vwap_weak"
        return PM, "observe_auction_exceed %.1f%%" % actual
    if "miss" in exp_status:
        return CS, "expect_miss"
    if not _intraday_confirmed_ready(code):
        return PM, "intraday_not_confirmed_ready"
    st = _eval_intraday(code, au)[0]
    return st, "intraday"

def _attempt_expected_buy(context, code, direction=None):

    dctx = direction if isinstance(direction, dict) else _exp_direction_eval(code)
    if dctx.get('hard_skip'):
        _exp_direction_log(code, dctx, 'skip')
        return None
    if _mid_board_avoid(code):
        _skip_log('mid_avoid', code, 'expected_buy', '[mid-avoid] %s 连板中位股规避(expected_buy)' % _sn(code)); return None
    _lbg, _lbg_note = _lb_senti_buy_gate(code)
    if not _lbg:
        _lb_gate_seen(code, _lbg_note, 'expected_buy')
        return None
    if code in (context.portfolio.positions or {}):
        return None
    if code in (g.exp_fired or set()):
        return None
    now = time.time()
    if now - g.buy_log.get(code, 0) < BLS["cold_secs"]:
        return None
    if not trade_open(code):
        return None
    st, reason = _exp_rt_status(code)
    if st == PM and str(reason).startswith("observe"):
        eo = g.exp.setdefault(code, {})
        if not eo.get("observe_seen"):
            eo["observe_seen"] = True
            log.info("[exp] %s observe %s -> 观察中(等分时确认)" % (_sn(code), reason))
    if st == CS:
        g.exp_fired.add(code)
        _save_state()
        log.info("[exp] %s miss=%s -> skip" % (_sn(code), reason))
        return True
    if st in (CX, CM):
        _exp_direction_log(code, dctx, 'allow')
        note = 'exp_rt %s %s dir=%s score=%.1f size_mult=1.0 reason=%s' % (
            st, reason, dctx.get('kind') or 'neutral', float(dctx.get('score') or 0.0),
            dctx.get('reason') or '-')
        if not place_expected_order(context, code, note=note):
            return None
        if st == CX and _dyn_unq_confirmed(code):
            log.info('[dyn-unq] %s CX 动态唯一龙头确认 -> 预期买入' % _sn(code))
        g.daily["bought"].append(code)
        g.exp_fired.add(code)
        g.buy_log[code] = now
        _save_state()
        return True
    return None

def _dyn_unq_state():

    try:
        day = str(get_trading_day())
    except Exception:
        day = ''
    st = getattr(g, 'dyn_unq', None)
    if not st or st.get('day') != day:
        st = {'day': day, 'auction': {}, 'uniq': {}, 'swept': {}}
        g.dyn_unq = st
    return st

def _auction_level(sec):

    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        return int(zt.get('board_cnt') or 0)
    except Exception:
        return 0

def _dyn_level_of(sec, snap=None):

    d = snap.get(sec) if snap else (g.spot.get(sec) or {})
    try:
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        base = int(zt.get('board_cnt') or 0)
    except Exception:
        base = 0
    try:
        up = float(d.get('up_px') or 0.0); px = float(d.get('last_px') or 0.0)
        if up > 0 and px and px >= up * 0.998:
            base += 1
    except Exception:
        pass
    return base

def _dyn_unq_confirmed(sec):

    st = getattr(g, 'dyn_unq', None)
    if not st:
        return False
    u = (st.get('uniq') or {}).get(sec) or {}
    return bool(u.get('uniq') and u.get('confirm'))

def _dyn_unq_auction_unique(sec):

    st = getattr(g, 'dyn_unq', None)
    if not st:
        return False
    a = (st.get('auction') or {}).get(sec) or {}
    return bool(a.get('unique'))

def _auction_board_of(sec):

    try:
        for b in _concept_boards_of(sec):
            if _board_members_file(b, 1):
                return b
        if getattr(g, 'stock_boards', None):
            for b in (g.stock_boards.get(sec) or []):
                if _board_members_file(b, 1):
                    return b
    except Exception:
        pass
    return None

def _dyn_unq_auction_eval():

    if not BLS.get('dyn_unq_enabled', True):
        return
    st = _dyn_unq_state()
    if st.get('auction_done'):
        return
    entries = {c: en for c, en in (g.exp_file or {}).items() if str(en.get('side') or '') == 'buy'}
    if not entries:
        return
    cboard = {}
    board_of = {}
    for c in entries:
        b = _auction_board_of(c)
        if b:
            cboard[c] = b
            board_of.setdefault(b, []).append(c)
    for c, en in entries.items():
        st_ = str(en.get('expected_status') or '')
        exceed = 'exceed' in st_
        if BLS.get('dyn_unq_mid_skip', True) and _mid_board_avoid(c):
            log.info('[dyn-unq] %s 中位股不参与唯一预判 -> skip' % _sn(c))
            continue
        b = cboard.get(c)
        mapped = bool(b)
        lvl = _auction_level(c)
        peer_n = 0; peer_ex = 0
        for p in (board_of.get(b) or []) if mapped else []:
            if p == c:
                continue
            if _auction_level(p) != lvl:
                continue
            peer_n += 1
            if 'exceed' in str((g.exp_file.get(p) or {}).get('expected_status') or ''):
                peer_ex += 1
        unique = (exceed and peer_ex == 0
                  and (mapped or not BLS.get('dyn_unq_require_board_map', True)))
        st['auction'][c] = {'exceed': exceed, 'level': lvl, 'peer_cnt': peer_n,
                            'peer_exceed': peer_ex, 'mapped': mapped, 'unique': unique}
        if exceed:
            if mapped:
                log.info('[dyn-unq] 竞价唯一预判 %s 身位=%s 竞品=%d/超预期=%d -> %s' % (
                    _sn(c), lvl, peer_n, peer_ex, '唯一' if peer_ex == 0 else '并列'))
            else:
                log.info('[dyn-unq] %s 板块未映射/成员缺失 -> 不判唯一 (竞品无法评估)' % _sn(c))
    st['auction_done'] = True
    return len(st['auction'])

def _dyn_unq_eval_uniq(sec, st, now):

    boards = [b for b in _concept_boards_of(sec) if _board_members_file(b, 1)]
    if not boards:
        return
    board = boards[0]
    members = [m for m in _board_members_file(board, int(BLS.get('dyn_unq_member_cap', 15))) if m]
    if not members:
        return
    _need = [m for m in members if not (g.spot.get(m) or {}).get('last_px')]
    if _need:
        try:
            _snap = _get_snapshot_many(_need, len(_need)) or {}
            for _m, _d in _snap.items():
                if _d:
                    g.spot[_m] = _d
        except Exception:
            pass
    my_lvl = _dyn_level_of(sec, {sec: g.spot.get(sec) or {}})
    higher = same = False
    for m in members:
        if m == sec:
            continue
        ml = _dyn_level_of(m, {m: g.spot.get(m) or {}})
        if ml > my_lvl:
            higher = True
        elif ml == my_lvl:
            same = True
    if higher or same:
        st['uniq'][sec] = {'board': board, 'uniq': False, 'ts': now, 'level': my_lvl, 'members': members}
        return
    st['uniq'][sec] = {'board': board, 'uniq': True, 'ts': now, 'level': my_lvl,
                       'members': members, 'confirm': False, 'confirm_ts': 0,
                       'follow_ev': False, 'last_follow': 0.0, 'surge_cnt': 0}
    log.info('[dyn-unq] %s 板块=%s 身位=%d -> 动态唯一龙头(首触)' % (_sn(sec), board, my_lvl))
def _dyn_unq_eval_follow(sec, st, u):

    now = time.time()
    if u.get('confirm'):
        return
    if now - float(u.get('last_follow') or 0) < 15.0:
        return
    u['last_follow'] = now
    first_ts = ((g.first_zt or {}).get(sec) or {}).get('ts') or u.get('ts') or now
    if now - float(first_ts) > float(BLS.get('dyn_unq_follow_win_sec', 300.0)):
        return
    members = u.get('members') or []
    if not u.get('follow_ev'):
        _need = [m for m in members if m != sec and not (g.spot.get(m) or {}).get('last_px')]
        if _need:
            try:
                _snap = _get_snapshot_many(_need, len(_need)) or {}
                for _m, _d in _snap.items():
                    if _d:
                        g.spot[_m] = _d
            except Exception:
                pass
        u['follow_ev'] = True
    my_lvl = u.get('level') or _dyn_level_of(sec, {sec: g.spot.get(sec) or {}})
    followers = []
    for m in members:
        if m == sec:
            continue
        d = g.spot.get(m) or {}
        try:
            up = float(d.get('up_px') or 0.0); px = float(d.get('last_px') or 0.0)
            pre = float(d.get('preclose_px') or 0.0)
        except Exception:
            continue
        if up > 0 and px and px >= up * 0.998:
            continue
        if _dyn_level_of(m, {m: d}) >= my_lvl:
            continue
        chg = (px / pre - 1.0) * 100.0 if (pre > 0 and px > 0) else -1.0
        if chg > 0:
            followers.append((chg, m))
    followers.sort(reverse=True)
    surge_cnt = 0
    for _chg, m in followers[:int(BLS.get('dyn_unq_surge_top_n', 5))]:
        try:
            if _elastic_1m_surge(m) >= float(BLS.get('dyn_unq_surge_pct', 1.5)):
                surge_cnt += 1
        except Exception:
            continue
    u['surge_cnt'] = surge_cnt
    if surge_cnt >= int(BLS.get('dyn_unq_follower_min', 2)):
        u['confirm'] = True; u['confirm_ts'] = now
        log.info('[dyn-unq] %s 跟风确认 %d家(1m>=%.1f%%) -> 确认' % (
            _sn(sec), surge_cnt, float(BLS.get('dyn_unq_surge_pct', 1.5))))
def _try_dyn_sweep(context, st=None):

    if not BLS.get('dyn_sweep_enabled', True):
        return
    if _min_age() > int(BLS.get('dyn_sweep_window_minute', 15)):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    st = st or _dyn_unq_state()
    positions = context.portfolio.positions
    now = time.time()
    for sec, en in (g.exp_file or {}).items():
        if str(en.get('side') or '') != 'buy':
            continue
        if sec in positions or sec in g.daily['bought'] or sec in st.get('swept', {}):
            continue
        if not _dyn_unq_auction_unique(sec) or not _dyn_unq_confirmed(sec):
            continue
        if not trade_open(sec):
            continue
        if _is_one_word_open(sec) or _block_sealed_buy(sec):
            continue
        s = g.spot.get(sec) or {}
        px = last_px(sec); up = float(s.get('up_px') or 0.0)
        if not px or px <= 0 or up <= 0 or px >= up * 0.998:
            continue
        if not (_two_1m_break(sec) or _limit_up_within_1m(sec)):
            continue
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs']:
            continue
        limit = _order_limit(sec, 'buy', 'board')
        if not limit:
            log.info('[dyn-sweep] %s sealed -> no sweep' % _sn(sec))
            continue
        if place_order(context, sec, 'buy',
                       note='dyn_sweep px=%.2f limit=%.2f 跟风%d家' % (
                           px, limit, (st.get('uniq', {}).get(sec) or {}).get('surge_cnt', 0)),
                       mode='board', ratio=float(BLS.get('dyn_sweep_budget_ratio', 0.20))):
            g.daily['bought'].append(sec); g.buy_log[sec] = now
            st['swept'][sec] = {'ts': now}
            _save_state()
            return
def _try_dyn_unq(context):

    if not BLS.get('dyn_unq_enabled', True):
        return
    if _min_age() > int(BLS.get('dyn_unq_window_minute', 30)):
        return
    positions = context.portfolio.positions
    st = _dyn_unq_state()
    now = time.time()
    try:
        for sec in list(positions):
            if _dyn_unq_confirmed(sec) and (g.first_zt or {}).get(sec):
                _hold_arb_log(sec, '盘中动态唯一龙头确认 -> 持有提示(不改卖出阈值)')
    except Exception:
        pass
    cands = [c for c, en in (g.exp_file or {}).items()
             if str(en.get('side') or '') == 'buy' and (g.first_zt or {}).get(c) and c not in positions]
    for sec in cands:
        try:
            u = st['uniq'].get(sec)
            if u is not None and u.get('uniq') is False:
                if now - float(u.get('ts') or 0) < 60.0:
                    continue
                u['ts'] = now
            if u is None or u.get('uniq') is False:
                _dyn_unq_eval_uniq(sec, st, now)
                u = st['uniq'].get(sec)
            if not u or not u.get('uniq'):
                continue
            _dyn_unq_eval_follow(sec, st, u)
        except Exception as e:
            _warn('dyn_unq %s fail %r' % (_sn(sec), e))
    _try_dyn_sweep(context, st)

def _pool_exp_priority(code, direction=None):

    try:
        sc = float(score_now(code) or 0.0)
    except Exception:
        sc = 0.0
    dctx = direction if isinstance(direction, dict) else _exp_direction_eval(code)
    if _dyn_unq_confirmed(code):
        sc += float(BLS.get('dyn_unq_sort_bonus', 2.0))
    sc += _zt_theme_sort_bonus(code)
    sc += float(dctx.get('score') or 0.0) * _lb_senti_participate_scale()
    act = _first_zt_ms(code) or 1e18
    return (-sc, act)

def _try_expected_buys(context):

    if _min_age() > int(BLS.get('exp_buy_window_min', 30)):
        return
    if not g.exp_file or len(g.daily["bought"]) >= BLS["daily_max_buy"]:
        return
    cands = []
    for idx, (code, en) in enumerate(g.exp_file.items()):
        if str(en.get("side") or "") != "buy":
            continue
        dctx = _exp_direction_eval(code)
        if dctx.get('hard_skip'):
            _exp_direction_log(code, dctx, 'skip')
            continue
        cands.append((code, dctx, _pool_exp_priority(code, direction=dctx), idx))

    cands.sort(key=lambda x: (x[2][0], x[2][1], x[3]))
    for code, dctx, _prio, _idx in cands:
        _attempt_expected_buy(context, code, direction=dctx)
        if len(g.daily["bought"]) >= BLS["daily_max_buy"]:
            return

def _ma5_first_5d(sec):

    df = _hist_1d(sec)
    if df is None or len(df) < 9:
        return False
    try:
        closes = list(df['close'])
        lows = list(df['low']) if 'low' in df else closes
    except Exception:
        return False
    n = len(closes)

    for i in range(n - 2, max(n - 6, 0), -1):
        lo = i - 4
        if lo < 0:
            continue
        ma5 = sum(closes[lo:i+1]) / 5.0
        if ma5 <= 0:
            return False
        if lows[i] > 0 and lows[i] <= ma5 + 0.001:
            return False
    return True
def try_ma5_buy(context):
    if _min_age() > int(BLS.get('ma5_buy_window_min', 240)):
        return
    positions = context.portfolio.positions
    day = str(get_trading_day())
    if getattr(g, 'ma5_touch_day', None) != day:
        g.ma5_touch_day = day; g.ma5_touched = set()
    if not isinstance(getattr(g, 'ma5_touched', None), set):
        g.ma5_touched = set(getattr(g, 'ma5_touched', None) or [])
    if getattr(g, 'ma5_lifecycle_day', None) != day:
        g.ma5_lifecycle_day = day; g.ma5_lows = {}
    if not isinstance(getattr(g, 'ma5_lows', None), dict):
        g.ma5_lows = {}
    for sec in _pool():
        if sec in positions:
            continue
        tags = _tags(sec)
        if BLS.get('ma5_core_only', True) and 'CORE' not in tags:
            continue
        px = last_px(sec)
        if not px or px <= 0:
            continue
        second_low = _ma5_second_low(sec, px)
        if _mid_board_avoid(sec):
            _skip_log('mid_avoid', sec, 'ma5', '[mid-avoid] %s 连板中位股规避(ma5)' % _sn(sec)); continue
        if BLS.get('ma5_require_bs', False) and 'BS' not in tags:
            continue
        if BLS.get('ma5_first_5d', False) and not _ma5_first_5d(sec):
            continue
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        ma5 = _ensure_ma5(sec)
        if not ma5:
            continue
        if BLS.get('ma5_second_low_enabled', True):
            ref_px = second_low
            ma5_ref = _ma5_at_price(sec, ref_px) if ref_px else None
        else:
            ref_px = px
            ma5_ref = ma5
        if not ref_px or not ma5_ref:
            continue
        band = abs(float(ref_px) - float(ma5_ref)) / float(ma5_ref)
        if band <= float(BLS.get('ma5_touch_band', 0.02)) + 1e-12:
            score = score_now(sec)
            if not score:
                continue
            if sec in g.ma5_touched:
                continue
            if score >= float(BLS.get('ma5_buy_score_min', 50.0)) and _buy_red_ok(sec):
                note = ('ma_pullback px=%.2f low2=%.2f ref=%.2f ma5=%.2f ma5ref=%.2f '
                        'band=%.2f%% ma5b4=%.2f score=%.1f l2=%.2f%% red=%.2f tags=%s') % (
                    px, ref_px, ref_px, ma5, ma5_ref, band * 100.0, (_ma5_base4(sec) or 0.0),
                    score, _l2_big_ratio(sec) * 100.0, _red_ratio(sec), ','.join(_tags(sec)))
                if place_order(context, sec, 'buy', note=note, mode='pullback',
                               ratio=float(BLS.get('ma5_buy_ratio', 0.10))):
                    g.ma5_touched.add(sec)
                    g.daily['bought'].append(sec); g.buy_log[sec] = now
                    _save_state()
                    if len(g.daily['bought']) >= BLS['daily_max_buy']:
                        break
            else:
                g.ma5_touched.add(sec)

def try_core_buy(context):

    if not BLS.get('core_buy_enabled', True):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if _min_age() > int(BLS.get('core_buy_window_min', 30)):
        return
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        if 'CORE' not in _tags(sec):
            continue
        if _mid_board_avoid(sec):
            _skip_log('mid_avoid', sec, 'core_buy', '[mid-avoid] %s 连板中位股规避(core_buy)' % _sn(sec)); continue
        if _is_one_word_open(sec):
            continue
        if _limitup_days(sec) >= int(BLS.get('core_max_lianban', 6)):
            continue
        if BLS.get('core_sealed_skip', True) and _block_sealed_buy(sec):
            continue
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        px = last_px(sec)
        if not px or px <= 0:
            continue
        score = score_now(sec)
        if not score:
            continue
        if score >= BLS['buy_score_min'] and _buy_red_ok(sec):
            if place_order(context, sec, 'buy', note='core_buy px=%.2f score=%.1f tags=%s' % (px, score, ','.join(_tags(sec))), mode='chase'):
                g.daily['bought'].append(sec); g.buy_log[sec] = now
                _save_state()
                if len(g.daily['bought']) >= BLS['daily_max_buy']:
                    break

def _sector_chg(sec):

    px = last_px(sec); pre = pre_close(sec)
    if not px or not pre or pre <= 0:
        return 0.0
    return px / pre - 1.0

def _is_one_word_open(sec):

    s = g.spot.get(sec) or {}
    op = float(s.get('open_px') or 0.0)
    up = float(s.get('up_px') or 0.0)
    return bool(op and up and op >= up * 0.998)

def _is_first_board(sec):

    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec)
    if zt:
        return int(zt.get('board_cnt') or 0) < 1
    return _limitup_days(sec) <= 1

def _board_member_codes(sec):

    if not getattr(g, 'bs_codes', None):
        g.bs_codes = {}
    c = g.bs_codes.get(sec)
    if c and (time.time() - c[0]) < 60:
        return list(c[1])
    codes = []
    cap = int(BLS.get('board_member_cap', 20))
    try:

        if getattr(g, 'boards', None):
            for b in _concept_boards_of(sec):
                codes = _board_members_file(b, cap)
                if codes:
                    break
        if not codes:
            blocks = get_stock_blocks(sec) or {}
            board_code = None
            for lst in blocks.values():
                if isinstance(lst, list):
                    for row in lst:
                        if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                            board_code = row[0]
                            break
                if board_code:
                    break
            if board_code:
                codes = [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board_code)) or [])[:cap]) if x]
    except Exception:
        codes = []
    g.bs_codes[sec] = (time.time(), tuple(codes))
    return codes

def _board_top_gainer(sec):

    my = _sector_chg(sec)
    if my <= 0:
        return False
    mem = [m for m in _board_member_codes(sec) if m != sec]
    _need = [m for m in mem if not (g.spot.get(m) or {}).get('last_px') or not (g.spot.get(m) or {}).get('preclose_px')]
    if _need:
        try:
            _sn = _get_snapshot_many(_need, len(_need)) or {}
            for _m, _d in _sn.items():
                if _d:
                    g.spot[_m] = _d
        except Exception:
            pass
    for m in mem:
        try:
            d = g.spot.get(m) or {}
            mp = float(d.get('preclose_px') or 0.0); mpx = float(d.get('last_px') or 0.0)
        except Exception:
            continue
        if mp > 0 and mpx > 0 and (mpx / mp - 1.0) > my + 1e-9:
            return False
    return True

def _first_zt_ms(sec):

    f = (g.first_zt or {}).get(sec) or {}
    ms = f.get('ms')
    if ms:
        try:
            return int(ms)
        except Exception:
            pass
    ts = f.get('ts') or 0.0
    if not ts:
        return 0
    lt = time.localtime(float(ts))
    return int(time.strftime('%Y%m%d%H%M%S', lt)) * 1000 + int(float(ts) % 1 * 1000)

def _board_first_zt(sec):

    my = _first_zt_ms(sec) or None
    for m in _board_member_codes(sec):
        if m == sec:
            continue
        if _is_one_word_open(m):
            continue
        t = _first_zt_ms(m)
        if t and (my is None or t < my - 1e-6):
            return False
    return True

def _try_first_board_buy(context, sec, rank_secs=None):

    if not BLS.get('first_board_buy_enabled', True):
        return
    if _min_age() > int(BLS.get('first_board_minute', 10)):
        return
    if sec in getattr(context, 'portfolio', None).positions:
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    if BLS.get('skip_st_pool', True) and _is_st(sec):
        _skip_log('st_skip', sec, 'st', '[st-skip] %s ST股首板拦截(first_board)' % _sn(sec)); return
    if _is_one_word_open(sec):
        return
    if not _is_first_board(sec):
        return
    if not _lb_senti_gate_apply(sec, 'first_board'):
        return
    _fg = _ferment_front_gate(sec)
    if _fg is False:
        log.info('[ferment] %s 新题材助攻非前排 -> skip first_board' % _sn(sec)); return
    if _mid_board_avoid(sec):
        _skip_log('mid_avoid', sec, 'first_board', '[mid-avoid] %s 连板中位股规避(first_board)' % _sn(sec)); return
    now = time.time()
    if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
        return
    if BLS.get('board_rank_enabled', True):
        rs = rank_secs if rank_secs is not None else _near_limit_cands(_pool())
        if not _board_rank_top3(sec, rs or [sec]):
            return
    if not _board_top_gainer(sec):
        return
    if not _board_first_zt(sec):
        return
    if _block_sealed_buy(sec):
        return
    amt, _cnt = _seal_metrics(sec)
    seal_min = float(BLS.get('first_board_seal_min', 50000.0))
    _big_r = _l2_big_ratio(sec)
    if seal_min > 0 and amt > 0 and amt < seal_min and not _l2_big_ok(sec):
        log.info('[firstboard] %s 封单不足 seal=%.0f<%.0f 且无大单加持(big=%.2f%%) -> skip' % (
            _sn(sec), amt, seal_min, _big_r * 100.0 if _big_r >= 0 else 0.0))
        return
    s = g.spot.get(sec) or {}
    up = float(s.get('up_px') or 0.0)
    if not up or up <= 0:
        return
    limit = _order_limit(sec, 'buy', 'board')
    if not limit:
        log.info('[firstboard] %s sealed -> skip board queue' % _sn(sec))
        return
    if place_order(context, sec, 'buy', note='first_board_buy px=%.2f limit=%.2f chg=%.1f%% tags=%s' % (
        last_px(sec) or 0.0, limit, _sector_chg(sec) * 100.0, ','.join(_tags(sec))), mode='board',
        ratio=BLS.get('board_buy_budget_ratio', 0.20)):
        g.daily['bought'].append(sec); g.buy_log[sec] = now
        if not getattr(g, 'first_board_fired', None):
            g.first_board_fired = set()
        g.first_board_fired.add(sec)
        _save_state()

def _try_reboard_buy(context):

    if not BLS.get('reboard_buy_enabled', True):
        return
    if _min_age() > int(BLS.get('reboard_until_minute', 30)):
        return
    if getattr(g, 'reboard_fired', False):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    cands = []
    for sec, ft in (getattr(g, 'first_zt', None) or {}).items():
        if not isinstance(ft, dict):
            continue
        if int(ft.get('break_cnt') or 0) < 1:
            continue
        if ft.get('break'):
            continue
        s0 = g.spot.get(sec) or {}
        last = float(s0.get('last_px') or 0.0); u0 = float(s0.get('up_px') or 0.0)
        if last <= 0 or u0 <= 0 or last < u0 * 0.998:
            continue
        if _is_one_word_open(sec) or sec in context.portfolio.positions:
            continue
        if _mid_board_avoid(sec):
            continue
        if _limitup_days(sec) > int(BLS.get('reboard_max_lianban', 2)):
            continue
        cands.append((float(ft.get('reboard_ts') or 0), sec))
    if not cands:
        return
    cands.sort(key=lambda x: x[0])
    _ts, sec = cands[0]
    if not _lb_senti_gate_apply(sec, 'reboard'):
        return
    if BLS.get('board_rank_enabled', True):
        rs = _near_limit_cands(_pool())
        if not _board_rank_top3(sec, rs or [sec]):
            _skip_log('reboard', sec, 'non_front', '[reboard] %s 非前排(强度前三) -> skip' % _sn(sec)); return
    amt, _cnt = _seal_metrics(sec)
    seal_min = float(BLS.get('reboard_seal_min', 50000.0))
    big_r = _l2_big_ratio(sec)
    big_ok = _l2_big_ok(sec) and big_r >= float(BLS.get('reboard_l2_big_min', 0.10))
    if not big_ok:
        _skip_log('reboard', sec, 'l2_big_low', '[reboard] %s 大单占比=%.2f%%<%s%% -> skip' % (_sn(sec), big_r * 100.0 if big_r >= 0 else 0.0, float(BLS.get('reboard_l2_big_min', 0.10)) * 100.0)); return
    if seal_min > 0 and amt > 0 and amt < seal_min:
        _skip_log('reboard', sec, 'seal_low', '[reboard] %s 封单不足 seal=%.0f<%.0f -> skip' % (_sn(sec), amt, seal_min)); return
    if _block_sealed_buy(sec):
        return
    limit = _order_limit(sec, 'buy', 'board')
    if not limit:
        log.info('[reboard] %s sealed -> skip board queue' % _sn(sec)); return
    if place_order(context, sec, 'buy', note='reboard_buy break_cnt=%d l2_big=%.2f%% px=%.2f limit=%.2f' % (
        int(((g.first_zt or {}).get(sec) or {}).get('break_cnt') or 0), big_r * 100.0 if big_r >= 0 else 0.0, last_px(sec) or 0.0, limit), mode='board',
        ratio=BLS.get('board_buy_budget_ratio', 0.20)):
        g.daily['bought'].append(sec); g.buy_log[sec] = time.time()
        g.reboard_fired = True
        _save_state()

def _try_first_board_buy_1m(context):

    if not BLS.get('first_board_buy_enabled', True):
        return
    positions = context.portfolio.positions
    for sec in _pool():
        if sec in positions:
            continue
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        if sec in (getattr(g, 'first_board_fired', None) or set()):
            continue
        s = g.spot.get(sec) or {}
        px = last_px(sec); up = float(s.get('up_px') or 0.0)
        if not px or not up or px < up * 0.998:
            continue
        if not g.first_zt.get(sec):
            g.first_zt[sec] = {'first_seal': 0.0, 'first_bids': 0, 'ts': time.time(),
                               'break': False, 'day': str(get_trading_day())}
        try:
            _try_first_board_buy(context, sec)
        except Exception as e:
            _warn('first_board_buy(1m) fail %r' % e)

def _elastic_yizi_pool():

    out = list(_pool()) + list((getattr(g, 'zt_lianban', {}) or {}).keys())
    return [x for x in (_norm_sec(c) for c in out) if x]

def _boards_of(sec):

    try:
        dh = _get_ds()
        v = dh.cached('blocks', sec, 300.0, lambda: _fetch_boards_of(sec), budget='blocks', stale_ok=True)
        return list(v) if v else []
    except Exception:
        return []

def _fetch_boards_of(sec):
    try:
        blocks = get_stock_blocks(sec) or {}
        names = []
        for lst in blocks.values():
            if isinstance(lst, list):
                for row in lst:
                    if isinstance(row, list) and len(row) >= 1 and str(row[0]).strip():
                        names.append(str(row[0]).strip())
        return tuple(names)
    except Exception:
        return ()

def _elastic_yizi_scan():

    if not getattr(g, 'elastic_cache', None):
        g.elastic_cache = {'day': '', 'ts': 0.0, 'strong': {}}
    c = g.elastic_cache
    day = str(get_trading_day())
    now = time.time()
    if c.get('day') == day and now - c.get('ts', 0.0) < float(BLS.get('elastic_arb_cache_ttl', 60.0)):
        return c.get('strong', {})

    _need = [sec for sec in _elastic_yizi_pool() if sec not in g.spot]
    if _need:
        try:
            for _cc, _dd in (_get_snapshot_many(_need, len(_need)) or {}).items():
                if _dd:
                    g.spot[_cc] = _dd
        except Exception:
            pass
    yizi = []
    for sec in _elastic_yizi_pool():
        try:
            s = g.spot.get(sec) or {}
            pre = float(s.get('preclose_px') or 0.0)
            op = float(s.get('open_px') or 0.0)
            if pre <= 0 or op <= 0 or op < pre * (1.0 + _limit_threshold(sec)) * 0.995:
                continue
            seal, _b = _seal_metrics(sec)
            if seal > 0:
                yizi.append(sec)
        except Exception:
            continue
    from collections import Counter
    cnt = Counter()
    for sec in yizi:
        for b in _concept_boards_of(sec):
            cnt[b] += 1
    strong = {b: n for b, n in cnt.items() if n >= int(BLS.get('elastic_arb_min_yizi', 2))}
    c.update(day=day, ts=now, strong=strong)
    log.info('[elastic] yizi=%d strong_boards=%d' % (len(yizi), len(strong)))
    return strong

def _elastic_in_strong_board(sec, strong):

    for b in _concept_boards_of(sec):
        if b in strong:
            return True
    return False

def _calc_1m_surge(sec):

    df = get_price(sec, start_date=None, end_date=None, count=2, frequency='1m')
    if df is None or len(df) < 1:
        return 0.0
    o = float(df['open'].iloc[-1] or 0.0); close_px = float(df['close'].iloc[-1] or 0.0)
    return (close_px / o - 1.0) * 100.0 if o > 0 else 0.0

def _elastic_1m_surge(sec):

    try:
        dh = _get_ds()
        v = dh.cached('m1_surge', sec, float(BLS.get('m1_surge_cache_ttl', 15.0)),
                      lambda: _calc_1m_surge(sec), budget='m1')
        return v if v is not None else 0.0
    except Exception:
        return 0.0

def _try_elastic_arb_buy(context):

    if not BLS.get('elastic_arb_enabled', True):
        return
    if _min_age() > int(BLS.get('elastic_arb_window_minute', 20)):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    strong = _elastic_yizi_scan()
    if not strong:
        return
    positions = context.portfolio.positions
    rank_secs = [c for c in _pool() if _is_elastic_eligible(c)]
    cands = []
    for sec in _pool():
        if sec in positions:
            continue
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        if not _is_elastic_eligible(sec):
            continue
        if not _lb_senti_gate_apply(sec, 'elastic'):
            continue
        if not _elastic_in_strong_board(sec, strong):
            continue
        if BLS.get('board_rank_enabled', True) and not _board_rank_top3(sec, rank_secs or [sec]):
            continue
        if _is_one_word_open(sec):
            continue
        s = g.spot.get(sec) or {}
        pre = float(s.get('preclose_px') or 0.0)
        if pre <= 0:
            continue
        op = float(s.get('open_px') or 0.0)
        open_chg = ((op / pre - 1.0) * 100.0) if op > 0 else _auction_change(sec)
        if open_chg > _elastic_max_open_change(sec) + 1e-9:
            continue
        px = last_px(sec)
        if not px or px <= 0:
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg < _elastic_min_change(sec) - 1e-9 or chg > _elastic_max_change(sec) + 1e-9:
            continue
        surge = _elastic_1m_surge(sec)
        if surge < float(BLS.get('elastic_arb_min_1m_surge', 3.0)):
            continue
        big = _l2_big_ratio(sec)
        cands.append((sec, px, chg, open_chg, surge, _elastic_big_bonus_pts(sec), big, bool(_l2_big_ok(sec))))
    cands.sort(key=lambda t: (-(t[5] + t[4]), -t[2]))
    for sec, px, chg, open_chg, surge, _big_bonus, big, big_ok in cands:
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs'] or not trade_open(sec):
            continue
        if _block_sealed_buy(sec):
            continue
        limit = _order_limit(sec, 'buy', 'chase')
        if place_order(context, sec, 'buy', note='elastic_arb px=%.2f limit=%.2f chg=%.1f%% 1m=%.1f%% open=%.1f%% big=%s big_ok=%d boards=%s' % (
            px, limit or px, chg, surge, open_chg, _fmt_big_ratio(big), int(big_ok), ','.join(list(strong.keys())[:2])), mode='chase'):
            g.daily['bought'].append(sec); g.buy_log[sec] = now
            _save_state()

def _board_probe():

    try:
        if not BLS.get('board_probe_enabled', True):
            return None
        day = str(get_trading_day())
        if getattr(g, 'board_probe_day', None) == day:
            return getattr(g, 'board_probe', None)
        g.board_probe_day = day
        samp = [x for x in (_norm_sec(c) for c in (list(get_positions()) + BLS['universe'] + _pool())) if x][:2]
        if not samp:
            samp = ['600570.XSHG']
        out = {}
        for sec in samp:
            try:
                blocks = get_stock_blocks(sec) or {}
            except Exception:
                blocks = {}
            rows = {}
            for cat, lst in (blocks or {}).items():
                rows[str(cat)] = [str(r[0]) if isinstance(r, list) and r else '' for r in (lst or [])[:3]]
            codes = []
            for cat in ('HY', 'GN', 'ZJHHY', 'DY'):
                for r in (blocks or {}).get(cat, []) or []:
                    if isinstance(r, list) and r and str(r[0]).strip():
                        codes.append((cat, str(r[0]).strip()))
                        break
            counts = {}
            for cat, code in codes[:2]:
                try:
                    counts['%s:%s' % (cat, code)] = len(get_industry_stocks(code) or [])
                except Exception:
                    counts['%s:%s' % (cat, code)] = -1
            out[sec] = {'cats': rows, 'members': counts}
            log.info('[probe] %s blocks=%s industry_members=%s' % (_sn(sec), rows, counts))
        g.board_probe = out
        return out
    except Exception as e:
        _warn('board probe fail: %r' % e)
        return None

def _elastic_top_cand_src():

    out = list(_pool()) + list((getattr(g, 'zt_lianban', {}) or {}).keys())
    return [x for x in (_norm_sec(c) for c in out) if x]

def _board_open_gain(board_code):

    try:
        dh = _get_ds()
        v = dh.cached('board_open', str(board_code), 86400.0,
                      lambda: _fetch_board_open_gain(board_code), budget='board', stale_ok=True)
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0

def _fetch_board_open_gain(board_code):

    gains = []
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(board_code, 20)) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        for m in mem:
            try:
                d = sn.get(m) or {}
                pre = float(d.get('preclose_px') or 0.0)
                op = float(d.get('open_px') or 0.0)
                if pre > 0 and op > 0:
                    gains.append(op / pre - 1.0)
            except Exception:
                continue
    except Exception:
        gains = []
    return (sum(gains) / len(gains)) * 100.0 if gains else 0.0

def _concept_active():

    try:
        return bool(BLS.get('board_concept_unified', True)) and bool(getattr(g, 'boards', None))
    except Exception:
        return False

def _concept_boards_of(sec):

    try:
        sb = getattr(g, 'stock_boards', None)
        if sb:
            bts = getattr(g, 'board_type', None) or {}
            return [nm for nm in (sb.get(sec) or []) if str(bts.get(nm) or '') == 'concept']
        return _boards_of(sec)
    except Exception:
        return _boards_of(sec)

def _board_members_file(board, cap):

    try:
        gb = getattr(g, 'boards', None)
        if gb:
            mem = gb.get(str(board)) or []
            return [x for x in (_norm_sec(m) for m in mem[:cap]) if x]
        return [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board)) or [])[:cap]) if x]
    except Exception:
        try:
            return [x for x in (_norm_sec(m) for m in (get_industry_stocks(str(board)) or [])[:cap]) if x]
        except Exception:
            return []

def _concept_snap_union(boards):

    dh = _get_ds()
    try:
        day = str(get_trading_day())
    except Exception:
        day = ''
    key = '|'.join(sorted(str(b) for b in boards))
    led = getattr(g, 'csnap_led', None)
    if not led or led.get('day') != day or led.get('key') != key:
        led = {'day': day, 'key': key, 'members': [], 'idx': 0, 'snap': {}, 'ts': 0.0, 'complete': False}
        g.csnap_led = led
    now = time.time()
    if now - float(led.get('ts') or 0.0) < float(BLS.get('board_rank_ttl_fast', 3.0)):
        return led['snap'], (1.0 if led.get('complete') else float(led.get('ratio') or 0.0))
    if not led['members']:
        seen = set()
        for b in boards:
            for m in _board_members_file(b, int(BLS.get('elastic_top_member_cap', 20))):
                if m not in seen:
                    seen.add(m); led['members'].append(m)
    total = len(led['members'])
    idx = int(led.get('idx') or 0)
    if idx >= total:
        idx = 0; led['idx'] = 0
        led['complete'] = True
    if dh.spend('board'):
        cap = int(BLS.get('frame_snap_batch', 100))
        batch = led['members'][idx:idx + cap]
        try:
            sn = _get_snapshot_many(batch, len(batch))
            if isinstance(sn, dict):
                led['snap'].update(sn)
                led['idx'] = idx + len(batch)
        except Exception:
            pass
        led['ts'] = now
    ratio = (int(led.get('idx') or 0) / total) if total else 1.0
    if led.get('complete'):
        ratio = 1.0
    led['ratio'] = ratio
    return led['snap'], ratio

def _concept_snap_for(board, mem):

    try:
        led = getattr(g, 'csnap_led', None)
        if led and (time.time() - float(led.get('ts') or 0.0)) < float(BLS.get('board_rank_ttl_fast', 3.0)):
            if str(board) in (str(led.get('key') or '')).split('|'):
                return led.get('snap') or {}
    except Exception:
        pass
    try:
        dh = _get_ds()
        v = dh.cached(('cbsnap', str(board)), '_', _board_refresh_ttl(),
                      lambda: _get_snapshot_many(mem, len(mem)) or {}, budget='board', stale_ok=True)
        return v if v is not None else {}
    except Exception:
        return {}

def _concept_board_strength(board, snap=None):

    try:
        if not _concept_active():
            return _board_strength_by_code(board)
    except Exception:
        return _board_strength_by_code(board)
    mem = _board_members_file(board, int(BLS.get('elastic_top_member_cap', 20)))
    if not mem:
        return 0.0
    if snap is None:
        snap = _concept_snap_for(board, mem)
    chgs = []
    for m in mem:
        try:
            d = snap.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre > 0 and px > 0:
                chgs.append(px / pre - 1.0)
        except Exception:
            continue
    return (sum(chgs) / len(chgs)) * 100.0 if chgs else 0.0

def _compute_concept_board_top1_lead(boards):

    if not boards:
        return (None, 0.0)
    snap, ratio = _concept_snap_union(boards)
    if ratio < 0.5:
        return (None, 0.0)
    best = None; best_st = None; second_st = None
    for b in boards:
        try:
            st = _concept_board_strength(b, snap=snap)
        except Exception:
            continue
        if best is None or st > best_st:
            second_st = best_st
            best, best_st = b, st
        elif second_st is None or st > second_st:
            second_st = st
    if best_st is None:
        return (None, 0.0)
    return (best, best_st - (second_st if second_st is not None else 0.0))

def _concept_board_rank_top1(secs):

    try:
        if not getattr(g, 'boards', None):
            return _board_rank_top1(secs)
    except Exception:
        return _board_rank_top1(secs)
    secs = [s for s in (secs or []) if s]
    if not secs:
        return (None, 0.0)
    boards = sorted({b for s in secs for b in _concept_boards_of(s) if b})
    if not boards:
        return (None, 0.0)
    try:
        dh = _get_ds()
        token = '|'.join(boards)
        v = dh.cached(('concept_top1', token), '_', _board_refresh_ttl(),
                      lambda: _compute_concept_board_top1_lead(boards), single=True)
        if isinstance(v, tuple) and len(v) == 2:
            return v
        return (v, 0.0)
    except Exception:
        return (None, 0.0)

def _board_5d_cache():

    if not getattr(g, 'board_5d', None):
        g.board_5d = {'day': '', 'data': {}}
    c = g.board_5d
    day = str(get_trading_day())
    if c.get('day') != day:
        c['day'] = day
        c['data'] = {}
    return c

def _calc_board_5d(board_code, rec):

    dh = _get_ds()
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(board_code, 20)) if x]
    except Exception:
        mem = []
    rec = dict(rec or {})
    total = len(mem)
    rec['total'] = total
    idx = int(rec.get('idx') or 0)
    ssum = float(rec.get('sum') or 0.0)
    cnt = int(rec.get('cnt') or 0)
    for i in range(idx, total):
        if not dh.spend('day'):
            break
        try:
            df = get_price(mem[i], start_date=None, end_date=None, count=6, frequency='1d')
            if df is not None and len(df) >= 6:
                closes = [float(df['close'].iloc[j]) for j in range(len(df))]
                chgs = [closes[j] / closes[j - 1] - 1.0 for j in range(1, 6) if closes[j - 1] > 0]
                if chgs:
                    ssum += sum(chgs) / len(chgs)
                    cnt += 1
        except Exception:
            pass
        idx = i + 1
    rec['idx'] = idx
    rec['sum'] = ssum
    rec['cnt'] = cnt
    rec['ratio'] = (cnt / total) if total else 1.0
    rec['avg'] = (ssum / cnt) * 100.0 if cnt else 0.0
    rec['finished'] = (total == 0) or (idx >= total)
    return rec

def _board_5d_strength(board_code):

    try:
        c = _board_5d_cache()
        rec = c['data'].get(board_code)
        if rec is None or not (rec.get('finished') or rec.get('ratio', 0.0) >= 0.5):
            rec = _calc_board_5d(board_code, rec or {})
            c['data'][board_code] = rec
        if rec.get('finished') or rec.get('ratio', 0.0) >= 0.5:
            return rec.get('avg')
        return None
    except Exception:
        return None

def _new_top_board_scan():

    if not BLS.get('elastic_top_enabled', True):
        return None
    if _min_age() > int(BLS.get('elastic_top_window_minute', 20)):
        return None
    et = getattr(g, 'elastic_top', None) or {'day': '', 'top': '', 'ts': 0.0, 'tracked': set(), 'trig': 0, 'done': False}
    g.elastic_top = et
    day = str(get_trading_day())
    if et.get('day') != day:
        et.update(day=day, top='', ts=0.0, tracked=set(), trig=0, done=False)
        et.pop('stab', None)
    top, lead = _concept_board_rank_top1(_elastic_top_cand_src())
    if not top:
        return None
    n_need = int(BLS.get('elastic_top_stable_frames', 3))
    lead_min = float(BLS.get('elastic_top_lead_min', 0.5))
    if top == et.get('top'):
        return None if et.get('done') else top
    stab = et.setdefault('stab', {'code': '', 'n': 0})
    if lead < lead_min:
        stab.update(code='', n=0)
    elif stab.get('code') != top:
        stab.update(code=top, n=1)
    else:
        stab['n'] = stab.get('n', 0) + 1
    if stab['n'] < n_need:
        if et.get('top') and not et.get('done'):
            return et['top']
        return None
    st = _concept_board_strength(top)
    if st < float(BLS.get('elastic_top_min_strength', 2.0)):
        return None
    open_g = _board_open_gain(top)
    avg5 = _board_5d_strength(top)
    if avg5 is None:
        return None
    if open_g < float(BLS.get('elastic_top_breakout_min_open', 1.0)):
        return None
    if open_g < avg5 + float(BLS.get('elastic_top_breakout_min_boost', 2.0)):
        return None
    if et.get('trig', 0) >= int(BLS.get('elastic_top_max_trigger_per_day', 2)):
        return None
    et['top'] = top; et['ts'] = time.time(); et['done'] = False
    if top in (et.get('tracked') or set()):
        return None
    et['tracked'].add(top); et['trig'] = et.get('trig', 0) + 1
    log.info('[elastic] new_top_board %s strength=%.1f%% open=%.1f%% avg5=%.1f%% lead=%.1f%% -> 启动弹性跟踪(最主动20cm/北交,10%%/15%%前买)' % (
        top, st, open_g, avg5, lead))
    return top

def _calc_elastic_top_candidates(top):

    out = []
    try:
        mem = [x for x in (_norm_sec(m) for m in _board_members_file(top, 30)) if x]
        sn = _get_snapshot_many(mem, len(mem)) or {}
        pre_rank = []
        for m in mem:
            if not _is_elastic_eligible(m):
                continue
            d = sn.get(m) or g.spot.get(m) or {}
            pre = float(d.get('preclose_px') or 0.0)
            px = float(d.get('last_px') or 0.0)
            if pre <= 0 or px <= 0:
                continue
            chg = (px / pre - 1.0) * 100.0
            if chg <= 0 or chg >= _elastic_top_buy_before(m):
                continue
            pre_rank.append((chg, m))
        pre_rank.sort(key=lambda t: -t[0])
        for chg, m in pre_rank[:int(BLS.get('elastic_top_surge_top_n', 5))]:
            surge = _elastic_1m_surge(m)
            out.append((surge, chg, _elastic_big_bonus_pts(m), m))
    except Exception:
        return []
    out.sort(key=lambda t: (-(t[0] + t[2]), -t[1]))
    return [m for _, _, _, m in out]

def _elastic_top_candidates(top):

    try:
        dh = _get_ds()
        v = dh.cached(('elastic_top', str(top)), '_', float(BLS.get('elastic_top_cache_ttl', 30.0)),
                      lambda: _calc_elastic_top_candidates(top))
        return list(v) if v else []
    except Exception:
        return []

def _try_elastic_top_buy(context):

    if not BLS.get('elastic_top_enabled', True):
        return
    if _min_age() > int(BLS.get('elastic_top_window_minute', 20)):
        return
    if len(g.daily['bought']) >= BLS['daily_max_buy']:
        return
    top = _new_top_board_scan()
    if not top:
        return
    positions = context.portfolio.positions
    for sec in _elastic_top_candidates(top):
        if sec in positions:
            continue
        if sec in g.daily['bought']:
            continue
        if len(g.daily['bought']) >= BLS['daily_max_buy']:
            return
        if not trade_open(sec):
            continue
        if not _lb_senti_gate_apply(sec, 'elastic'):
            continue
        if _is_one_word_open(sec):
            continue
        if _block_sealed_buy(sec):
            continue
        if _mid_board_avoid(sec):
            continue
        s = g.spot.get(sec) or {}
        pre = float(s.get('preclose_px') or 0.0)
        if pre <= 0:
            continue
        px = last_px(sec)
        if not px or px <= 0:
            continue
        chg = (px / pre - 1.0) * 100.0
        if chg <= 0 or chg >= _elastic_top_buy_before(sec):
            continue
        op = float(s.get('open_px') or 0.0)
        open_chg = ((op / pre - 1.0) * 100.0) if op > 0 else _auction_change(sec)
        if open_chg > _elastic_max_open_change(sec) + 1e-9:
            continue
        surge = _elastic_1m_surge(sec)
        if surge < float(BLS.get('elastic_top_min_1m_surge', 2.0)):
            continue
        big = _l2_big_ratio(sec)
        now = time.time()
        if now - g.buy_log.get(sec, 0) < BLS['cold_secs']:
            continue
        limit = _order_limit(sec, 'buy', 'chase')
        if place_order(context, sec, 'buy', note='elastic_top board=%s px=%.2f limit=%.2f chg=%.1f%% 1m=%.1f%% big=%s big_ok=%d' % (
            top, px, limit or px, chg, surge, _fmt_big_ratio(big), int(_l2_big_ok(sec))), mode='chase'):
            g.daily['bought'].append(sec); g.buy_log[sec] = now
            et = getattr(g, 'elastic_top', None)
            if et:
                et['done'] = True
            _save_state()
        return

def _realtime_weak(sec):

    try:
        if _auction_change(sec) < 0:
            return True
        if sec in g.spot and _below_vwap(sec):
            return True
        return False
    except Exception:
        return False

def _hold_arb_log(sec, msg):

    try:
        gl = getattr(g, 'hold_arb_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.hold_arb_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0) < 60.0:
            return
        gl[sec] = now
        log.info('[arb] %s %s' % (_sn(sec), msg))
    except Exception:
        pass

def _role_tolerance(sec):

    en = g.exp_file.get(sec) or {}
    e = g.exp.get(sec) or {}
    hint = str(e.get('sell_policy_hint') or en.get('sell_policy_hint') or 'none')
    tbl = BLS.get('sell_policy', {})
    rp = tbl.get(hint) or tbl.get('none') or {'green_tol': 1.0, 'stop_adj': 1.0, 'score_clear_adj': 1.0, 'score_half_adj': 1.0}
    if hint not in ('', 'none') and _realtime_weak(sec):

        _gt = float(rp.get('green_tol') or 1.0)
        _sa = float(rp.get('stop_adj') or 1.0)
        _n = _gt > 1.0 or _sa > 1.0
        if _n:
            _hold_arb_log(sec, '文件 sell_policy=%s 乐观容忍 vs 云端实时走弱 -> P1/P3 阈值回落基础(实时优先)' % hint)
            return {'green_tol': 1.0 if _gt > 1.0 else _gt, 'stop_adj': 1.0 if _sa > 1.0 else _sa,
                    'score_clear_adj': float(rp.get('score_clear_adj') or 1.0),
                    'score_half_adj': float(rp.get('score_half_adj') or 1.0)}
    return rp

def _sellable_source():

    try:
        p = get_positions() or {}
    except Exception:
        p = {}
    return p if isinstance(p, dict) and p else {}

_SEL_FIELDS_AVAIL = ('enable_amount', 'available_amount', 'sellable_amount', 'closeable_amount',
                     'real_enable_amount', 'm_nCanUseVolume', 'm_nPREnableVolume',
                     'can_use_volume', 'enable_volume', 'sellable_volume')
_SEL_FIELDS_TOTAL = ('current_amount', 'amount', 'hold_amount', 'holding_amount', 'm_nVolume', 'volume')

def _sellable_detail(sec, positions):

    p = positions.get(sec)
    for key in _SEL_FIELDS_AVAIL:
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is None:
                continue
            return max(int(float(v) or 0), 0), key, True, False
        except Exception:
            continue
    for key in _SEL_FIELDS_TOTAL:
        try:
            v = p.get(key) if isinstance(p, dict) else getattr(p, key, None)
            if v is None:
                continue
            qty = max(int(float(v) or 0), 0)
            if key == 'm_nVolume':
                try:
                    fv = p.get('m_nFrozenVolume') if isinstance(p, dict) else getattr(p, 'm_nFrozenVolume', None)
                    qty = max(qty - max(int(float(fv) or 0), 0), 0)
                except Exception:
                    pass
            return qty, key, False, True
        except Exception:
            continue
    if p is not None:
        _audit_pos_fields(sec, p)
    return 0, '', False, False

def _sellable(sec, positions):
    return _sellable_detail(sec, positions)[0]

def _limit_down_price(sec):

    pre = pre_close(sec)
    if not pre or pre <= 0:
        return None
    num = str(sec).split('.')[0]
    if num.startswith(('300', '301', '688', '689')):
        ratio = float(BLS.get('limit_down_chinext', 0.20))
    elif num.startswith(('8', '4', '92')):
        ratio = float(BLS.get('limit_down_bse', 0.30))
    else:
        ratio = float(BLS.get('limit_down_main', 0.10))
    return max(pre * (1.0 - ratio), 0.0)

def _sell_inflight(sec):

    p = (getattr(g, 'pending', None) or {}).get(sec) or {}
    if str(p.get('side') or '') != 'sell':
        return False
    st = str(p.get('status') or 'SENT').upper()
    if st in ('FILLED', 'CANCELLED', 'REJECTED'):
        return False
    ts = float(p.get('ts') or 0)
    if ts > 0 and (time.time() - ts) > float(BLS.get('sell_pending_timeout', 120.0)):
        return False
    return True

def _do_sell(context, sec, qty, note, urgent=False, mode=None, cool=True):

    if qty <= 0:
        return
    if not isinstance(getattr(g, 'sold_log', None), dict):
        g.sold_log = {}
    if cool:
        g.sold_log[sec] = time.time()
    place_order(context, sec, 'sell', qty=qty, note=note, mode=mode or ('sell_urgent' if urgent else 'sell'))

def _audit_pos_fields(sec, p):

    try:
        gl = getattr(g, 'pos_field_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.pos_field_log = gl
        now = time.time()
        if now - float(gl.get(sec) or 0) < 3600.0:
            return
        gl[sec] = now
        if isinstance(p, dict):
            log.info('[pos-fields] %s %s keys=%s' % (_sn(sec), type(p).__name__, sorted(str(k) for k in p.keys())))
        else:
            log.info('[pos-fields] %s %s attrs=%s' % (_sn(sec), type(p).__name__, sorted(str(a) for a in dir(p) if not a.startswith('_'))[:40]))
    except Exception:
        pass

def _audit_sell_skip(sec, why, now=None):

    try:
        now = now or time.time()
        gs = getattr(g, 'last_skip_log', None)
        if not isinstance(gs, dict):
            gs = {}; g.last_skip_log = gs
        if now - float(gs.get(sec) or 0) < 60.0:
            return
        gs[sec] = now
        log.info('[sell-skip] %s %s (positions=%s)' % (_sn(sec), why, sorted(str(x) for x in (getattr(g, 'holdings_keys_hint', None) or []))))
    except Exception:
        pass

def _p2e_core_sell_check(sec):

    if not BLS.get('p2e_sell_enabled', True):
        return False, ''
    en = g.exp_file.get(sec) or {}
    if str(en.get('side') or '') not in ('sell', 'hold'):
        return False, ''
    _au = _auction_change(sec)

    _mid = None
    if BLS.get('p2e_theme_sell_enabled', True):
        try:
            for _nm in _zt_themes_of(sec):
                for _c in ((getattr(g, 'zt_theme', {}) or {}).get(_nm) or {}).get('members') or []:
                    _rec = (getattr(g, 'zt_lianban', {}) or {}).get(_c) or {}
                    _bc = int(_rec.get('board_cnt') or 0)
                    if not (2 <= _bc <= 5):
                        continue
                    _acm = _auction_change(_c)
                    if _mid is None or _acm < _mid[0]:
                        _mid = (_acm, _c, _auction_benchmark(_c))
        except Exception:
            _mid = None
    _hitA = False; _noteA = ''
    if _mid is not None:
        _dm = float(BLS.get('p2e_theme_drop_min', -2.0))
        if _mid[0] <= _dm:
            _bmv, _bmok = _mid[2]
            if (_bmok and _mid[0] < _bmv) or (not _bmok and _mid[0] < 0):
                _hitA = True
                _noteA = 'P2E_theme_mid_break mid=%s ac=%.1f%%' % (_sn(_mid[1]), _mid[0])

    _est = str(en.get('expected_status') or '')
    _ma = ('confirmed_miss', 'degraded')
    if BLS.get('exp_sell_on_pending_miss', False):
        _ma = _ma + ('pending_miss',)
    _hitB = bool(_est and _est in _ma and _au <= float(BLS.get('p2e_auction_drop_min', -2.0)))
    if _hitB:
        try:
            _rev, _ra = _confirm_expected(sec)
            if _rev == CX:
                _hold_arb_log(sec, '文件预期=%s 悲观 vs 云端实时竞价超预期(CX) -> 不核卖' % _est)
                _hitB = False
        except Exception:
            pass

    if (_hitA or _hitB) and _unique_stand(sec):
        _hold_arb_log(sec, '唯一高身位豁免 P2E 竞价核卖 -> 交盘中监控')
        return False, ''
    if _hitA:
        return True, _noteA
    if _hitB:
        return True, 'P2E_exp_miss %s ac=%.1f%%' % (_est, _au)
    return False, ''

def p2e_auction_core_sell(context):

    _set_now(context)
    if not BLS.get('p2e_sell_enabled', True):
        return
    _hms = _hhmmss()
    _confirm_at = str(BLS.get('p2e_confirm_at', '09:24:45'))
    if not (_confirm_at <= _hms < '09:25:30'):
        if not getattr(g, 'p2e_warm_logged', False):
            g.p2e_warm_logged = True
            log.info('[P2E] 竞价核卖监控启动 预热段 09:15-%s 不触发（确认段 %s-09:25 评估）' % (_confirm_at, _confirm_at))
        return
    if getattr(g, 'p2e_fresh_day', None) != str(get_trading_day()):
        g.auction_c = {}
        g.p2e_fresh_day = str(get_trading_day())
        try:
            _load_expectation(merge=True)
        except Exception:
            pass
    positions = _sellable_source() or context.portfolio.positions
    if not positions:
        return
    _sl = float(BLS.get('sell_cold_secs', 30.0))
    for _raw in list(positions.keys()):
        sec = _norm_sec(_raw) or _raw
        amt = _sellable(_raw, positions)
        if amt <= 0:
            continue
        if _sell_inflight(sec):
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (time.time() - g.sold_log.get(sec, 0)) < _sl:
            continue
        try:
            _hit, _note = _p2e_core_sell_check(sec)
        except Exception as _e:
            _warn('p2e check fail %s: %r' % (_sn(sec), _e)); continue
        if _hit:
            log.info('[P2E] %s 竞价核卖 %s hms=%s' % (_sn(sec), _note, _hms))
            _do_sell(context, sec, amt, _note, urgent=True)

def sell_manager(context):
    positions = _sellable_source() or context.portfolio.positions
    sl = float(BLS.get('sell_cold_secs', 30.0))

    g.holdings_keys_hint = sorted(str(x) for x in positions.keys())
    for _raw in list(positions.keys()):
        sec = _norm_sec(_raw) or _raw
        px = last_px(sec); cost = my_cost(_raw, positions)
        if not px or px <= 0:
            _audit_sell_skip(sec, 'no_px(lookup key=%s)' % _raw)
            continue
        try:
            _hold_exp_init(sec)
        except Exception:
            pass
        amt = _sellable(_raw, positions)
        if amt <= 0:
            _q0, _k0, _av0, _tv0 = _sellable_detail(_raw, positions)
            _bought_today = '1' if str(_raw) in ((getattr(g, 'daily', None) or {}).get('bought') or []) else '0'
            _audit_sell_skip(sec, 'amt0(lookup key=%s field=%s avail=%d total=%d t1=%s)' % (
                _raw, _k0 or '-', int(_av0), int(_tv0), _bought_today))
            continue
        now = time.time()
        if _sell_inflight(sec):
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (now - g.sold_log.get(sec, 0)) < sl:
            continue
        rp = _role_tolerance(sec)
        if _auction_change(sec) <= BLS['green_open_drop'] * rp['green_tol']:
            _do_sell(context, sec, amt, 'P1_green_open drop=%.1f%%' % _auction_change(sec), urgent=True); continue

        _hit2, _note2 = _p2e_core_sell_check(sec)
        if _hit2:
            _do_sell(context, sec, amt, _note2, urgent=True); continue
        if cost > 0:
            pnl_pct = px / cost - 1.0
            if pnl_pct <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss pnl=%.1f%%' % (pnl_pct * 100), urgent=True); continue

        if BLS.get('p7_sell_enabled', True):
            _p7a = _p7a_check(sec, amt)
            if _p7a and sec not in (getattr(g, 'p7a_sold', None) or set()):
                _do_sell(context, sec, _p7a[1], _p7a[0]); _mark_p7(sec, 'p7a'); continue
            _p7b = _p7b_check(sec, amt)
            if _p7b and sec not in (getattr(g, 'p7b_sold', None) or set()):
                _do_sell(context, sec, _p7b[1], _p7b[0]); _mark_p7(sec, 'p7b'); continue
            _p7c = _p7c_check(sec, amt)
            if _p7c:
                _do_sell(context, sec, _p7c[1], _p7c[0], cool=False); _save_state(); continue

        _p8 = _lb_senti_cut_hold(sec)
        if _p8:
            _q8 = int(int(amt * float(_p8[0])) // 100) * 100
            if _q8 < 100:
                _q8 = amt if amt < 100 else 100
            _do_sell(context, sec, _q8, _p8[1]); _mark_lb_cut(sec); continue

        if sec in g.exp:
            if g.exp[sec].get('entry_type') == 'one_word' and _is_one_word_open(sec):
                st, _r = _exp_one_word(sec)
                if st == CS or st == PS:
                    _do_sell(context, sec, amt, 'P4_exp_one_word ' + st); continue
            else:

                if g.exp[sec].get('entry_type') == 'one_word' and not _is_one_word_open(sec):
                    _hold_arb_log(sec, '文件 entry_type=one_word 但实时已开板 -> 回落普通分时三态')
                au = g.exp[sec].get('auction_status') or _eval_auction(sec)[0]
                st = _eval_intraday(sec, au)[0]
                if st in (PS, CS):
                    _do_sell(context, sec, amt, 'P4_exp_miss ' + st); continue
        _en = g.exp_file.get(sec) or {}
        if str(_en.get('side') or '') == 'sell':
            _eun, _ea2 = _confirm_expected(sec)
            if _eun == CS:
                _do_sell(context, sec, amt, 'P4_exp_sell ' + _eun); continue
        sc = score_now(sec)
        if sc is None:
            continue
        if sc < BLS['score_sell_clear'] * rp['score_clear_adj']:
            _do_sell(context, sec, amt, 'P5_score_clear score=%.1f' % sc)
        elif sc < BLS['score_sell_half'] * rp['score_half_adj']:
            half = int(amt * float(BLS.get('sell_half_ratio', 0.5)))
            qty = int(half // 100) * 100
            if qty < 1:
                qty = amt if amt < 100 else 100
            if qty > amt:
                qty = amt
            _do_sell(context, sec, qty, 'P6_score_half score=%.1f' % sc)

def tick_sell_manager(context):
    g.sellscan_used = 0

    if not BLS.get('tick_sell_enabled', True):
        return
    positions = _sellable_source() or context.portfolio.positions
    sl = float(BLS.get('sell_cold_secs', 30.0))
    for _raw in list(positions.keys()):
        sec = _norm_sec(_raw) or _raw
        px = last_px(sec)
        if not px or px <= 0:
            continue
        amt = _sellable(_raw, positions)
        if amt <= 0:
            continue
        try:
            _hold_exp_init(sec)
        except Exception:
            pass
        now = time.time()
        if _sell_inflight(sec):
            continue
        if isinstance(getattr(g, 'sold_log', None), dict) and (now - g.sold_log.get(sec, 0)) < sl:
            continue
        ft = (g.first_zt or {}).get(sec) or {}

        if BLS.get('break_sell_enabled', True) and ft.get('break'):
            _bc = int(ft.get('break_cnt') or 0)
            if _bc >= 2 and _unique_stand(sec):
                if sec not in (getattr(g, 'break2_sold', None) or set()):
                    _half = int(amt * float(BLS.get('break2_half_ratio', 0.5)))
                    _half = int(_half // 100) * 100
                    _do_sell(context, sec, _half if _half >= 100 else amt,
                             'TICK_break2_half_sell break_cnt=%d held=%.0fs' % (_bc, now - float(ft.get('break_ts') or now)), mode='sell_break')
                    _mark_sold_event(sec, 'break2')
                    continue
            else:
                if sec not in (getattr(g, 'break_sold', None) or set()):
                    _do_sell(context, sec, amt, 'TICK_break_sell break_cnt=%d held=%.0fs' % (_bc, now - float(ft.get('break_ts') or now)), mode='sell_break')
                    _mark_sold_event(sec, 'break')
                    continue

        if BLS.get('seal_low_sell_enabled', True) and ft.get('seal_low'):
            if sec not in (getattr(g, 'seal_sold', None) or set()):
                _do_sell(context, sec, amt,
                         'TICK_seal_low_sell ratio<=%.2f' % float(BLS.get('seal_fail_ratio', 0.333)),
                         mode='sell_break')
                _mark_sold_event(sec, 'seal')
                continue

        rp = _role_tolerance(sec)
        if _auction_change(sec) <= BLS['green_open_drop'] * rp['green_tol']:
            _do_sell(context, sec, amt, 'P1_green_open_tick drop=%.1f%%' % _auction_change(sec), urgent=True); continue
        _hit2, _note2 = _p2e_core_sell_check(sec)
        if _hit2:
            _do_sell(context, sec, amt, _note2, urgent=True); continue
        cost = my_cost(_raw, positions)
        if cost > 0:
            pnl = px / cost - 1.0
            if pnl <= -get_stop_loss_pct(sec) * rp['stop_adj']:
                _do_sell(context, sec, amt, 'P3_stop_loss_tick pnl=%.1f%%' % (pnl * 100), urgent=True); continue

        if BLS.get('p7_sell_enabled', True):
            _p7a = _p7a_check(sec, amt)
            if _p7a and sec not in (getattr(g, 'p7a_sold', None) or set()):
                _do_sell(context, sec, _p7a[1], _p7a[0]); _mark_p7(sec, 'p7a'); continue
            _p7b = _p7b_check(sec, amt)
            if _p7b and sec not in (getattr(g, 'p7b_sold', None) or set()):
                _do_sell(context, sec, _p7b[1], _p7b[0]); _mark_p7(sec, 'p7b'); continue
            _p7c = _p7c_check(sec, amt)
            if _p7c:
                _do_sell(context, sec, _p7c[1], _p7c[0], cool=False); _save_state(); continue

        _p8 = _lb_senti_cut_hold(sec)
        if _p8:
            _q8 = int(int(amt * float(_p8[0])) // 100) * 100
            if _q8 < 100:
                _q8 = amt if amt < 100 else 100
            _do_sell(context, sec, _q8, _p8[1]); _mark_lb_cut(sec); continue

        if not BLS.get('tick_full_sell_enabled', True):
            continue
        if int(getattr(g, 'sellscan_used', 0)) >= int(BLS.get('frame_sellscan_limit', 8)):
            continue
        g.sellscan_used = int(getattr(g, 'sellscan_used', 0)) + 1
        if sec in g.exp:
            if g.exp[sec].get('entry_type') == 'one_word' and _is_one_word_open(sec):
                st4, _r4 = _exp_one_word(sec, quiet=True)
                if st4 in (CS, PS):
                    _do_sell(context, sec, amt, 'P4_exp_one_word_tick ' + st4); continue
            else:
                if g.exp[sec].get('entry_type') == 'one_word' and not _is_one_word_open(sec):
                    _hold_arb_log(sec, '文件 entry_type=one_word 但实时已开板 -> 回落普通分时三态')
                au4 = g.exp[sec].get('auction_status') or _eval_auction(sec)[0]
                st4 = _eval_intraday(sec, au4)[0]
                if st4 in (PS, CS):
                    _do_sell(context, sec, amt, 'P4_exp_miss_tick ' + st4); continue

        if _hist_1d(sec) is None:
            continue
        sc = score_now(sec)
        if sc is None:
            continue
        if sc < BLS['score_sell_clear'] * rp['score_clear_adj']:
            _do_sell(context, sec, amt, 'P5_score_clear_tick score=%.1f' % sc)
        elif sc < BLS['score_sell_half'] * rp['score_half_adj']:
            half = int(amt * float(BLS.get('sell_half_ratio', 0.5)))
            qty = int(half // 100) * 100
            if qty < 1:
                qty = amt if amt < 100 else 100
            if qty > amt:
                qty = amt
            _do_sell(context, sec, qty, 'P6_score_half_tick score=%.1f' % sc)

def _mark_sold_event(sec, kind):

    try:
        key = 'break_sold' if kind == 'break' else ('break2_sold' if kind == 'break2' else 'seal_sold')
        st = getattr(g, key, None)
        if not isinstance(st, set):
            st = set(); setattr(g, key, st)
        st.add(sec)
        _save_state()
    except Exception:
        pass

def _hold_stand_pts(role, active, board):

    pts = 0.0
    pts += {'leader': 3.0, 'follower': -1.0, 'mid': -3.0}.get(role, 0.0)
    pts += {'active': 3.0, 'follow': -3.0}.get(active, 0.0)
    if board == 'weak':
        pts -= 3.0
    return pts

def _hold_board_strong(sec):

    try:
        if _board_strength(sec) >= float(BLS.get('p7b_board_min', 1.0) or 1.0):
            return True
        st = _dyn_theme_status()
        for nm in _zt_themes_of(sec):
            d = st.get(nm) or {}
            ld = d.get('leader')
            if ld and _sealed_now(ld):
                return True
        fm = _dyn_theme_ferment()
        for nm in _new_themes_of(sec):
            d = fm.get(nm) or {}
            if d.get('confirmed') and d.get('front') and _sealed_now(d['front']):
                return True
    except Exception:
        pass
    return False

def _hold_stand(sec):

    try:
        cache = getattr(g, 'hold_stand_cache', None)
        if not isinstance(cache, dict):
            cache = {}; g.hold_stand_cache = cache
        now = time.time()
        hit = cache.get(sec)
        if hit and now - float(hit.get('ts') or 0) < float(BLS.get('hold_stand_cache_sec', 15.0) or 15.0):
            return hit
        role = 'outside'; active = 'neutral'; board = 'mid'
        zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
        cnt = int(zt.get('board_cnt') or 0)
        if _dyn_theme_leader(sec):
            role = 'leader'
        elif zt and cnt >= 1:
            if 2 <= cnt <= 5 and not zt.get('unique_high'):
                role = 'mid'
            else:

                st = _dyn_theme_status()
                is_fol = False
                for nm in _zt_themes_of(sec):
                    d = st.get(nm) or {}
                    if d.get('leader') and d.get('leader') != sec and int(d.get('alive_count') or 0) > 1:
                        is_fol = True; break
                role = 'follower' if is_fol else 'outside'

        try:
            my_chg = _sector_chg(sec) * 100.0
            bstr = _board_strength(sec)
            if bstr > 0 and my_chg >= bstr + float(BLS.get('p7c_active_threshold', 0.5) or 0.5):
                active = 'active'
            elif bstr >= 1.0 and my_chg <= bstr - float(BLS.get('p7c_active_threshold', 0.5) or 0.5):
                active = 'follow'
        except Exception:
            pass

        try:
            if _hold_board_strong(sec):
                board = 'strong'
            elif _board_strength(sec) <= -1.0:
                board = 'weak'
            else:
                board = 'mid'
        except Exception:
            pass
        out = {'ts': now, 'role': role, 'active': active, 'board': board}
        cache[sec] = out
        gl = getattr(g, 'hold_stand_log', None)
        if not isinstance(gl, dict):
            gl = {}; g.hold_stand_log = gl
        if now - float(gl.get(sec) or 0) >= float(BLS.get('hold_stand_log_sec', 60.0) or 60.0):
            gl[sec] = now
            log.info('[hold] %s role=%s active=%s board=%s pts=%+.1f' % (
                _sn(sec), role, active, board, _hold_stand_pts(role, active, board)))
        return out
    except Exception:
        return {'ts': time.time(), 'role': 'outside', 'active': 'neutral', 'board': 'mid'}

def _p7a_check(sec, amt):

    if not BLS.get('p7_sell_enabled', True):
        return None
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
    if int(zt.get('board_cnt') or 0) < 2:
        return None
    if _sealed_now(sec):
        return None
    df = _hist_1d(sec)
    if df is None or len(df) < 2:
        return None
    vols = list(df['volume'])
    yv = float(vols[-2] or 0.0)
    tv = _snap_vol(g.spot.get(sec) or {})
    if yv <= 0 or tv <= 0:
        return None
    if tv < yv * float(BLS.get('p7a_vol_ratio', 1.10) or 1.10):
        return None
    if _unique_stand(sec):
        half = int(amt * float(BLS.get('p7a_half_ratio', 0.5) or 0.5))
        half = int(half // 100) * 100
        qty = half if half >= 100 else amt
        return ('P7a_vol_break_half vol=%.0f yv=%.0f' % (tv, yv), qty)
    return ('P7a_vol_break vol=%.0f yv=%.0f' % (tv, yv), amt)

def _p7b_check(sec, amt):

    if not BLS.get('p7_sell_enabled', True):
        return None
    st = _hold_stand(sec)
    if st.get('role') not in ('follower', 'outside'):
        return None
    if st.get('board') != 'strong':
        return None
    if _sealed_now(sec):
        return None
    sg = _elastic_1m_surge(sec)
    if sg < float(BLS.get('p7b_surge_min', 1.5) or 1.5):
        return None
    half = int(amt * float(BLS.get('p7b_half_ratio', 0.5) or 0.5))
    half = int(half // 100) * 100
    qty = half if half >= 100 else amt
    return ('P7b_follow_break surge=%.1f%%' % sg, qty)

def _p7c_check(sec, amt):

    if not BLS.get('p7_sell_enabled', True):
        return None
    zt = (getattr(g, 'zt_lianban', {}) or {}).get(sec) or {}
    if int(zt.get('board_cnt') or 0) != 1:
        return None
    if _min_age() > int(BLS.get('p7c_until_minute', 30) or 30):
        return None

    if _today_zt(sec) or _sealed_now(sec):
        part = getattr(g, 'p7c_part', None)
        if isinstance(part, dict) and sec in part:
            del part[sec]
        sold = getattr(g, 'p7c_sold', None)
        if isinstance(sold, set) and sec in sold:
            sold.discard(sec)
        return None
    st = _hold_stand(sec)
    if st.get('active') == 'active':
        part = getattr(g, 'p7c_part', None)
        if isinstance(part, dict) and sec in part:
            del part[sec]
        return None
    part = getattr(g, 'p7c_part', None)
    if not isinstance(part, dict):
        part = {}; g.p7c_part = part
    px = last_px(sec) or 0.0
    rec = part.get(sec)
    if rec is None:
        part[sec] = {'ts': time.time(), 'price': px}
        return None
    tripx = float(rec.get('price') or 0.0) * (1.0 + float(BLS.get('p7c_surge_min', 1.5) or 1.5) / 100.0)
    if px < tripx:
        return None
    now = time.time()
    cold = float(BLS.get('p7c_batch_cold_secs', 10.0) or 10.0)
    if rec.get('sold1_ts'):
        if now - float(rec['sold1_ts']) < cold:
            return None
        qty = min(int(float(rec.get('half') or amt)), amt)
        if qty < 100:
            qty = amt
        part.pop(sec, None)
        sold = getattr(g, 'p7c_sold', None)
        if not isinstance(sold, set):
            sold = set(); g.p7c_sold = sold
        sold.add(sec)
        return ('P7c_passive_sweep b2 px=%.2f tripx=%.2f' % (px, tripx), qty)
    half = int(amt * 0.5)
    half = int(half // 100) * 100
    if half < 1:
        half = amt if amt < 100 else 100
    rec['half'] = half
    rec['sold1_ts'] = now
    return ('P7c_passive_sweep b1 px=%.2f tripx=%.2f' % (px, tripx), half)

def _mark_p7(sec, kind):

    try:
        key = 'p7a_sold' if kind == 'p7a' else 'p7b_sold'
        st = getattr(g, key, None)
        if not isinstance(st, set):
            st = set(); setattr(g, key, st)
        st.add(sec)
        _save_state()
    except Exception:
        pass

def _l2_probe(context):

    if getattr(g, 'l2_probed', False):
        return
    try:
        secs = list(get_positions()) or (_pool() or [])[:1]
        if not secs:
            return
        sec = secs[0]
        tx = get_individual_transaction([sec], data_count=10, is_dict=True) or {}
        ent = get_individual_entrust([sec], data_count=10, is_dict=True) or {}
        n_tx = len(tx.get(sec) or []) if isinstance(tx, dict) else 0
        n_ent = len(ent.get(sec) or []) if isinstance(ent, dict) else 0
        gear = get_gear_price(sec) or {}
        bid_cnt = 0
        try:
            grp = gear.get('bid_grp') if isinstance(gear, dict) else {}
            if isinstance(grp, dict):
                for row in grp.values():
                    if isinstance(row, (list, tuple)) and len(row) >= 3:
                        bid_cnt = int(row[2] or 0)
                        break
        except Exception:
            bid_cnt = 0
        if isinstance(tx, dict) and tx.get(sec):
            log.info('[l2] %s tx_row=%s' % (_sn(sec), tx[sec][-1]))
        if isinstance(tx, dict) and tx.get('fields'):
            log.info('[l2] %s tx_fields=%s' % (_sn(sec), list(tx['fields'])))
        ok = 'L2_OK' if (n_tx or n_ent or bid_cnt) else 'L2_NONE'
        log.info('[l2] code=%s tx=%d entrust=%d gear_bid_cnt=%d -> %s' % (_sn(sec), n_tx, n_ent, bid_cnt, ok))

        try:
            _s1 = get_snapshot([sec]) or {}
            _s1 = (_s1.get(sec) or {}) if isinstance(_s1, dict) else {}
            _b1 = (_s1.get('bid_grp') or {}).get(1) or []
            _l2q = bool(isinstance(_b1, (list, tuple)) and len(_b1) >= 4 and _b1[3])
            log.info('[l2] %s snap total_bidqty=%s total_offerqty=%s entrust_diff=%s entrust_rate=%s bid1_queue_l2=%s' % (
                _sn(sec), _s1.get('total_bidqty'), _s1.get('total_offerqty'),
                _s1.get('entrust_diff'), _s1.get('entrust_rate'), _l2q))
            _bs = 0.0; _as = 0.0
            for _r in (gear.get('bid_grp') or {}).values():
                if isinstance(_r, (list, tuple)) and len(_r) >= 2:
                    _bs += float(_r[1] or 0)
            for _r in (gear.get('offer_grp') or {}).values():
                if isinstance(_r, (list, tuple)) and len(_r) >= 2:
                    _as += float(_r[1] or 0)
            log.info('[l2] %s gear bid_sum=%s offer_sum=%s' % (_sn(sec), _bs, _as))
        except Exception as _e:
            _warn('l2 totals probe fail %r' % _e)

        try:
            _dfv = _hist_1d(sec)
            _vv = list(_dfv['volume']) if _dfv is not None and len(_dfv) >= 2 else []
            _sv = g.spot.get(sec) or {}
            log.info('[vol] %s snap business_amount=%s volume=%s trd_volume=%s hist1d[-1]=%s hist1d[-2]=%s' % (
                _sn(sec), _sv.get('business_amount'), _sv.get('volume'), _sv.get('trd_volume'),
                (_vv[-1] if len(_vv) >= 1 else 'NA'), (_vv[-2] if len(_vv) >= 2 else 'NA')))
        except Exception:
            pass
        g.l2_probed = True
    except Exception as e:
        _warn('l2 probe fail: %r' % e)

def _tick_targets():

    tok = int(time.time() / 3.0)
    _c = getattr(g, 'tick_targets_cache', None) or {}
    if _c.get('tok') == tok:
        return _c['secs']
    pos = list(get_positions())
    _skip_st = BLS.get('skip_st_pool', True)
    if _skip_st:
        _warm_name_map(list(BLS['universe']) + (g.pool_static or []) + list((getattr(g, 'near_scan', None) or {}).keys()) + (g.watch or []))
    uni = [x for x in BLS['universe'] if x not in pos and not (_skip_st and _is_st(x))]
    static = [x for x in (g.pool_static or []) if x not in pos and x not in uni and not (_skip_st and _is_st(x))]
    ft = getattr(g, 'first_zt', None) or {}
    near_cap = int(BLS.get('tick_near_cap', 12))
    near = [x for x in (getattr(g, 'near_scan', None) or {})
            if x not in pos and x not in uni and x not in static and x not in ft and not (_skip_st and _is_st(x))][:near_cap]
    cap = int(BLS.get('tick_watch_cap', 15))
    watch = [x for x in (g.watch or []) if x not in pos and x not in uni and x not in static and x not in near and not (_skip_st and _is_st(x))][:cap]
    out = pos + uni + near + static + watch
    if BLS.get('tick_board_scan', True) and _min_age() <= int(BLS.get('first_board_minute', 10)):

        try:
            top3 = _board_rank_top3_set(_pool() or out)
            if top3:
                _cap_m = int(BLS.get('tick_board_member_cap', 10))
                for _b in top3:
                    for _m in _board_members_file(_b, _cap_m):
                        if _m and _m not in out and _m not in pos and not (_skip_st and _is_st(_m)):
                            out.append(_m)
        except Exception:
            pass
    try:
        g.tick_targets_cache = {'tok': tok, 'secs': out}
    except Exception:
        pass
    return out

def _snap_vol(s):
    for k in ('business_amount', 'volume', 'trd_volume', 'amount'):
        v = s.get(k)
        if v:
            try:
                return float(v)
            except Exception:
                return 0.0
    return 0.0

def _tick_seed_cands(_near):

    out = list(_near or [])
    ft = getattr(g, 'first_zt', None) or {}
    _skip_st = BLS.get('skip_st_pool', True)
    for s in (getattr(g, 'near_scan', None) or {}):
        if s not in ft and s not in out and not (_skip_st and _is_st(s)):
            out.append(s)
    return out

def _parse_tx_zt_ms(sec, rows, fields):

    if not rows or not isinstance(rows, list):
        return None
    def _idx(name, default):
        return fields.index(name) if name in fields else default
    i_t = _idx('business_time', 0); i_p = _idx('hq_px', 1)
    u = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
    if u <= 0:
        return None
    _td = str(get_trading_day()).replace('-', '')
    if len(_td) == 8 and _td.isdigit():
        day_open = int(_td + '093000000')
    else:
        lt = time.localtime()
        day_open = int('%04d%02d%02d093000000' % (lt.tm_year, lt.tm_mon, lt.tm_mday))
    best = None
    for row in rows:
        try:
            ms = int(row[i_t]); px = float(row[i_p])
            if ms < day_open or px < u - 1e-9:
                continue
            if best is None or ms < best:
                best = ms
        except Exception:
            continue
    return best

def _tx_dir(v):

    try:
        if v is None:
            return None
        sv = str(v).strip().lower()
        if sv in ('', 'none'):
            return None
        _m = BLS.get('l2_big_dir_map') or {}
        if sv in _m:
            _r = _m[sv]
            return _r if _r in ('buy', 'sell') else None
        if sv in ('b', 'buy', '买'):
            return 'buy'
        if sv in ('s', 'sell', '卖'):
            return 'sell'
    except Exception:
        pass
    return None

def _tx_big_feed(secs, fields, raw):

    if not BLS.get('l2_big_enabled', True) or not raw:
        return
    try:
        min_amt = float(BLS.get('l2_big_amt_min', 1000000.0))
    except Exception:
        return
    if min_amt <= 0:
        return
    def _idx(name, default):
        return fields.index(name) if name in fields else default
    i_a = _idx('business_amount', -1); i_t = _idx('trade_index', -1); i_p = _idx('hq_px', -1); i_d = _idx('business_direction', -1); i_bt = _idx('business_time', -1)
    if i_a < 0:
        return
    unit = str(BLS.get('l2_big_amt_unit', 'shares')).lower()
    mult = 100.0 if unit == 'lots' else 1.0
    yuan_mode = (unit == 'yuan')
    dir_on = BLS.get('l2_big_dir_enabled', True)
    acc = getattr(g, 'l2_big', None)
    if acc is None:
        acc = {}; g.l2_big = acc
    probed = getattr(g, 'l2_big_probed', None)
    if probed is None:
        probed = set(); g.l2_big_probed = probed
    wm = getattr(g, 'l2_big_wm', None)
    if wm is None:
        wm = {}; g.l2_big_wm = wm
    dist = getattr(g, 'l2_dir_dist', None)
    if dist is None:
        dist = {}; g.l2_dir_dist = dist
    _cap = int(BLS.get('l2_big_seen_cap', 20000))
    for sec in secs:
        rows = raw.get(sec) or []
        if not rows:
            continue
        a = acc.setdefault(sec, {'amt': 0.0, 'buy': 0.0, 'sell': 0.0, 'un': 0.0,
                                 'bn': 0, 'sn': 0, 'un_n': 0, 'seen': set(), 'max': 0.0, 'first_ts': None})
        seen = a['seen']
        if len(seen) >= _cap:
            continue
        for row in rows:
            try:
                if i_t >= 0:
                    ti = row[i_t]
                    if ti in seen:
                        continue
                    seen.add(ti)
                if i_bt >= 0:
                    _bt = int(row[i_bt])
                    if _bt <= wm.get(sec, 0):
                        continue
                va = float(row[i_a])
                if yuan_mode:
                    yuan = va
                else:
                    px = float(row[i_p]) if i_p >= 0 else 0.0
                    yuan = va * mult * px
                if yuan >= min_amt:
                    a['amt'] += yuan
                    if yuan > a.get('max', 0.0):
                        a['max'] = yuan
                    if i_bt >= 0 and _bt > wm.get(sec, 0):
                        wm[sec] = _bt
                    if dir_on and i_d >= 0:
                        _rk = str(row[i_d]).strip().lower()
                        dist[_rk] = dist.get(_rk, 0) + 1
                    if dir_on:
                        _d = _tx_dir(row[i_d]) if i_d >= 0 else None
                        if _d == 'buy':
                            a['buy'] += yuan
                            a['bn'] = a.get('bn', 0) + 1
                        elif _d == 'sell':
                            a['sell'] += yuan
                            a['sn'] = a.get('sn', 0) + 1
                        else:
                            a['un'] += yuan
                            a['un_n'] = a.get('un_n', 0) + 1
            except Exception:
                continue
        now = time.time()
        log_ts = getattr(g, 'l2_big_log_ts', None)
        if log_ts is None:
            log_ts = {}; g.l2_big_log_ts = log_ts
        first = sec not in probed

        if first or now - log_ts.get(sec, 0.0) >= float(BLS.get('l2_big_log_sec', 300)):
            probed.add(sec)
            log_ts[sec] = now
            r = _l2_big_ratio(sec)
            _to = _l2_big_turnover(sec)
            if dir_on:
                _dd = '{%s}' % ', '.join('%s:%d' % (k, dist[k]) for k in sorted(dist)) if dist else '{}'
                log.info('[l2-big] %s 大单买=%.0f(%d笔) 卖=%.0f(%d笔) 净=%.0f 占比=%.2f%% 分母=%.0f 未知=%.0f(%d笔) 最大单笔=%.0f元 全局分布=%s (阈值=%.0f unit=%s)' % (
                    _sn(sec), a.get('buy', 0.0), a.get('bn', 0), a.get('sell', 0.0), a.get('sn', 0),
                    a.get('buy', 0.0) - a.get('sell', 0.0), r * 100.0 if r >= 0 else -1.0, _to,
                    a.get('un', 0.0), a.get('un_n', 0), a.get('max', 0.0), _dd, min_amt, unit))

                if first and a.get('amt', 0.0) > 0 and a.get('buy', 0.0) <= 0 and a.get('sell', 0.0) <= 0:
                    w = getattr(g, 'l2_big_dir_warn', None)
                    if w is None:
                        w = set(); g.l2_big_dir_warn = w
                    if sec not in w:
                        w.add(sec)
                        log.info('[l2-big] %s 逐笔 direction 全部未识别(未知=%.0f) 净量口径待探针校准' % (_sn(sec), a.get('un', 0.0)))
            else:
                log.info('[l2-big] %s 累计大单=%.0f 占比=%.2f%% 分母=%.0f 最大单笔=%.0f元 (阈值=%.0f unit=%s)' % (
                    _sn(sec), a['amt'], r * 100.0 if r >= 0 else -1.0, _to, a.get('max', 0.0), min_amt, unit))

def _fmt_tick_ts(ms):

    try:
        ms = int(ms)
        return '%02d:%02d:%02d.%03d' % ((ms // 10000000) % 100, (ms // 100000) % 100, (ms // 1000) % 100, ms % 1000)
    except Exception:
        return str(ms)

def _l2_big_seed(secs, pages=None):

    if not BLS.get('l2_tickdir_enabled', True) or not secs:
        return
    try:
        min_amt = float(BLS.get('l2_big_amt_min', 1000000.0))
        if min_amt <= 0:
            return
        pages = int(pages or BLS.get('l2_tickdir_pages', 3))
        count = 200
        wm = getattr(g, 'l2_big_wm', None)
        if wm is None:
            wm = {}; g.l2_big_wm = wm
        acc = getattr(g, 'l2_big', None)
        if acc is None:
            acc = {}; g.l2_big = acc
        dist = getattr(g, 'l2_dir_dist', None)
        if dist is None:
            dist = {}; g.l2_dir_dist = dist
        seeded = getattr(g, 'l2_big_seeded', None)
        if seeded is None:
            seeded = set(); g.l2_big_seeded = seeded
        all_rows = {}
        flds = []
        try:
            for pg in range(max(1, pages)):
                raw = get_tick_direction(secs, start_pos=pg * count, search_direction=1, data_count=count, is_dict=True) or {}
                if pg == 0:
                    flds = raw.get('fields') or []
                for _sec in secs:
                    rws = raw.get(_sec) or []
                    if not rws:
                        continue
                    all_rows.setdefault(_sec, []).extend(rws)
        except Exception as e:
            log.info('[tickdir] pull fail %r' % e)
        for sec in secs:
            rows = all_rows.get(sec) or []
            if not rows:
                continue
            def _idx(name, default):
                return flds.index(name) if name in flds else default
            i_t = _idx('time_stamp', 0); i_b = _idx('business_balance', -1); i_d = _idx('business_direction', -1)
            if i_b < 0:
                log.info('[tickdir] %s fields 缺 business_balance 跳过' % _sn(sec)); continue
            a = acc.setdefault(sec, {'amt': 0.0, 'buy': 0.0, 'sell': 0.0, 'un': 0.0,
                                     'bn': 0, 'sn': 0, 'un_n': 0, 'seen': set(), 'max': 0.0, 'first_ts': None})
            w = wm.get(sec, 0); w_new = w; big = 0; first_ts = None; n = 0; seen_ts = set()
            for row in rows:
                try:
                    ts = int(row[i_t])
                except Exception:
                    continue
                n += 1
                if ts in seen_ts:
                    continue
                seen_ts.add(ts)
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if ts <= w:
                    continue
                if ts > w_new:
                    w_new = ts
                try:
                    bal = float(row[i_b])
                except Exception:
                    continue
                if bal < min_amt:
                    continue
                big += 1
                a['amt'] += bal
                if bal > a.get('max', 0.0):
                    a['max'] = bal
                if i_d >= 0:
                    _rk = str(row[i_d]).strip().lower()
                    dist[_rk] = dist.get(_rk, 0) + 1
                _d = _tx_dir(row[i_d]) if i_d >= 0 else None
                if _d == 'buy':
                    a['buy'] += bal
                    a['bn'] = a.get('bn', 0) + 1
                elif _d == 'sell':
                    a['sell'] += bal
                    a['sn'] = a.get('sn', 0) + 1
                else:
                    a['un'] += bal
                    a['un_n'] = a.get('un_n', 0) + 1
            a['first_ts'] = first_ts
            wm[sec] = w_new
            if sec not in seeded:
                seeded.add(sec)
                log.info('[tickdir] %s 首笔=%s 条数=%d 大单分笔=%d 水印=%s (阈值=%.0f)' % (
                    _sn(sec), _fmt_tick_ts(first_ts), n, big, _fmt_tick_ts(w_new), min_amt))
    except Exception as e:
        _warn('l2_big_seed fail %r' % e)

def _rebuild_first_zt_queue():

    cands = [x for x in dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])]
    pending = getattr(g, 'first_zt_rebuild_pending', None)
    if pending is None:
        pending = []; g.first_zt_rebuild_pending = pending
    ft = getattr(g, 'first_zt', None) or {}
    added = 0
    for sec in cands:
        if sec in ft or sec in pending or _is_st(sec):
            continue
        pending.append(sec)
        try:
            g.first_zt_rebuild_ts[sec] = time.time()
        except Exception:
            pass
        added += 1
    if added:
        log.info('[restart-rebuild] 登记待重建首触 %d 家（新增 %d）' % (len(pending), added))

def _rebuild_first_zt_tick():

    pending = getattr(g, 'first_zt_rebuild_pending', None)
    if not pending:
        return
    now = time.time()

    _max_att = max(1, int(BLS.get('first_zt_rebuild_max_attempts', 8) or 8))
    _attempts = getattr(g, 'first_zt_rebuild_attempts', None)
    if _attempts is None:
        _attempts = {}; g.first_zt_rebuild_attempts = _attempts
    _giveup = []
    for _sec in list(pending):
        if int(_attempts.get(_sec, 0) or 0) >= _max_att:
            _giveup.append(_sec)
    if _giveup:
        for _sec in _giveup:
            log.info('[restart-rebuild] 放弃(重试%d轮无涨停证据) %s' % (_max_att, _sn(_sec)))
        pending[:] = [x for x in pending if x not in set(_giveup)]
        if not pending:
            _restart_rebuild_heartbeat(now, done=len(_giveup), wait=0)
            return
    cap = int(BLS.get('first_zt_rebuild_cap', 5))
    retry = getattr(g, 'first_zt_rebuild_retry_ts', None)
    if retry is None:
        retry = {}; g.first_zt_rebuild_retry_ts = retry
    ft = getattr(g, 'first_zt', None)
    if ft is None:
        ft = {}; g.first_zt = ft
    retry_sec = float(BLS.get('first_zt_rebuild_retry_sec', 30.0))
    done = set()
    wait = set()
    got = []

    batch = []
    for sec in pending:
        if sec in ft:
            done.add(sec)
            continue
        if _is_st(sec):
            done.add(sec)
            continue
        if now - float(retry.get(sec, 0.0) or 0.0) < retry_sec:
            continue
        batch.append(sec)
        _attempts[sec] = int(_attempts.get(sec, 0) or 0) + 1
        if len(batch) >= cap:
            break
    if not batch:
        _restart_rebuild_heartbeat(now)
        return

    try:
        _need_snap = [sec for sec in batch if not float((g.spot.get(sec) or {}).get('up_px') or 0.0)]
        if _need_snap:
            _get_ds().snapshot(_need_snap)
    except Exception:
        pass
    need_tx = []
    for sec in batch:
        s = g.spot.get(sec) or {}
        u = float(s.get('up_px') or 0.0)
        if u <= 0:
            wait.add(sec)
            continue
        need_tx.append(sec)
    if need_tx:
        try:
            raw = get_individual_transaction(need_tx, data_count=int(BLS.get('first_zt_rebuild_tx_count', 200)), is_dict=True) or {}
            fields = raw.get('fields') or []
            for sec in need_tx:
                ms = _parse_tx_zt_ms(sec, raw.get(sec) or [], fields)
                src = 'restart_rebuild'
                if ms is None:
                    _s2 = g.spot.get(sec) or {}
                    _last = float(_s2.get('last_px') or 0.0)
                    _u2 = float(_s2.get('up_px') or 0.0)
                    h = _s2.get('hsTimeStamp') or 0

                    if h and _u2 > 0 and _last >= _u2 - 1e-9:
                        ms = int(h)
                        src = 'restart_rebuild_fallback'
                if ms is not None:
                    got.append((sec, ms, src))
                else:
                    wait.add(sec)
        except Exception as _e:
            _warn('restart-rebuild tx fail: %r' % _e)
            wait.update(need_tx)
    for sec, ms, src in got:
        if sec in ft:
            done.add(sec)
            continue
        s = g.spot.get(sec) or {}
        seal, bids = _seal_metrics(sec)
        vol = _snap_vol(s)
        amt = _l2_big_turnover(sec)
        ft[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': now,
                   'vol': vol, 'amt': amt, 'ms': ms, 'break': False, 'seal_low': False,
                   'src': src, 'day': str(get_trading_day())}
        done.add(sec)
        log.info('[restart-rebuild] %s 恢复首触 ms=%s seal=%.0f bids=%d src=%s' % (_sn(sec), ms, seal, bids, src))
    if wait:
        for sec in wait:
            retry[sec] = now
    if done:
        pending[:] = [x for x in pending if x not in done]
    _restart_rebuild_heartbeat(now, done=len(done), wait=len(wait))

def _restart_rebuild_heartbeat(now, done=0, wait=0):

    hb = float(getattr(g, 'restart_rebuild_hb_ts', 0.0) or 0.0)
    if now - hb < float(BLS.get('first_zt_rebuild_heartbeat_sec', 60.0)):
        return
    g.restart_rebuild_hb_ts = now
    pending = getattr(g, 'first_zt_rebuild_pending', None) or []
    _left = ','.join([_sn(x) for x in pending[:6]]) if pending else '-'
    log.info('[restart-rebuild] pending=%d done=%d wait=%d left=%s' % (len(pending), done, wait, _left))

def _log_l2_big_seed_summary(sec):

    try:
        a = (getattr(g, 'l2_big', {}) or {}).get(sec) or {}
        if not a.get('amt'):
            return
        r = _l2_big_ratio(sec)
        _to = _l2_big_turnover(sec)
        log.info('[l2-big-seed] %s 播种后 大单买=%.0f(%d笔) 卖=%.0f(%d笔) 净=%.0f 占比=%.2f%% 分母=%.0f' % (
            _sn(sec), a.get('buy', 0.0), a.get('bn', 0), a.get('sell', 0.0), a.get('sn', 0),
            a.get('buy', 0.0) - a.get('sell', 0.0), r * 100.0 if r >= 0 else -1.0, _to))
    except Exception:
        pass

def _l2_big_seed_onjoin(secs):

    if not BLS.get('l2_big_seed_onjoin_enabled', True):
        return
    secs = [s for s in (secs or []) if s]
    if not secs:
        return
    seeded = getattr(g, 'l2_big_seeded', None)
    if seeded is None:
        seeded = set(); g.l2_big_seeded = seeded
    todo = [s for s in secs if s not in seeded]
    if not todo:
        return
    now = time.time()
    px_ts = getattr(g, 'l2_big_seed_onjoin_px', None)
    if px_ts is None:
        px_ts = {}; g.l2_big_seed_onjoin_px = px_ts
    gap_px = float(BLS.get('l2_big_seed_onjoin_px_sec', 0))
    max_frame = int(BLS.get('l2_big_seed_onjoin_max_per_frame', 5))
    pages = int(BLS.get('l2_tickdir_pages_onjoin', 5))
    done = 0
    for s in todo:
        if done >= max_frame:
            break
        if now - float(px_ts.get(s, 0.0) or 0.0) < gap_px:
            continue
        px_ts[s] = now
        try:
            _l2_big_seed([s], pages=pages)
            done += 1
            if BLS.get('l2_big_seed_log', True):
                _log_l2_big_seed_summary(s)
        except Exception as e:
            _warn('l2_big_seed_onjoin %s fail %r' % (_sn(s), e))

def _l2_big_turnover(sec):

    try:
        s = g.spot.get(sec) or {}
        to = float(s.get('business_balance') or 0.0)
        if to > 0:
            return to
        vol = float(s.get('business_amount') or 0.0)
        px = float(s.get('wavg_px') or s.get('last_px') or 0.0)
        if vol > 0 and px > 0:
            return vol * px
        to = float(s.get('turnover') or s.get('amount') or 0.0)
        return to if to > 0 else 0.0
    except Exception:
        return 0.0

def _l2_big_day_summary(limit=30):

    try:
        acc = getattr(g, 'l2_big', None) or {}
        out = []
        for sec, a in acc.items():
            if not isinstance(a, dict) or not a.get('amt'):
                continue
            buy = float(a.get('buy') or 0.0)
            sell = float(a.get('sell') or 0.0)
            out.append((sec, buy, sell, buy - sell,
                        int(a.get('bn') or 0), int(a.get('sn') or 0), int(a.get('un_n') or 0)))
        out.sort(key=lambda x: x[3], reverse=True)
        return out[:int(limit)]
    except Exception:
        return []

def _l2_big_ratio(sec):

    try:
        acc = (getattr(g, 'l2_big', None) or {}).get(sec)
        if not acc:
            return -1.0
        if BLS.get('l2_big_dir_enabled', True):
            num = float(acc.get('buy') or 0.0) - float(acc.get('sell') or 0.0)
            if num <= 0:
                return -1.0
        else:
            num = float(acc.get('amt') or 0.0)
            if num <= 0:
                return -1.0
        to = _l2_big_turnover(sec)
        if to <= 0:
            return -1.0
        r = num / to
        if r > 1.0:
            return -1.0
        return r
    except Exception:
        return -1.0

def _l2_big_ok(sec):

    try:
        return _l2_big_ratio(sec) >= float(BLS.get('l2_big_ratio_min', 0.10))
    except Exception:
        return False

def _l2_big_bonus_pts(sec):

    try:
        return float(BLS.get('l2_big_bonus', 5.0)) if _l2_big_ok(sec) else 0.0
    except Exception:
        return 0.0

def _tx_frame_zt_ms(sec, frame_data):

    try:
        t = (frame_data or {}).get(sec) or {}
        tx = t.get('transaction') if isinstance(t, dict) else None
        if tx is None:
            return None
        u = float((g.spot.get(sec) or {}).get('up_px') or 0.0)
        if not u or u <= 0:
            return None
        best = None
        if hasattr(tx, 'iloc'):
            iloc = tx.iloc
            if isinstance(iloc, (list, tuple)):
                rows_iter = [(0, r) for r in iloc]
            elif hasattr(tx, 'iterrows'):
                rows_iter = tx.iterrows()
            else:
                rows_iter = [(0, tx)]
            for _, row in rows_iter:
                try:
                    ms = row.get('business_time'); px = float(row.get('hq_px'))
                except Exception:
                    continue
                if not ms:
                    continue
                ms = int(ms)
                if px >= u - 1e-9 and (best is None or ms < best):
                    best = ms
        elif isinstance(tx, dict):
            try:
                ms = int(tx.get('business_time')); px = float(tx.get('hq_px'))
            except Exception:
                return None
            if ms and px >= u - 1e-9:
                return ms
        return best
    except Exception:
        return None

def tick_data(context, data):

    if not BLS.get('tick_enabled', True):
        return
    _secs = _tick_targets()
    _dh = _get_ds()
    try:
        _dh.snapshot(_secs)
    except Exception:
        pass
    try:
        _rebuild_first_zt_tick()
    except Exception as _e:
        _warn('restart-rebuild fail: %r' % _e)

    _tx_map = {}
    if BLS.get('firsttx_enabled', True):
        _near = []
        _near_px = float(BLS.get('firsttx_near_px', 0.98))
        for _sec in _secs:
            _s0 = g.spot.get(_sec) or {}
            _l0 = float(_s0.get('last_px') or 0.0); _u0 = float(_s0.get('up_px') or 0.0)
            if (_l0 > 0 and _u0 > 0 and _l0 >= _u0 * _near_px
                    and not _is_one_word_open(_sec) and g.first_zt.get(_sec) is None):
                _near.append(_sec)
        if _near:
            try:
                _l2_big_seed_onjoin(_tick_seed_cands(_near))
            except Exception:
                pass
            try:
                _tx_map = _dh.tx_zt_batch(_near, data)
            except Exception:
                _tx_map = {}
    for sec in _secs:
        try:
            s = g.spot.get(sec) or {}
            g.spot[sec] = s
            last = float(s.get('last_px') or 0.0)
            u = float(s.get('up_px') or 0.0)
            if last <= 0 or u <= 0:
                continue
            seal, bids = _seal_metrics(sec)
            ft = g.first_zt.get(sec)
            if ft is None:
                vol = _snap_vol(s)
                amt = _l2_big_turnover(sec)
                ms = s.get('hsTimeStamp') or 0

                tx_ms = _tx_map.get(sec) if BLS.get('firsttx_enabled', True) else None
                if tx_ms is not None:
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': tx_ms, 'break': False, 'seal_low': False,
                                       'src': 'tx', 'day': str(get_trading_day())}
                    log.info('[firstzt] %s price=%.2f tx_ms=%s vol=%.0f seal=%.0f bids=%d state=first(src=tx)' % (_sn(sec), last, tx_ms, vol, seal, bids))
                    if BLS.get('l2_big_seed_on_firstzt', True) and sec not in (getattr(g, 'l2_big_seeded', None) or set()):
                        try:
                            _l2_big_seed([sec])
                            if BLS.get('l2_big_seed_log', True):
                                _log_l2_big_seed_summary(sec)
                        except Exception as _e:
                            _warn('l2_big_seed firstzt %r' % _e)
                    try:
                        _try_first_board_buy(context, sec, rank_secs=_near)
                    except Exception as _e:
                        _warn('first_board_buy fail %r' % _e)
                    continue
                if (last >= u - 1e-9 and seal >= float(BLS.get('firstzt_min_seal', 0.0))
                        and bids >= int(BLS.get('firstzt_min_bids', 0))):
                    g.first_zt[sec] = {'first_seal': seal, 'first_bids': bids, 'ts': time.time(),
                                       'vol': vol, 'amt': amt, 'ms': ms, 'break': False, 'seal_low': False,
                                       'src': 'snap', 'day': str(get_trading_day())}
                    log.info('[firstzt] %s price=%.2f vol=%.0f ms=%s seal=%.0f bids=%d state=first(src=snap)' % (_sn(sec), last, vol, ms, seal, bids))
                    if BLS.get('l2_big_seed_on_firstzt', True) and sec not in (getattr(g, 'l2_big_seeded', None) or set()):
                        try:
                            _l2_big_seed([sec])
                            if BLS.get('l2_big_seed_log', True):
                                _log_l2_big_seed_summary(sec)
                        except Exception as _e:
                            _warn('l2_big_seed firstzt %r' % _e)

                    try:
                        _try_first_board_buy(context, sec, rank_secs=_near)
                    except Exception as _e:
                        _warn('first_board_buy fail %r' % _e)
                continue
            if last < u - 1e-9:
                if not ft.get('break'):
                    ft['break'] = True; ft['break_ts'] = time.time()
                    ft['break_cnt'] = int(ft.get('break_cnt') or 0) + 1
                    log.info('[firstzt] %s price=%.2f -> BREAK#%d seal=%.0f held=%.0fs' % (_sn(sec), last, int(ft.get('break_cnt') or 0), seal, time.time() - ft.get('ts', time.time())))
                continue
            if ft.get('break') and last >= u - 1e-9 and seal >= float(BLS.get('firstzt_min_seal', 0.0)):
                ft['break'] = False
                if not ft.get('reboard_ts'):
                    ft['reboard_ts'] = time.time()
                log.info('[firstzt] %s 回封 reboard_ts=%.0f break_cnt=%d seal=%.0f' % (_sn(sec), float(ft.get('reboard_ts') or 0), int(ft.get('break_cnt') or 0), seal))
            fs = ft.get('first_seal') or 0.0
            _sfr = float(BLS.get('seal_fail_ratio', 0.333))
            if _unique_stand(sec):
                _sfr = float(BLS.get('seal_fail_ratio_unique', 0.25))
            if fs > 0 and seal < fs * _sfr:
                if not ft.get('seal_low'):
                    ft['seal_low'] = True
                    log.info('[firstzt] %s seal=%.0f first=%.0f ratio=%.2f bids=%d -> SEAL_LOW' % (_sn(sec), seal, fs, seal / fs, bids))
            try:
                _board_queue_cancel(sec, seal, bids)
            except Exception as _e:
                _warn('board queue cancel scan fail %r' % _e)
        except Exception:
            continue

    try:
        tick_sell_manager(context)
    except Exception as e:
        _warn('tick sell fail: %r' % e)

    try:
        _try_reboard_buy(context)
    except Exception as e:
        _warn('reboard buy fail: %r' % e)

    if BLS.get('tick_exp_enabled', True):
        try:
            _try_expected_buys(context)
        except Exception as e:
            _warn('tick exp buy fail: %r' % e)

    try:
        _try_elastic_arb_buy(context)
    except Exception as e:
        _warn('elastic_arb buy fail: %r' % e)

    try:
        _try_elastic_top_buy(context)
    except Exception as e:
        _warn('elastic_top buy fail: %r' % e)

    try:
        _try_dyn_unq(context)
    except Exception as e:
        _warn('dyn_unq fail: %r' % e)

    _budget_log()

def auction_pre_confirm(context):

    _set_now(context)
    day = str(get_trading_day())
    if getattr(g, 'exp_day', None) != day:
        g.exp_day = day
    _load_expectation(merge=True)
    _load_zt_lianban(merge=True)
    _load_boards()
    _synth_pool_expect()
    _dyn_unq_auction_eval()
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _synth_selfwatch_expect()
    _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
    _sync_pool_static()
    _mark_one_word_open()
    try:
        _l2_big_seed(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
    except Exception:
        pass
    for code in list(get_positions()):
        g.exp.setdefault(code, {})
        g.exp[code]['auction_status'] = _eval_auction(code)[0]
    for code in (g.exp_file or {}):
        if str((g.exp_file[code] or {}).get('side') or '') != 'buy':
            continue
        try:
            st, reason = _exp_rt_status(code)
        except Exception as e:
            _warn('auction_pre_confirm %s fail %r' % (_sn(code), e)); continue
        g.exp[code]['status'] = st
        if st == PM and str(reason).startswith('observe'):
            eo = g.exp.setdefault(code, {})
            if not eo.get('observe_seen'):
                eo['observe_seen'] = True
                log.info('[exp] %s 09:25竞价终态初步确认超预期 -> 观察(等分时确认) %s' % (_sn(code), reason))
        elif st == CS and str(reason).startswith('auction_not_met'):
            log.info('[exp] %s 09:25竞价终态未超预期 -> 放弃 %s' % (_sn(code), reason))
    try:
        _fill_zt_spot()
        _lb_senti_auction()
        _lb_senti_mid()
    except Exception as e:
        _warn('lb_senti auction eval fail: %r' % e)
    log.info('auction_pre_confirm 09:25 done exp_file=%d' % len(g.exp_file))

def after_open_probe(context):
    _set_now(context)
    log.info('after_open_probe 09:31')

    _load_expectation(merge=True)
    _synth_pool_expect()
    _dyn_unq_auction_eval()
    if BLS.get('selfwatch_enabled', True):
        _load_selfwatch()
    _synth_selfwatch_expect()
    _overwrite_auction_c(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
    _sync_pool_static()
    g.exp_day = str(get_trading_day()); g.seal_base = {}; g.seal_bid_base = {}; g.first_zt = {}; g.sealed_warn = set(); g.first_board_fired = set(); g.break_sold = set(); g.seal_sold = set(); g.break2_sold = set(); g.reboard_fired = False; g.sealed_since = {}; g.one_word_open = set(); g.one_word_marked_open = False; g.rt_stats = {}; g.l2_big = {}; g.l2_big_probed = set(); g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}; g.zt_new_cache = {}; g.zt_ferment_cache = {}; g.zt_ferment_stage = {}; g.zt_unmapped_n = 0; g.lb_senti = {}; g.lb_senti_cache = {}
    _mark_one_word_open()
    try:
        _l2_big_seed(list(dict.fromkeys([x for x in (_pool() + list(get_positions()) + list(g.exp_file or {})) if x])))
    except Exception:
        pass
    for sec in list(get_positions()):
        g.exp.setdefault(sec, {})
        au, _r = _eval_auction(sec)
        g.exp[sec]['auction_status'] = au
        _en = g.exp_file.get(sec) or {}
        for _k in ('entry_type', 'side', 'expected_status', 'expected_auction_change_pct', 'seal_amount_t0', 'sell_policy_hint'):
            if _en.get(_k) is not None:
                g.exp[sec][_k] = _en[_k]
    dump_scores(context)
    _l2_probe(context)
    try:
        _lb_senti_auction()
        _lb_senti_mid()
    except Exception as e:
        _warn('lb_senti after_open eval fail: %r' % e)

def mid_probe(context):
    _set_now(context)
    log.info('mid_probe 11:00')
    dump_scores(context)
    sell_manager(context)

def _round_price(x):

    try:
        return float(round(float(x), int(BLS.get('price_precision', 2))))
    except Exception:
        return float(x)

def _order_limit(sec, side, mode):

    s = g.spot.get(sec) or {}
    px = last_px(sec)
    up = float(s.get('up_px') or 0.0) if s else 0.0
    if not px or px <= 0:
        return None
    if side == 'sell':
        if mode == 'sell_urgent' and BLS.get('sell_urgent_floor', 1):
            floor = _limit_down_price(sec)
            if floor and floor > 0:
                return _round_price(floor)
        if mode == 'sell_break':
            try:
                gp = _gear(sec)
                _lv = int(BLS.get('break_sell_bid_level', 3))
                b = (gp.get('bid_grp') or {}).get(_lv) or []
                if isinstance(b, (list, tuple)) and len(b) >= 1 and float(b[0] or 0) > 0:
                    bid = float(b[0])
                    floor = px * float(BLS.get('break_sell_floor_ratio', 0.95))
                    if bid < floor:
                        bid = floor
                    return _round_price(bid)
            except Exception:
                pass
            return _round_price(px)
        return _round_price(px)
    if mode == 'board':
        if _sealed_at_limit(sec):
            return None
        return _round_price(up if up and up > 0 else px)
    if mode == 'pullback':
        return _round_price(px)
    p = px * (1 + float(BLS.get('buy_chase_pct', 0.008)))
    if up and up > 0 and p > up:
        p = up
    cap = _max_elastic_buy_price(sec)
    if cap and cap > 0 and p > cap:
        p = cap
    return _round_price(p)

def _total_asset(context):

    po = getattr(context, 'portfolio', None)
    if po is None:
        return 0.0
    try:
        t = getattr(po, 'total_value', 0) or 0
        if t:
            return float(t)
    except Exception:
        pass
    try:
        c = float(getattr(po, 'cash', 0) or 0)
    except Exception:
        c = 0.0
    try:
        mv = 0.0
        for p in (getattr(po, 'positions', None) or {}).values():
            amt = float(getattr(p, 'amount', 0) or 0)
            px = float(getattr(p, 'last_price', 0) or 0)
            mv += amt * px
        return c + mv
    except Exception:
        return c

def _sim_mode():

    try:
        if BLS.get('DO_ORDER', False) or BLS.get('EXPECT_ORDER', False):
            return False
        return float(BLS.get('sim_cash_base', 0.0) or 0.0) > 0
    except Exception:
        return False

def _size_cash(context):

    if _sim_mode():
        return float(BLS.get('sim_cash_base', 0.0) or 0.0)
    return _avail_cash(context)

def _size_total(context):

    if _sim_mode():
        return float(BLS.get('sim_cash_base', 0.0) or 0.0)
    return _total_asset(context)

def _calc_buy_qty(context, sec, price, ratio):

    if price is None or price <= 0:
        return 0
    try:
        cash = _size_cash(context)
    except Exception:
        return 0
    if cash <= 0:
        return 0
    total = _size_total(context) or cash
    p = (getattr(context.portfolio, 'positions', None) or {}).get(sec)
    held_mv = 0.0
    if p is not None:
        try:
            held_mv = float(getattr(p, 'amount', 0) or 0) * price
        except Exception:
            held_mv = 0.0
    cap = total * float(BLS.get('single_stock_cap', 0.30)) - held_mv
    if cap <= 0:
        return 0
    try:
        budget = min(cash * float(ratio), cap, cash)
    except Exception:
        return 0
    if budget <= 0:
        return 0
    lot = price * 100
    if lot <= 0:
        return 0
    return int(budget / lot) * 100

def _rt_lag_info(sec):

    try:
        now = time.time()
        ft = (getattr(g, 'first_zt', None) or {}).get(sec) or {}
        t = ft.get('ts')
        if not t:
            return '', None
        lag = max(now - float(t), 0.0)
        src = ft.get('src') or '-'
        ms = ft.get('ms') or '-'
        return ('lag=%.1fs det=%s:%s' % (lag, src, ms), lag)
    except Exception:
        return '', None

def _acc_rt(side, mode, lag):

    try:
        st = getattr(g, 'rt_stats', None)
        if not isinstance(st, dict):
            st = {}; g.rt_stats = st
        key = (str(side), str(mode))
        d = st.setdefault(key, {'n': 0, 'lag': 0.0, 'max': 0.0})
        d['n'] += 1; d['lag'] += lag; d['max'] = max(d['max'], lag)
    except Exception:
        pass

def _signal(sec, side, qty, limit, mode, note='', ent='', status=''):

    try:
        sc = 0.0
        try:
            sc = float(score_now(sec) or 0.0)
        except Exception:
            sc = 0.0
        _lag, _lv = _rt_lag_info(sec)
        if _lv is not None:
            _acc_rt(side, mode, _lv)
        log.info('[signal] %s side=%s qty=%s limit=%s mode=%s note=%s score=%.1f ent=%s status=%s %s' % (
            _sn(sec), side, qty, limit, mode, note, sc, ent, status, _lag))
    except Exception:
        pass

def _o_get(obj, *keys, default=None):

    for k in keys:
        try:
            if isinstance(obj, dict):
                if k in obj:
                    return obj[k]
            else:
                v = getattr(obj, k, None)
                if v is not None:
                    return v
        except Exception:
            continue
    return default

def _map_order_status(st):

    s = str(st or '').strip().upper()
    if s in ('FILLED', '8', 'V'):
        return 'FILLED'
    if s in ('CANCELLED', 'CANCELED', '5', '9'):
        return 'CANCELLED'
    if s in ('REJECTED', '6'):
        return 'REJECTED'
    if s in ('PARTIAL', '7', '4'):
        return 'PARTIAL'
    return 'SENT'

def _trade_side(bs):

    s = str(bs or '').strip().upper()
    if s in ('2', 'S', 'SELL', 'SALE'):
        return 'sell'
    if s in ('1', 'B', 'BUY'):
        return 'buy'
    return ''

def _avail_cash(context):

    try:
        cash = float(getattr(context.portfolio, 'cash', 0) or 0)
    except Exception:
        cash = 0.0
    try:
        cm = getattr(g, 'buy_commit', None)
        if isinstance(cm, dict) and cm:
            cash = max(0.0, cash - float(sum(cm.values()) or 0.0))
    except Exception:
        pass
    return cash

def _buy_commit_add(sec, qty, px):
    try:
        cm = getattr(g, 'buy_commit', None)
        if not isinstance(cm, dict):
            cm = {}; g.buy_commit = cm
        cm[sec] = float(cm.get(sec, 0.0) or 0.0) + max(0.0, float(qty or 0) * float(px or 0))
    except Exception:
        pass

def _buy_commit_rel(sec, qty, px):

    try:
        cm = getattr(g, 'buy_commit', None)
        if not isinstance(cm, dict) or sec not in cm:
            return
        _rel = max(0.0, float(qty or 0) * float(px or 0))
        if _rel <= 0:
            cm.pop(sec, None); return
        cm[sec] = max(0.0, float(cm.get(sec, 0.0) or 0.0) - _rel)
        if cm[sec] <= 0:
            cm.pop(sec, None)
    except Exception:
        pass

def _release_buy_slot(sec):

    try:
        _db = getattr(g, 'daily', None)
        if isinstance(_db, dict) and isinstance(_db.get('bought'), list) and sec in _db['bought']:
            _db['bought'].remove(sec)
        if isinstance(getattr(g, 'exp_fired', None), set):
            g.exp_fired.discard(sec)
        log.info('[buy-slot] %s 释放当日买入名额(REJECTED/CANCELLED)' % _sn(sec))
        _save_state()
    except Exception:
        pass

def _reconcile_pending():

    try:
        oo = get_open_orders() or []
    except Exception:
        oo = []
    if not isinstance(oo, (list, tuple)) or not oo:
        return 0
    try:
        ao = get_all_orders() or []
    except Exception:
        ao = []
    info = {}
    for _d in (ao or []):
        try:
            if isinstance(_d, dict) and str(_d.get('entrust_no') or ''):
                info[str(_d['entrust_no'])] = _d
        except Exception:
            continue
    pend = getattr(g, 'pending', None)
    if not isinstance(pend, dict):
        pend = {}; g.pending = pend
    n = 0
    now = time.time()
    for o in oo:
        try:
            _ent = str(_o_get(o, 'entrust_no') or '')
            _sym = str(_o_get(o, 'symbol') or _o_get(o, 'stock_code') or '')
            sec = _norm_sec(_sym) if _sym else ''
            if not _ent or not sec:
                continue
            _di = info.get(_ent) or {}
            _amt = int(float(_o_get(_di, 'amount', 'business_amount') or _o_get(o, 'amount') or 0) or 0)
            _fld = int(float(_o_get(_di, 'filled_amount') or _o_get(o, 'filled') or 0) or 0)
            _px = float(_o_get(_di, 'price') or _o_get(o, 'limit') or _o_get(o, 'price') or 0)
            _bs = str(_di.get('entrust_bs') or _o_get(o, 'side', 'entrust_bs') or '')
            _sd = _trade_side(_bs) or ('buy' if _bs else '')
            _st = _map_order_status(_o_get(_di, 'status') or _o_get(o, 'status'))
            if sec in pend and str(pend[sec].get('no') or '') == _ent:
                pend[sec]['status'] = _st
                if _st == 'FILLED':
                    pend[sec]['filled'] = _fld or int(pend[sec].get('qty') or 0)
                elif _st in ('CANCELLED', 'REJECTED'):
                    pend[sec]['filled'] = _fld
                continue
            if _sd not in ('buy', 'sell'):
                _sd = 'buy'
            _sb, _sbc = _seal_metrics(sec)
            pend[sec] = {'no': _ent, 'side': _sd, 'qty': _amt, 'limit': _px,
                         'status': _st if _st in ('CANCELLED', 'REJECTED', 'FILLED') else 'SENT',
                         'filled': _fld, 'ts': now, 'mode': 'board' if _sd == 'buy' else '',
                         'seal_base': _sb, 'seal_bid_base': _sbc}
            n += 1
        except Exception:
            continue
    if n:
        log.info('[pending-restore] 重启对账在途委托 %d 单' % n)
    return n

def _reconcile_daily_bought_slots():

    try:
        _db = getattr(g, 'daily', None)
        if not isinstance(_db, dict):
            return 0
        _bought = list(_db.get('bought') or [])
        if not _bought:
            return 0
        _pos = set()
        try:
            _p = get_positions() or {}
            for _k, _v in _p.items():
                _amt = 0
                try:
                    _amt = int(float((_v.get('amount') if isinstance(_v, dict) else getattr(_v, 'amount', 0) or 0) or 0) or 0)
                except Exception:
                    _amt = 0
                if _amt > 0:
                    _pos.add(_norm_sec(_k) or _k)
        except Exception:
            _pos = set()
        if not _pos:
            return 0
        _pend = getattr(g, 'pending', None) or {}
        _keep = []
        _rel = []
        for _c in _bought:
            _pp = _pend.get(_c) or {}
            _filled = int(_pp.get('filled') or 0)
            _filled_buy = (str(_pp.get('side') or '') == 'buy' and
                           (str(_pp.get('status') or '') == 'FILLED' or _filled > 0))
            if _c in _pos or _filled_buy:
                _keep.append(_c)
            else:
                _rel.append(_c)
        if not _rel:
            return 0
        _db['bought'] = _keep
        for _c in _rel:
            try:
                if isinstance(getattr(g, 'buy_commit', None), dict):
                    g.buy_commit.pop(_c, None)
                if isinstance(getattr(g, 'exp_fired', None), set):
                    g.exp_fired.discard(_c)
            except Exception:
                pass
        log.info('[buy-slot] 重启对账释放未成交占坑 %s (保留 %s)' % (_snl(_rel), _snl(_keep)))
        _save_state()
        return len(_rel)
    except Exception as e:
        _warn('buy-slot restart reconcile fail %r' % e)
        return 0

def place_order(context, sec, side, qty=None, note='', mode='chase', ratio=None):

    positions = context.portfolio.positions
    _lag, _lv = _rt_lag_info(sec)
    if side == 'buy':
        if _mid_board_avoid(sec):
            _skip_log('mid_avoid', sec, 'order', '[mid-avoid] %s 连板中位股规避(order)' % _sn(sec)); return False
        if BLS.get('skip_st_pool', True) and _is_st(sec):
            _skip_log('st_skip', sec, 'st', '[st-skip] %s ST股拦截(order)' % _sn(sec)); return False
        limit = _order_limit(sec, side, mode)
        px = limit or last_px(sec) or 0.0
        cash = _size_cash(context)
        if px <= 0 or cash <= 0:
            if cash <= 0:
                return False
            _skip_log('place_order', sec, 'no_px_cash', 'place_order skip(no px/cash) %s' % _sn(sec)); return False
        qty = _calc_buy_qty(context, sec, px, float(ratio) if ratio else float(BLS.get('ordinary_buy_ratio', 0.10)))
        if qty <= 0:
            if _sim_mode():
                qty = int(BLS.get('sim_min_lot', 100) or 100)
                log.info('[sim-min-lot] %s buy qty 0->%d (SIM 最小一手兜底)' % (_sn(sec), qty))
            else:
                _skip_log('place_order', sec, 'qty0', 'place_order skip(qty<=0) %s' % _sn(sec)); return False
        if not _buy_pos_ok(context, sec, qty, limit):
            return False
    else:
        limit = _order_limit(sec, side, mode)
        if qty is None:
            qty = int(getattr(positions.get(sec), 'amount', 0) or 0)
    if not qty or qty <= 0:
        _warn('place_order skip qty<=0 %s' % _sn(sec)); return False
    if not BLS['DO_ORDER']:
        log.info('[may-order] %s %s qty=%s limit=%s %s %s (DO_ORDER=False)' % (_sn(sec), side, qty, limit, note, _lag))
        _signal(sec, side, qty, limit, mode, note, ent='', status='SIM')
        return True
    try:
        amt = qty if side == 'buy' else -qty
        ent = order(sec, amt, limit_price=limit) if limit else order(sec, amt)
        _sb, _sbc = _seal_metrics(sec)
        g.pending[sec] = {'no': ent, 'side': side, 'qty': qty, 'limit': limit, 'status': 'SENT', 'filled': 0,
                          'ts': time.time(), 'mode': mode, 'seal_base': _sb, 'seal_bid_base': _sbc}
        if side == 'buy':
            _buy_commit_add(sec, qty, limit or px)
        log.info('order sent %s %s qty=%s amt=%s limit=%s ent=%s %s %s' % (_sn(sec), side, qty, amt, limit, ent, note, _lag))
        _signal(sec, side, qty, limit, mode, note, ent=ent, status='SENT')
        return True
    except Exception as e:
        log.error('order fail %s: %r' % (_sn(sec), e))
        return False

def place_expected_order(context, sec, note=''):
    _lag, _lv = _rt_lag_info(sec)

    if _mid_board_avoid(sec):
        _skip_log('mid_avoid', sec, 'exp_order', '[mid-avoid] %s 连板中位股规避(exp-order)' % _sn(sec)); return False
    if BLS.get('skip_st_pool', True) and _is_st(sec):
        _skip_log('st_skip', sec, 'st', '[st-skip] %s ST股拦截(exp-order)' % _sn(sec)); return False
    s = g.spot.get(sec) or {}
    px = last_px(sec) or 0.0
    up = float(s.get('up_px') or 0.0) if s else 0.0
    cash = _size_cash(context)
    if px <= 0 or cash <= 0:
        if cash <= 0:
            return False
        _skip_log('exp_order', sec, 'no_px_cash', 'exp order skip(no px/cash) %s' % _sn(sec))
        return False
    rd = _intraday_ready_detail(sec)
    if not rd:
        _skip_log('exp_order', sec, 'intraday_data_not_ready',
                  '[exp-order] %s intraday_data_not_ready(兜底) ready=%s %s' % (_sn(sec), rd, note))
        return False
    if _block_sealed_buy(sec):
        return False

    mode = 'board' if (up and px and px >= up * 0.998) else 'chase'
    limit = _order_limit(sec, 'buy', mode)
    p_for_size = limit or px
    ratio = float(BLS.get('board_buy_budget_ratio', BLS.get('exp_order_pct', 0.3))) if mode == 'board' else float(BLS.get('exp_order_pct', 0.3))
    qty = _calc_buy_qty(context, sec, p_for_size, ratio)
    if qty <= 0:
        if _sim_mode():
            qty = int(BLS.get('sim_min_lot', 100) or 100)
            log.info('[sim-min-lot] %s exp buy qty 0->%d (SIM 最小一手兜底)' % (_sn(sec), qty))
        else:
            _skip_log('exp_order', sec, 'qty0', 'exp order skip(qty<=0) %s' % _sn(sec)); return False
    if not _buy_pos_ok(context, sec, qty, limit):
        return False
    if BLS.get('EXPECT_ORDER', False):
        try:
            ent = order(sec, qty, limit_price=limit) if limit else order(sec, qty)
            _sb, _sbc = _seal_metrics(sec)
            g.pending[sec] = {'no': ent, 'side': 'buy', 'qty': qty, 'limit': limit, 'status': 'SENT', 'filled': 0,
                              'ts': time.time(), 'mode': mode, 'seal_base': _sb, 'seal_bid_base': _sbc}
            _buy_commit_add(sec, qty, limit or px)
            log.info('[exp-order] %s buy qty=%s limit=%s ent=%s ready=%s %s %s (EXPECT_ORDER=True)' % (_sn(sec), qty, limit, ent, rd, note, _lag))
            _signal(sec, 'BUY', qty, limit, mode, note, ent=ent, status='SENT')
            return True
        except Exception as e:
            log.error('exp order fail %s: %r' % (_sn(sec), e))
            return False
    log.info('[exp-order] %s buy qty=%s limit=%s ready=%s %s %s (EXPECT_ORDER=False)' % (_sn(sec), qty, limit, rd, note, _lag))
    _signal(sec, 'BUY', qty, limit, mode, note, ent='', status='SIM')
    return True

def on_order_response(context, order_list):

    try:
        items = order_list if isinstance(order_list, (list, tuple)) else [order_list]
        for _o in items:
            try:
                _ent = str(_o_get(_o, 'entrust_no', 'order_id') or '')
                _st_raw = _o_get(_o, 'order_status', 'status') or 'SENT'
                _st = _map_order_status(_st_raw)
                _sec_m = None; _p = {}
                if _ent:
                    for _sec, _pp in (getattr(g, 'pending', None) or {}).items():
                        if str(_pp.get('no') or '') == _ent:
                            _sec_m = _sec; _p = _pp
                            break
                if _sec_m is None:

                    _sec_r = _norm_sec(_o_get(_o, 'stock_code', 'ticker', 'code', 'sec', 'symbol') or '')
                    _pp2 = (getattr(g, 'pending', None) or {}).get(_sec_r) if _sec_r else None
                    if _pp2:
                        _sec_m = _sec_r; _p = _pp2
                        if _ent:
                            _p['no'] = _ent
                if _sec_m:
                    _p['status'] = _st
                    if _st == 'FILLED':
                        _p['filled'] = int(_p.get('qty') or 0)
                    elif _st in ('CANCELLED', 'REJECTED'):
                        _p['filled'] = int(_p.get('filled') or 0)
                log.info('on_order_response %s status=%s sec=%s pend_side=%s' % (
                    _ent, _st_raw, _sn(_sec_m) if _sec_m else '-', _p.get('side') or '-'))
                _signal(_sec_m, 'ORD', int(_p.get('qty') or 0), float(_p.get('limit') or 0.0), 'ord', 'order_response', ent=_ent, status=_st)
                if _sec_m and str(_p.get('side') or '') == 'buy' and _st in ('CANCELLED', 'REJECTED', 'FILLED'):
                    _buy_commit_rel(_sec_m, int(_p.get('qty') or 0), float(_p.get('limit') or 0.0))
                    if _st in ('CANCELLED', 'REJECTED'):
                        _release_buy_slot(_sec_m)
            except Exception:
                continue
    except Exception as e:
        _warn('on_order_response err %r' % e)

def on_trade_response(context, trade_list):

    try:
        items = trade_list if isinstance(trade_list, (list, tuple)) else [trade_list]
        for _t in items:
            try:
                code = _norm_sec(_o_get(_t, 'stock_code', 'ticker', 'code', 'sec', 'symbol') or '')
                if not code:
                    continue
                _rt = str(_o_get(_t, 'real_type') or '0')
                _ts = _map_order_status(_o_get(_t, 'status'))
                if _rt == '2' or _ts in ('CANCELLED', 'REJECTED'):
                    continue
                try:
                    _hold_exp_init(code)
                except Exception:
                    pass
                qty = abs(int(float(_o_get(_t, 'business_amount', 'quantity', 'volume', 'amount') or 0) or 0))
                side = str(_o_get(_t, 'entrust_bs', 'side', 'business_bs') or '')
                _side = _trade_side(side)
                p = (getattr(g, 'pending', None) or {}).get(code) or {}
                _ps = str(p.get('side') or '')

                _eff = _side if _side in ('buy', 'sell') else _ps
                if _side in ('buy', 'sell') and _ps in ('buy', 'sell') and _side != _ps:
                    _warn('side-conflict %s raw=%s pend=%s eff=%s' % (_sn(code), side, _ps, _eff))
                if _eff == 'sell':
                    p['filled'] = int(p.get('filled') or 0) + qty
                    p['last_trade_ts'] = time.time()
                    if p['filled'] >= int(p.get('qty') or p['filled']):
                        p['status'] = 'FILLED'
                    else:
                        p['status'] = 'PARTIAL'
                    if not isinstance(getattr(g, 'sold_log', None), dict):
                        g.sold_log = {}
                    g.sold_log[code] = time.time()
                    daily = g.daily.setdefault('sold', [])
                    if code not in daily:
                        daily.append(code)
                    _save_state()
                elif _eff == 'buy':
                    p['filled'] = int(p.get('filled') or 0) + qty
                    if p['filled'] >= int(p.get('qty') or p['filled']):
                        p['status'] = 'FILLED'
                    else:
                        p['status'] = 'PARTIAL'
                    _buy_commit_rel(code, qty, float(p.get('limit') or 0.0))
                log.info('on_trade_response %s qty=%s raw_side=%s pend_side=%s eff=%s' % (
                    _sn(code), qty, side, _ps, _eff))
                _signal(code, _eff or _ps or side, qty, 0, 'fill', 'trade_response', ent='', status=str(p.get('status') or 'TRADE'))
            except Exception:
                continue
    except Exception as e:
        _warn('on_trade_response err %r' % e)

def state_fp():
    return get_research_path() + 'buysell_core_state.pkl'

def load_state():
    try:
        with open(state_fp(), 'rb') as f:
            st = pickle.load(f)
        g.buy_log = st.get('buy_log', {}); g.sold_log = st.get('sold_log', {})
        g.daily = st.get('daily', {'bought': [], 'sold': []})
        g.exp_fired = set(st.get('exp_fired') or [])
        g.state_day = st.get('day')
        _today = str(get_trading_day())
        if st.get('day') == _today:

            _ac_day = str(st.get('ac_day') or '')
            _fz_day = str(st.get('first_zt_day') or '')
            if _ac_day == _today:
                g.auction_c = dict(st.get('auction_c') or {})
            else:
                g.auction_c = {}
                if st.get('auction_c'):
                    log.info('[restart-guard] auction_c 非当日残留(ac_day=%s) -> 清空' % _ac_day)
            if _fz_day == _today:
                _fz0 = dict(st.get('first_zt') or {})
                g.first_zt = {k: dict(v) for k, v in _fz0.items()
                              if str((v or {}).get('day') or '') == _today}
                if len(g.first_zt) != len(_fz0):
                    log.info('[restart-guard] first_zt 含跨日/无日期记录 %d 家 -> 丢弃(保留 %d)'
                             % (len(_fz0) - len(g.first_zt), len(g.first_zt)))
            else:
                g.first_zt = {}
                if st.get('first_zt'):
                    log.info('[restart-guard] first_zt 非当日残留(first_zt_day=%s) -> 清空重建' % _fz_day)
            g.break_sold = set(st.get('break_sold') or [])
            g.seal_sold = set(st.get('seal_sold') or [])
            g.break2_sold = set(st.get('break2_sold') or [])
            g.board_cancel_log = set(st.get('board_cancel_log') or [])
            g.reboard_fired = bool(st.get('reboard_fired'))
            g.l2_big = {k: dict(v, seen=set(v.get('seen') or [])) for k, v in (st.get('l2_big') or {}).items()}
            g.l2_dir_dist = dict(st.get('l2_dir_dist') or {})
            g.l2_big_wm = dict(st.get('l2_big_wm') or {})
            g.dyn_unq = st.get('dyn_unq')
            g.exp_day = st.get('exp_day')
            g.exp_file = dict(st.get('exp_file') or {})
            g.p7a_sold = set(st.get('p7a_sold') or [])
            g.p7b_sold = set(st.get('p7b_sold') or [])
            g.p7c_part = dict(st.get('p7c_part') or {})
            g.p7c_sold = set(st.get('p7c_sold') or [])
            g.pending = {k: dict(v) for k, v in (st.get('pending') or {}).items()}
            g.buy_commit = dict(st.get('buy_commit') or {})
            g.lb_senti = dict(st.get('lb_senti') or {})
            g.ma5_touch_day = st.get('ma5_touch_day')
            g.ma5_touched = set(st.get('ma5_touched') or [])
            g.ma5_lifecycle_day = st.get('ma5_lifecycle_day')
            g.ma5_lows = {k: list(v or [])[:2] for k, v in (st.get('ma5_lows') or {}).items()}
        else:
            g.auction_c = {}
            g.first_zt = {}
            g.break_sold = set()
            g.seal_sold = set()
            g.break2_sold = set()
            g.board_cancel_log = set()
            g.reboard_fired = False
            g.dyn_unq = None
            g.l2_big = {}; g.l2_dir_dist = {}; g.l2_big_wm = {}; g.l2_big_seeded = set(); g.l2_big_seed_onjoin_ts = 0.0; g.l2_big_seed_onjoin_px = {}; g.l2_big_log_ts = {}; g.below_vwap_pending = {}
            g.buy_commit = {}
            g.lb_senti = {}
            g.ma5_touch_day = None; g.ma5_touched = set()
            g.ma5_lifecycle_day = None; g.ma5_lows = {}
            g.exp_day = None
            g.exp_file = {}
    except Exception:
        g.buy_log = {}; g.sold_log = {}
        g.daily = {'bought': [], 'sold': []}; g.state_day = None
        g.exp_fired = set(); g.ma5_touch_day = None; g.ma5_touched = set()
        g.ma5_lifecycle_day = None; g.ma5_lows = {}
        g.auction_c = {}; g.first_zt = {}
        g.exp_file = {}

def _save_state():

    try:
        if not getattr(g, 'state_day', None):
            g.state_day = str(get_trading_day())
        _today = getattr(g, 'state_day', None) or str(get_trading_day())
        with open(state_fp(), 'wb') as f:
            pickle.dump({'buy_log': g.buy_log, 'sold_log': g.sold_log,
                         'daily': g.daily, 'day': _today,
                         'exp_fired': sorted(getattr(g, 'exp_fired', None) or []),
                         'auction_c': dict(getattr(g, 'auction_c', None) or {}),
                         'ac_day': _today,
                         'first_zt': dict(getattr(g, 'first_zt', None) or {}),
                         'first_zt_day': _today,
                         'break_sold': sorted(getattr(g, 'break_sold', None) or []),
                         'seal_sold': sorted(getattr(g, 'seal_sold', None) or []),
                         'break2_sold': sorted(getattr(g, 'break2_sold', None) or []),
                         'board_cancel_log': sorted(getattr(g, 'board_cancel_log', None) or []),
                         'reboard_fired': bool(getattr(g, 'reboard_fired', False)),
                         'dyn_unq': dict(getattr(g, 'dyn_unq', None) or {}),
                         'l2_big': dict(getattr(g, 'l2_big', None) or {}),
                         'l2_dir_dist': dict(getattr(g, 'l2_dir_dist', None) or {}),
                         'l2_big_wm': dict(getattr(g, 'l2_big_wm', None) or {}),
                         'exp_day': getattr(g, 'exp_day', None),
                         'exp_file': dict(getattr(g, 'exp_file', None) or {}),
                         'p7a_sold': sorted(getattr(g, 'p7a_sold', None) or []),
                         'p7b_sold': sorted(getattr(g, 'p7b_sold', None) or []),
                         'p7c_part': dict(getattr(g, 'p7c_part', None) or {}),
                         'p7c_sold': sorted(getattr(g, 'p7c_sold', None) or []),
                         'pending': {k: dict(v) for k, v in (getattr(g, 'pending', None) or {}).items()},
                         'buy_commit': dict(getattr(g, 'buy_commit', None) or {}),
                         'lb_senti': dict(getattr(g, 'lb_senti', None) or {}),
                         'ma5_touch_day': getattr(g, 'ma5_touch_day', None),
                         'ma5_touched': sorted(getattr(g, 'ma5_touched', None) or []),
                         'ma5_lifecycle_day': getattr(g, 'ma5_lifecycle_day', None),
                         'ma5_lows': dict(getattr(g, 'ma5_lows', None) or {})}, f, protocol=2)
    except Exception as e:
        _warn('save_state fail %r' % e)

def after_trading_end(context, data):
    _save_state()

    try:
        _st = getattr(g, 'rt_stats', None)
        if isinstance(_st, dict) and _st:
            for (_side, _mode), _d in sorted(_st.items()):
                if _d.get('n'):
                    log.info('[rt-summary] side=%s mode=%s n=%d avg=%.1fs max=%.1fs' % (_side, _mode, _d['n'], _d['lag'] / _d['n'], _d['max']))
            g.rt_stats = {}
    except Exception:
        pass
    try:
        _dd = getattr(g, 'l2_dir_dist', None)
        if isinstance(_dd, dict) and _dd:
            log.info('[l2-dir] 当日大单方向取值分布=%s' % ({k: v for k, v in sorted(_dd.items())},))
    except Exception:
        pass
    try:
        _rows = _l2_big_day_summary()
        if _rows:
            _parts = ['%s 买=%.0f/%d笔 卖=%.0f/%d笔 净=%.0f' % (
                _sn(sec), buy, bn, sell, sn, buy - sell) for sec, buy, sell, _n, bn, sn, _u in _rows]
            log.info('[l2-big-sum] 当日买入/卖出大单(买-卖=净, 元): %s' % ' | '.join(_parts))
    except Exception:
        pass
    log.info('buysell_core end bought=%s sold=%s' % (_snl(g.daily.get('bought')), _snl(g.daily.get('sold'))))
