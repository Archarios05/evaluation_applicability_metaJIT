# -*- coding: utf-8 -*-
# 計測回 (bench/results/runs/<ID>/) と PYPYLOG を管理・要約・比較するツール
#   python3 bench/logtool.py runs                      計測回の一覧
#   python3 bench/logtool.py show [RUN]                計測条件とログの一覧
#   python3 bench/logtool.py note RUN "メモ"           計測回にメモを付ける
#   python3 bench/logtool.py rm RUN                    計測回を削除する
#   python3 bench/logtool.py import DIR                旧形式 (results/ 直下に logs/ と raw.json) を取り込む
#   python3 bench/logtool.py traces LOG                ログ内のトレース一覧
#   python3 bench/logtool.py trace LOG N [--noopt]     トレース N の本文
#   python3 bench/logtool.py ops LOG [N]               op の種類別の数
#   python3 bench/logtool.py cmp EXAMPLE [--run RUN]   1 つの例題を実装間で比較
#   python3 bench/logtool.py diff RUN_A RUN_B          2 つの計測回の指標の差
#   python3 bench/logtool.py html [RUN ...]            HTML ビューアを書き出す
# RUN は ID・ID の一部・latest (既定)。LOG はファイルパスか [RUN/]実装-例題[.種類] (例: CEK-fib.noopt)
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import unicodedata

import analyze

BENCH = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(BENCH, "results")
RUNS = os.path.join(RESULTS, "runs")
TEMPLATE = os.path.join(BENCH, "logviewer.html")

LOGNAME = re.compile(r"^([^-]+)-(.+)\.([a-z]+\d*)\.log$")
HDR_LOOP = re.compile(r"^# Loop (\d+) \((.*)\) : (loop|entry bridge) with (\d+) ops$")
HDR_BRIDGE = re.compile(r"^# bridge out of Guard (0x[0-9a-f]+) with (\d+) ops$")
HDR_NOOPT = re.compile(r"^# Traced loop or bridge with (\d+) ops$")
OP = re.compile(r"^(?:\+\d+: )?(?:[a-z]\d+ = )?([a-z_][a-z_0-9]*)\(")
GUARD = re.compile(r"descr=<Guard(0x[0-9a-f]+)>")
TOKEN = re.compile(r"descr=TargetToken\((\d+)\)")
SUMMARY = re.compile(r"^(\s*[A-Za-z#: -]+):\s+([0-9.\s]+)$")
KIND_ORDER = {"full": 0, "noopt": 1}
CATS = [("guard", "ガード"), ("alloc", "確保"), ("mem", "メモリ"), ("call", "呼び出し"),
        ("arith", "演算"), ("control", "制御"), ("other", "その他")]
MEM_OPS = ("getfield", "setfield", "getarrayitem", "setarrayitem", "getinteriorfield",
           "setinteriorfield", "arraylen", "strlen", "strgetitem", "strsetitem", "unicode",
           "raw_load", "raw_store", "gc_load", "gc_store", "copystrcontent",
           "copyunicodecontent", "zero_array")
ARITH_OPS = ("int_", "uint_", "float_", "cast_", "ptr_", "instance_ptr_", "same_as",
             "nursery_ptr_increment")


# ---------------------------------------------------------------- 計測回

def run_ids():
    if not os.path.isdir(RUNS):
        return []
    return sorted(d for d in os.listdir(RUNS) if os.path.isfile(os.path.join(RUNS, d, "meta.json")))


def resolve_run(spec=None):
    ids = run_ids()
    if not ids:
        raise SystemExit("計測回がありません (%s)" % RUNS)
    if spec in (None, "", "latest"):
        return ids[-1]
    if spec in ids:
        return spec
    hit = [i for i in ids if spec in i]
    if len(hit) == 1:
        return hit[0]
    raise SystemExit("計測回 %r が%s: %s" % (spec, "曖昧です" if hit else "見つかりません",
                                          ", ".join(hit or ids)))


def run_dir(rid):
    return os.path.join(RUNS, rid)


def latest_run():
    return run_dir(resolve_run())


def new_run_id(tag=""):
    return time.strftime("%Y%m%d-%H%M") + ("-" + tag if tag else "")


def load_meta(rdir):
    with open(os.path.join(rdir, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def save_meta(rdir, meta):
    with open(os.path.join(rdir, "meta.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def log_files(rdir):
    # (実装, 例題, 種類, パス) を meta の実装・例題の順に並べる
    meta = load_meta(rdir)
    d = os.path.join(rdir, "logs")
    out = []
    for fn in os.listdir(d) if os.path.isdir(d) else []:
        m = LOGNAME.match(fn)
        if m:
            out.append((m.group(1), m.group(2), m.group(3), os.path.join(d, fn)))
    io = dict((x, i) for i, x in enumerate(meta.get("impls", [])))
    eo = dict((x, i) for i, x in enumerate(meta.get("examples", [])))
    return sorted(out, key=lambda t: (io.get(t[0], 99), t[0], eo.get(t[1], 99), t[1],
                                      KIND_ORDER.get(t[2], 2), t[2]))


def resolve_log(spec):
    if os.path.isfile(spec):
        return spec
    rid, _, name = spec.rpartition("/")
    d = os.path.join(run_dir(resolve_run(rid or None)), "logs")
    if name.endswith(".log"):
        cands = [name]
    elif LOGNAME.match(name + ".log"):
        cands = [name + ".log"]
    else:
        cands = [name + "." + k + ".log" for k in ("noopt", "full", "min0")]
    for c in cands:
        if os.path.isfile(os.path.join(d, c)):
            return os.path.join(d, c)
    raise SystemExit("ログが見つかりません: %s (%s)" % (spec, d))


def load_summary(rdir):
    p = os.path.join(rdir, "summary.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    if not os.path.isfile(os.path.join(rdir, "raw.json")):
        return None
    try:
        return analyze.analyze(rdir)
    except SystemExit as e:
        print("注意: analyze.py の集計に失敗しました (%s)" % e, file=sys.stderr)
        return None


def dir_size(d):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)


# ---------------------------------------------------------------- ログの解析

class Node:
    __slots__ = ("name", "start", "end", "children", "lines")

    def __init__(self, name, start):
        self.name, self.start, self.end = name, start, None
        self.children, self.lines = [], []

    def walk(self):
        for c in self.children:
            yield c
            for g in c.walk():
                yield g


def parse_sections(path):
    root = Node("", None)
    stack = [root]
    last = 0
    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = analyze.SEC.match(line)
            if m:
                last = int(m.group(1), 16)
                if m.group(2):
                    n = Node(m.group(3), last)
                    stack[-1].children.append(n)
                    stack.append(n)
                    continue
                if m.group(4) and len(stack) > 1 and stack[-1].name == m.group(3):
                    stack.pop().end = last
                    continue
            stack[-1].lines.append(line)
    # 途中で切れたログは最後の時刻で閉じる
    for n in stack[1:]:
        n.end = last
    return root.children


def category(op):
    if op.startswith("guard_"):
        return "guard"
    if op.startswith("new"):
        return "alloc"
    if op.startswith(MEM_OPS):
        return "mem"
    if op.startswith(("call", "cond_call")):
        return "call"
    if op in ("label", "jump", "finish"):
        return "control"
    if op.startswith(ARITH_OPS):
        return "arith"
    return "other"


def op_stats(lines):
    # 全体と label ごとの区間の (ops, guards, steps, op 別の数)。ops は debug_merge_point / label / jump を除く
    def seg(token, at):
        return {"token": token, "line": at, "ops": 0, "guards": 0, "steps": 0, "hist": {}}
    total = seg(None, 0)
    segs = [seg(None, 0)]
    for i, l in enumerate(lines):
        m = OP.match(l)
        if not m:
            continue
        op = m.group(1)
        if op == "label":
            t = TOKEN.search(l)
            segs.append(seg(t.group(1) if t else None, i))
            continue
        if op == "jump":
            continue
        for s in (total, segs[-1]):
            if op == "debug_merge_point":
                s["steps"] += 1
                continue
            s["ops"] += 1
            s["hist"][op] = s["hist"].get(op, 0) + 1
            if op.startswith("guard_"):
                s["guards"] += 1
    if len(segs) > 1 and not segs[0]["ops"] and not segs[0]["steps"]:
        segs.pop(0)
    return total, segs


def parse_counts(node):
    c = {"entry": {}, "token": {}, "bridge": {}}
    for l in node.lines:
        m = re.match(r"^(entry|bridge) (\d+):(\d+)$", l) or re.match(r"^TargetToken\((\d+)\):(\d+)$", l)
        if not m:
            continue
        if len(m.groups()) == 3:
            c[m.group(1)][m.group(2)] = int(m.group(3))
        else:
            c["token"][m.group(1)] = int(m.group(2))
    return c


def parse_log(path):
    top = parse_sections(path)
    fn = os.path.basename(path)
    m = LOGNAME.match(fn)
    log = {"name": fn[:-4], "path": path, "size": os.path.getsize(path),
           "impl": m.group(1) if m else None, "ex": m.group(2) if m else None,
           "kind": m.group(3) if m else None,
           "summary": {}, "counts": {"entry": {}, "token": {}, "bridge": {}},
           "sections": {}, "traces": [], "hot": None, "total": None}
    if not top:
        return log
    gc = [n.start for n in top if n.name == "gc-hardware"]
    t0 = min(gc) if gc else top[0].start
    sec = lambda ticks: ticks / analyze.TSC_HZ
    for n in top:
        s = log["sections"].setdefault(n.name, [0, 0.0])
        s[0] += 1
        s[1] += sec(n.end - n.start)
        if n.name == "jit-summary":
            log["total"] = sec(n.start - t0)
            for l in n.lines:
                mm = SUMMARY.match(l)
                if mm:
                    log["summary"][mm.group(1).strip()] = mm.group(2).split()
        elif n.name == "jit-backend-counts":
            log["counts"] = parse_counts(n)
    counts = log["counts"]
    owner = {}
    for n in top:
        if n.name != "jit-tracing":
            continue
        t = {"n": len(log["traces"]) + 1, "kind": None, "name": "", "loopno": None,
             "guard": None, "parent": None, "links": {},
             "start": sec(n.start - t0), "dur": sec(n.end - n.start),
             "path": [], "noopt": [], "opt": [], "abort": [],
             "noopt_ops": None, "hdr_ops": None, "iters": None, "entries": None,
             "ops": None, "guards": None, "steps": None, "hist": {}, "segs": []}
        for l in n.lines:
            if l.startswith("compiled new "):
                t["kind"] = l[len("compiled new "):]
            elif not l.startswith("JIT starting"):
                t["path"].append(l)
        for c in n.walk():
            if c.name.startswith("jit-log-noopt"):
                t["noopt"] = c.lines
            elif c.name in ("jit-log-opt-loop", "jit-log-opt-bridge"):
                t["opt"] = c.lines
            elif c.name == "jit-abort":
                t["kind"] = "abort"
                t["abort"] = c.lines
        if t["noopt"]:
            mm = HDR_NOOPT.match(t["noopt"][0])
            t["noopt_ops"] = int(mm.group(1)) if mm else None
        hdr = t["opt"][0] if t["opt"] else ""
        mm = HDR_LOOP.match(hdr)
        mb = HDR_BRIDGE.match(hdr)
        if mm:
            t["loopno"], t["name"], t["hdr_ops"] = int(mm.group(1)), mm.group(2), int(mm.group(4))
            t["kind"] = t["kind"] or mm.group(3)
            t["entries"] = counts["entry"].get(mm.group(1))
        elif mb:
            t["guard"], t["hdr_ops"] = mb.group(1), int(mb.group(2))
            t["name"] = "Guard " + mb.group(1)
            t["kind"] = t["kind"] or "bridge"
            t["iters"] = counts["bridge"].get(str(int(mb.group(1), 16)))
        if not t["name"] and t["path"]:
            t["name"] = t["path"][0]
        t["kind"] = t["kind"] or "?"
        lines = t["opt"] or t["noopt"]
        if lines:
            total, segs = op_stats(lines)
            t["ops"], t["guards"], t["steps"], t["hist"] = (total["ops"], total["guards"],
                                                            total["steps"], total["hist"])
            for s in segs:
                s["iters"] = counts["token"].get(s["token"]) if s["token"] else None
            t["segs"] = segs
            it = [s["iters"] for s in segs if s["iters"] is not None]
            if it:
                t["iters"] = max(it)
        for i, l in enumerate(t["opt"]):
            g = GUARD.search(l)
            if g:
                owner[g.group(1)] = (t, i)
        log["traces"].append(t)
    for t in log["traces"]:
        if t["guard"] in owner:
            p, i = owner[t["guard"]]
            t["parent"] = [p["n"], i]
            p["links"][str(i)] = t["n"]
    # 最も多く回った TargetToken の区間 (analyze.hot_loop と同じ選び方)
    best = None
    for t in log["traces"]:
        for j, s in enumerate(t["segs"]):
            if s["iters"] is not None and (best is None or s["iters"] > best[0]):
                best = (s["iters"], t["n"], j)
    if best:
        log["hot"] = [best[1], best[2]]
    return log


def cat_hist(hist):
    out = dict((c, 0) for c, _ in CATS)
    for op, k in hist.items():
        out[category(op)] += k
    return out


# ---------------------------------------------------------------- 指標 (summary.json から)

METRICS = [
    ("t_nojit", "nojit 時間 (s)", "%.3f"),
    ("t_jit", "jit 時間 (s)", "%.3f"),
    ("speedup", "速度向上比", "%.1f"),
    ("speedup_net", "速度向上比 (起動コスト除く)", "%.1f"),
    ("loops", "ループ数", "%d"),
    ("bridges", "ブリッジ数", "%d"),
    ("aborts", "abort 数", "%d"),
    ("rec_ops", "記録 ops (全トレース)", "%d"),
    ("opt_ops", "最適化後 ops (全トレース)", "%d"),
    ("rec_guards", "記録 guards (全トレース)", "%d"),
    ("opt_guards", "最適化後 guards (全トレース)", "%d"),
    ("hot_ops", "ホットループ ops/周", "%d"),
    ("hot_guards", "ホットループ guards/周", "%d"),
    ("hot_steps", "ホットループ steps/周", "%d"),
    ("hot_iters", "ホットループ周回数", "%d"),
    ("first_loop", "最初のループまで (s)", "%.4f"),
    ("last_compile", "最後のコンパイルまで (s)", "%.4f"),
    ("compile", "コンパイル合計 (s)", "%.4f"),
]


def metrics(s):
    # ({(実装, 例題): {指標: 値}}, 実装の並び, 例題の並び)。値が None は error か欠測
    T, J = s["time"], s["jit"]
    vals, impls, exs = {}, [], []
    for k, j in J.items():
        im, ex = k.split("/", 1)
        impls += [im] if im not in impls else []
        exs += [ex] if ex not in exs else []
        a, b = T.get("%s-nojit/%s" % (im, ex)), T.get("%s-jit/%s" % (im, ex))
        a0, b0 = T.get("%s-nojit/empty" % im), T.get("%s-jit/empty" % im)
        oa, ob = a is not None and analyze.ok(a), b is not None and analyze.ok(b)
        v = dict((key, None) for key, _, _ in METRICS)
        v["t_nojit"] = a["min"] if oa else None
        if ob:
            v["t_jit"] = b["min"]
            sv = lambda key: int(float(j["summary"][key][0])) if key in j["summary"] else None
            h, w = j.get("hot") or {}, j.get("warm") or {}
            v.update(loops=j["loops"], bridges=j["bridges"], aborts=j["aborts"],
                     rec_ops=sv("recorded ops"), opt_ops=sv("opt ops"),
                     rec_guards=sv("guards"), opt_guards=sv("opt guards"),
                     hot_ops=h.get("ops"), hot_guards=h.get("guards"),
                     hot_steps=h.get("steps"), hot_iters=h.get("iters"),
                     first_loop=w.get("first_loop"), last_compile=w.get("last_compile"),
                     compile=w.get("compile"))
        if oa and ob:
            v["speedup"] = a["min"] / b["min"]
            if a0 and b0:
                v["speedup_net"] = (a["min"] - a0["min"]) / (b["min"] - b0["min"])
        vals[(im, ex)] = v
    return vals, impls, exs


def fmt(v, f="%s"):
    if v is None:
        return "—"
    return f % v


# ---------------------------------------------------------------- 表示

def wcs(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def ptable(header, rows, right=()):
    rows = [["" if c is None else str(c) for c in r] for r in rows]
    ws = [max(wcs(r[i]) for r in [header] + rows) for i in range(len(header))]

    def line(r):
        cs = []
        for i, c in enumerate(r):
            pad = " " * (ws[i] - wcs(c))
            cs.append(pad + c if i in right else c + pad)
        return "  ".join(cs).rstrip()
    print(line(header))
    print("  ".join("-" * w for w in ws))
    for r in rows:
        print(line(r))


def human(n):
    for u in ("B", "K", "M", "G"):
        if n < 1024 or u == "G":
            return ("%d%s" if u == "B" else "%.1f%s") % (n, u)
        n /= 1024.0


def trace_counts(log):
    k = [t["kind"] for t in log["traces"]]
    return "%d/%d/%d/%d" % (k.count("loop"), k.count("bridge"), k.count("entry bridge"),
                            k.count("abort"))


def summary_pair(log, a, b):
    s = log["summary"]
    if a not in s or b not in s:
        return "—"
    return "%d → %d" % (int(float(s[a][0])), int(float(s[b][0])))


def same_result(a, b):
    key = lambda l: ([(t["kind"], t["path"]) for t in l["traces"]],
                     dict((k, v) for k, v in l["summary"].items()
                          if k not in ("Tracing", "Backend", "TOTAL")))
    return key(a) == key(b)


# ---------------------------------------------------------------- コマンド

def cmd_runs(a):
    rows = []
    for rid in run_ids():
        d = run_dir(rid)
        m = load_meta(d)
        rows.append([rid, m.get("date", ""), len(log_files(d)), ",".join(m.get("impls", [])),
                     ",".join(m.get("examples", [])), human(dir_size(d)), m.get("note", "")])
    if not rows:
        print("計測回がありません (%s)" % RUNS)
        return
    ptable(["ID", "日時", "ログ", "実装", "例題", "サイズ", "メモ"], rows, right=(2, 5))


def cmd_show(a):
    rid = resolve_run(a.run)
    d = run_dir(rid)
    m = load_meta(d)
    print("ID      : %s" % rid)
    for k in ("date", "note", "runs", "warm_runs", "cpu", "host"):
        if m.get(k) not in (None, ""):
            print("%-8s: %s" % (k, m[k]))
    for k, v in sorted((m.get("pypylog") or {}).items()):
        print("PYPYLOG : %-6s %s" % (k, v))
    for k, v in sorted((m.get("binaries") or {}).items()):
        print("binary  : %-12s %s" % (k, v[:16] if v else "—"))
    for k, v in sorted(m.items()):
        if k not in ("id", "date", "note", "runs", "warm_runs", "cpu", "host", "pypylog",
                     "binaries", "impls", "examples", "examples_sha256"):
            print("%-8s: %s" % (k, json.dumps(v, ensure_ascii=False)))
    print()
    logs = [parse_log(p) for _, _, _, p in log_files(d)]
    rows = []
    i = 0
    while i < len(logs):
        l = logs[i]
        grp = [l]
        if l["kind"].startswith("min"):
            while (i + len(grp) < len(logs) and logs[i + len(grp)]["kind"].startswith("min")
                   and logs[i + len(grp)]["impl"] == l["impl"] and logs[i + len(grp)]["ex"] == l["ex"]):
                grp.append(logs[i + len(grp)])
        kind = l["kind"]
        if len(grp) > 1:
            if all(same_result(l, g) for g in grp[1:]):
                kind = "%s-%s (同一)" % (l["kind"], grp[-1]["kind"][3:])
            else:
                grp = [l]
        hot = l["traces"][l["hot"][0] - 1]["segs"][l["hot"][1]] if l["hot"] else None
        rows.append([l["impl"], l["ex"], kind, trace_counts(l),
                     summary_pair(l, "recorded ops", "opt ops"),
                     summary_pair(l, "guards", "opt guards"),
                     "%d / %d" % (hot["ops"], hot["guards"]) if hot else "—",
                     fmt(hot and hot["iters"]), fmt(l["total"], "%.4f"), human(l["size"])])
        i += len(grp)
    ptable(["実装", "例題", "種類", "L/B/E/A", "ops 記録→最適化", "guards 記録→最適化",
            "ホット ops/guards", "ホット周回", "jit-summary (s)", "サイズ"],
           rows, right=(3, 4, 5, 6, 7, 8, 9))
    print("\nL/B/E/A = ループ / ブリッジ / entry bridge / abort。ホット = 最も多く回った label からの 1 周")


def cmd_note(a):
    rid = resolve_run(a.run)
    m = load_meta(run_dir(rid))
    m["note"] = a.text
    save_meta(run_dir(rid), m)
    print("%s: %s" % (rid, a.text))


def cmd_rm(a):
    rid = resolve_run(a.run)
    d = run_dir(rid)
    if not a.yes:
        ans = input("%s (%s, ログ %d 個) を削除しますか? [y/N] " % (rid, human(dir_size(d)),
                                                              len(log_files(d))))
        if ans.strip().lower() != "y":
            print("中止しました")
            return
    shutil.rmtree(d)
    print("削除しました: %s" % rid)


def cmd_import(a):
    src = os.path.abspath(a.dir)
    raw = os.path.join(src, "raw.json")
    if not os.path.isfile(raw) or not os.path.isdir(os.path.join(src, "logs")):
        raise SystemExit("%s に raw.json と logs/ がありません" % src)
    with open(raw) as f:
        r = json.load(f)
    rid = a.id or time.strftime("%Y%m%d-%H%M", time.strptime(r["date"], "%Y-%m-%d %H:%M"))
    d = run_dir(rid)
    if os.path.exists(d):
        raise SystemExit("既にあります: %s" % d)
    os.makedirs(d)
    moved = []
    for fn in ("logs", "raw.json", "summary.json", "tables.md"):
        if os.path.exists(os.path.join(src, fn)):
            (shutil.copytree if a.copy and fn == "logs" else shutil.copy2 if a.copy else shutil.move)(
                os.path.join(src, fn), os.path.join(d, fn))
            moved.append(fn)
    impls, exs = [], []
    for k in r["logs"]:
        im, ex = k.split("/", 1)
        impls += [im] if im not in impls else []
        exs += [ex] if ex not in exs else []
    # PYPYLOG の設定は残っていないので、ログに実際に出ているセクション名を種類ごとに記録する
    secs = {}
    for fn in sorted(os.listdir(os.path.join(d, "logs"))):
        m = LOGNAME.match(fn)
        if m:
            kind = "min" if m.group(3).startswith("min") else m.group(3)
            names = secs.setdefault(kind, set())
            for n in parse_sections(os.path.join(d, "logs", fn)):
                names.update([n.name] + [c.name for c in n.walk()])
    save_meta(d, {"id": rid, "date": r["date"], "note": a.note, "runs": r.get("runs"),
                  "warm_runs": len(next(iter(r["logs"].values()))["min"]),
                  "impls": impls, "examples": exs, "binaries": None,
                  "log_sections": dict((k, ",".join(sorted(v))) for k, v in secs.items()),
                  "imported": {"from": src, "at": time.strftime("%Y-%m-%d %H:%M")}})
    print("%s に%s: %s" % (rid, "コピー" if a.copy else "移動", ", ".join(moved)))


def cmd_traces(a):
    log = parse_log(resolve_log(a.log))
    print("%s  (%s, トレース %d 本, L/B/E/A=%s)" % (log["name"], human(log["size"]),
                                                  len(log["traces"]), trace_counts(log)))
    rows = []
    for t in log["traces"]:
        hot = log["hot"] and log["hot"][0] == t["n"]
        rows.append(["#%d%s" % (t["n"], "*" if hot else ""), t["kind"],
                     ("Loop %d (%s)" % (t["loopno"], t["name"])) if t["loopno"] else t["name"],
                     "%.2f" % (t["start"] * 1e3), "%.2f" % (t["dur"] * 1e3),
                     fmt(t["noopt_ops"]), fmt(t["ops"] if t["opt"] else None),
                     fmt(t["guards"] if t["opt"] else None), fmt(t["steps"]),
                     fmt(t["iters"]), fmt(t["entries"]),
                     "#%d %s" % (t["parent"][0], OP.match(log["traces"][t["parent"][0] - 1]["opt"][t["parent"][1]]).group(1))
                     if t["parent"] else ""])
    ptable(["#", "種類", "名前", "開始 ms", "時間 ms", "記録 ops", "最適化 ops", "guards",
            "steps", "周回数", "entry", "親ガード"], rows, right=(3, 4, 5, 6, 7, 8, 9, 10))
    print("\n* = 最も多く回った label を含むトレース。ops は debug_merge_point / label / jump を除いた数。"
          "steps は debug_merge_point の数")


def cmd_trace(a):
    log = parse_log(resolve_log(a.log))
    if not 1 <= a.n <= len(log["traces"]):
        raise SystemExit("トレースは #1 から #%d まで" % len(log["traces"]))
    t = log["traces"][a.n - 1]
    print("# %s #%d  %s  %s" % (log["name"], t["n"], t["kind"], t["name"]))
    if t["parent"]:
        print("# 親: #%d の %d 行目のガード" % tuple(t["parent"]))
    for s in t["segs"]:
        print("# 区間 %s: ops %d, guards %d, steps %d, 周回数 %s" % (
            ("TargetToken(%s)" % s["token"]) if s["token"] else "(label 前)",
            s["ops"], s["guards"], s["steps"], fmt(s["iters"])))
    if a.path:
        print("\n".join(t["path"]))
        return
    lines = t["noopt"] if a.noopt else (t["opt"] or t["noopt"])
    if not lines:
        print("# このログにはトレース本文がありません (経路は --path で表示)")
        return
    links = {} if a.noopt else t["links"]
    for i, l in enumerate(lines):
        if a.no_dmp and l.startswith("debug_merge_point"):
            continue
        if str(i) in links:
            b = log["traces"][links[str(i)] - 1]
            l += "    # -> #%d (%s 回)" % (b["n"], fmt(b["iters"]))
        print(l)


def cmd_ops(a):
    log = parse_log(resolve_log(a.log))
    ts = [log["traces"][a.n - 1]] if a.n else log["traces"]
    hist = {}
    for t in ts:
        src = op_stats(t["noopt"])[0]["hist"] if a.noopt else t["hist"]
        for op, k in src.items():
            hist[op] = hist.get(op, 0) + k
    total = sum(hist.values()) or 1
    ptable(["op", "分類", "数", "%"],
           [[op, dict(CATS)[category(op)], k, "%.1f" % (100.0 * k / total)]
            for op, k in sorted(hist.items(), key=lambda kv: -kv[1])], right=(2, 3))
    print()
    ch = cat_hist(hist)
    ptable(["分類", "数", "%"], [[lab, ch[c], "%.1f" % (100.0 * ch[c] / total)] for c, lab in CATS],
           right=(1, 2))


def cmd_cmp(a):
    rid = resolve_run(a.run)
    d = run_dir(rid)
    s = load_summary(d)
    if not s:
        raise SystemExit("%s には summary.json がなく、raw.json からも集計できません" % rid)
    vals, impls, exs = metrics(s)
    if a.example not in exs:
        raise SystemExit("例題は %s のどれか" % ", ".join(exs))
    print("%s / %s\n" % (rid, a.example))
    ptable(["指標"] + impls, [[lab] + [fmt(vals[(im, a.example)][k], f) for im in impls]
                              for k, lab, f in METRICS], right=range(1, len(impls) + 1))
    # ホットループの op 内訳 (指定した種類のログから)
    hots = {}
    for im, ex, kind, p in log_files(d):
        if ex == a.example and kind == a.kind:
            l = parse_log(p)
            if l["hot"]:
                hots[im] = cat_hist(l["traces"][l["hot"][0] - 1]["segs"][l["hot"][1]]["hist"])
    if hots:
        print("\nホットループ 1 周の op 内訳 (%s ログ)\n" % a.kind)
        ptable(["分類"] + impls, [[lab] + [fmt(hots[im][c]) if im in hots else "—" for im in impls]
                                  for c, lab in CATS], right=range(1, len(impls) + 1))


def cmd_diff(a):
    ra, rb = resolve_run(a.a), resolve_run(a.b)
    sa, sb = load_summary(run_dir(ra)), load_summary(run_dir(rb))
    if not sa or not sb:
        raise SystemExit("summary.json がない計測回があります")
    (va, ia, ea), (vb, ib, eb) = metrics(sa), metrics(sb)
    rows = []
    for im in ia + [x for x in ib if x not in ia]:
        for ex in ea + [x for x in eb if x not in ea]:
            if a.example and ex != a.example:
                continue
            x, y = va.get((im, ex)), vb.get((im, ex))
            for k, lab, f in METRICS:
                p, q = x and x[k], y and y[k]
                if p is None and q is None:
                    continue
                r = q / p if p and q is not None else None
                if not a.all and p == q:
                    continue
                if r is not None and abs(r - 1) < a.threshold:
                    continue
                rows.append([im, ex, lab, fmt(p, f), fmt(q, f), fmt(r, "×%.3f")])
    print("A = %s, B = %s\n" % (ra, rb))
    if rows:
        ptable(["実装", "例題", "指標", "A", "B", "B/A"], rows, right=(3, 4, 5))
    else:
        print("差はありません")


def build_data(rids):
    runs = []
    for rid in rids:
        d = run_dir(rid)
        s = load_summary(d)
        mt = None
        if s:
            vals, impls, exs = metrics(s)
            mt = {"impls": impls, "examples": exs,
                  "values": dict(("%s/%s" % k, v) for k, v in vals.items())}
        logs = []
        for _, _, _, p in log_files(d):
            l = parse_log(p)
            del l["path"]
            for t in l["traces"]:
                for sg in t["segs"]:
                    sg["cats"] = cat_hist(sg.pop("hist"))
            logs.append(l)
        runs.append({"id": rid, "meta": load_meta(d), "metrics": mt, "logs": logs})
    return {"generated": time.strftime("%Y-%m-%d %H:%M"), "runs": runs,
            "metric_defs": [{"key": k, "label": lab, "fmt": f} for k, lab, f in METRICS],
            "cats": [{"key": c, "label": lab} for c, lab in CATS]}


def cmd_html(a):
    rids = [resolve_run(r) for r in a.runs] if a.runs else [resolve_run()]
    if a.all:
        rids = run_ids()
    out = a.out or (os.path.join(run_dir(rids[0]), "viewer.html") if len(rids) == 1
                    else os.path.join(RESULTS, "viewer.html"))
    data = json.dumps(build_data(rids), ensure_ascii=False, separators=(",", ":"))
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    page = page.replace("/*__DATA__*/null", data.replace("</", "<\\/"))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("%s (%s, 計測回 %d)" % (out, human(os.path.getsize(out)), len(rids)))


def main():
    ap = argparse.ArgumentParser(description="計測回と PYPYLOG の管理")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("runs", help="計測回の一覧").set_defaults(fn=cmd_runs)
    p = sp.add_parser("show", help="計測条件とログの一覧")
    p.add_argument("run", nargs="?")
    p.set_defaults(fn=cmd_show)
    p = sp.add_parser("note", help="メモを付ける")
    p.add_argument("run")
    p.add_argument("text")
    p.set_defaults(fn=cmd_note)
    p = sp.add_parser("rm", help="計測回を削除")
    p.add_argument("run")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(fn=cmd_rm)
    p = sp.add_parser("import", help="旧形式の結果ディレクトリを取り込む (既定は移動)")
    p.add_argument("dir")
    p.add_argument("--id")
    p.add_argument("--note", default="")
    p.add_argument("--copy", action="store_true", help="移動せずにコピーする")
    p.set_defaults(fn=cmd_import)
    p = sp.add_parser("traces", help="トレース一覧")
    p.add_argument("log")
    p.set_defaults(fn=cmd_traces)
    p = sp.add_parser("trace", help="トレース本文")
    p.add_argument("log")
    p.add_argument("n", type=int)
    p.add_argument("--noopt", action="store_true", help="最適化前を表示")
    p.add_argument("--path", action="store_true", help="トレースした経路 (jit-tracing の本文) を表示")
    p.add_argument("--no-dmp", action="store_true", help="debug_merge_point を省く")
    p.set_defaults(fn=cmd_trace)
    p = sp.add_parser("ops", help="op の種類別の数")
    p.add_argument("log")
    p.add_argument("n", type=int, nargs="?")
    p.add_argument("--noopt", action="store_true")
    p.set_defaults(fn=cmd_ops)
    p = sp.add_parser("cmp", help="例題 1 つを実装間で比較")
    p.add_argument("example")
    p.add_argument("--run")
    p.add_argument("--kind", default="full", help="ホットループの内訳を取るログの種類 (既定 full)")
    p.set_defaults(fn=cmd_cmp)
    p = sp.add_parser("diff", help="2 つの計測回の指標の差")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--example")
    p.add_argument("--all", action="store_true", help="同じ値の指標も表示")
    p.add_argument("--threshold", type=float, default=0.0, help="|B/A - 1| がこれ未満の行を省く")
    p.set_defaults(fn=cmd_diff)
    p = sp.add_parser("html", help="HTML ビューアを書き出す")
    p.add_argument("runs", nargs="*")
    p.add_argument("--all", action="store_true", help="全計測回を入れる")
    p.add_argument("-o", "--out")
    p.set_defaults(fn=cmd_html)
    a = ap.parse_args()
    # Windows でパイプに出すと cp932 になり、表せない文字で落ちるのを防ぐ
    sys.stdout.reconfigure(errors="replace")
    a.fn(a)


if __name__ == "__main__":
    main()
