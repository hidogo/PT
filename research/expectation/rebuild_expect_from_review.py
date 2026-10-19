# -*- coding: utf-8 -*-
import json, os
REV = r"D:\PROJ\AXquant\data\review\position_review_2026-10-16.jsonl"
OUT = r"D:\PROJ\PT\data\position_expectation_2026-10-19.jsonl"
NEXT = "2026-10-19"; REVIEW_TD = "2026-10-16"
role_fix = {"601811.SH": ("consecutive_limit_up", "consecutive_limit_up")}
def ln(x, fall=0.0):
    try: return float(x)
    except Exception: return fall
rows=[]
for line in open(REV, encoding="utf-8"):
    line=line.strip()
    if not line: continue
    r=json.loads(line)
    code=r.get("code") or ""
    kind=r.get("review_kind") or ""
    side="buy" if kind=="seedling" else "hold"
    st="pending_exceed" if side=="buy" else "pending_meet"
    auc=ln(r.get("auction_change_pct"))
    exp_auc=max(auc,3.0) if side=="buy" else auc
    role,role_detail=r.get("role") or "", r.get("role_detail") or ""
    if code in role_fix:
        role,role_detail=role_fix[code]
    te=r.get("t1_expectation") or {}
    rec={
      "trade_date": NEXT, "review_date": REVIEW_TD, "code": code,
      "name": r.get("name") or "", "review_kind": kind,
      "role": role, "role_detail": role_detail,
      "junk_follower": bool(r.get("junk_follower")), "sell_policy_hint": r.get("sell_policy_hint") or "",
      "entry_type": "normal", "side": side, "status": st,
      "auction_change_pct": round(auction_change_pct if False else exp_auc,4) if False else round(exp_auc,4),
      "yesterday_open_pct": ln(r.get("yesterday_open_pct")),
      "expected_auction_change_pct": round(exp_auc,4),
      "seal_amount_t0": ln(r.get("seal_amount_t0")),
      "board_name": r.get("board_name") or "", "limit_up_time": r.get("limit_up_time") or "",
      "strength": ln(r.get("strength")), "board_rank": r.get("board_rank"),
      "reasons": ["rebuilt_from_axquant_review"],
      "t1_expectation": {"primary": te.get("primary"), "secondary": te.get("secondary"),
                          "three_states": te.get("three_states"), "basis": te.get("basis") or ""},
      "source_agent": "pt_bridge_cli_rebuild", "updated_at": "2026-10-18",
    }
    rows.append(rec)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT,"w",encoding="utf-8") as f:
    for rec in rows:
        f.write(json.dumps(rec, ensure_ascii=False)+"\n")
print("written %s rows=%d" % (OUT, len(rows)))
for rec in rows:
    print(rec["code"], rec["name"], rec["side"], rec["status"], rec["expected_auction_change_pct"], rec["seal_amount_t0"], rec["board_name"], rec["role"])