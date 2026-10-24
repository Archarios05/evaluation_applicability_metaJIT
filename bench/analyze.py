# -*- coding: utf-8 -*-
# run_bench.py の結果 (results/raw.json と logs/) から指標ごとの表を作る
#   python3 bench/analyze.py [計測回 ID か結果ディレクトリ]  (既定は最新の計測回)
import json
import os
import re
import statistics
import sys

TSC_HZ = 1996.198e6
IMPLS = ["CEK", "CPS", "3imp"]
EXAMPLES = ["countdown", "let-loop", "fib", "sum"]
LABELS = {
    "countdown": "`countdown`（末尾再帰 10^7 回）",
    "let-loop": "`let-loop`（letrec + 関数位置の lambda, 10^7 回）",
    "fib": "`fib`（fib 30）",
    "sum": "`sum`（非末尾再帰 10^6 段）",
}
SEC = re.compile(r"^\[([0-9a-f]+)\] (\{)?([a-z0-9-]+)(\})?$")


def sections(path):
    # トップレベルの区間 (名前, 開始, 終了, 内側の区間名の集合) と本文行
    top, stack, body = [], [], []
    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = SEC.match(line)
            if not m:
                if stack:
                    body.append((len(top), stack[-1][0], line))
                continue
            ts, opening, name = int(m.group(1), 16), m.group(2), m.group(3)
            if opening:
                stack.append([name, ts, set()])
            else:
                n, start, inner = stack.pop()
                if stack:
                    stack[-1][2].add(n)
                    stack[-1][2].update(inner)
                else:
                    top.append((n, start, ts, inner))
    return top, body


def summary(top_body):
    vals = {}
    for _, sec, line in top_body:
        if sec != "jit-summary":
            continue
        m = re.match(r"^(\s*[A-Za-z#: -]+):\s+([0-9.\s]+)$", line)
        if m:
            vals[m.group(1).strip()] = m.group(2).split()
    return vals


def kind(inner):
    if "jit-log-opt-loop" in inner:
        return "loop"
    if "jit-log-opt-bridge" in inner:
        return "bridge"
    if "jit-abort" in inner:
        return "abort"
    return "other"


def hot_loop(path):
    # jit-backend-counts で最も多く回った TargetToken の label から次の label/jump まで
    counts = {}
    loops = []
    cur = None
    in_counts = False
    with open(path, errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = SEC.match(line)
            if m:
                name = m.group(3)
                if name == "jit-backend-counts":
                    in_counts = bool(m.group(2))
                if name == "jit-log-opt-loop":
                    if m.group(2):
                        cur = []
                    else:
                        loops.append(cur)
                        cur = None
                continue
            if in_counts:
                mm = re.match(r"^TargetToken\((\d+)\):(\d+)$", line)
                if mm:
                    counts[mm.group(1)] = int(mm.group(2))
            elif cur is not None:
                cur.append(line)
    if not counts:
        return None
    tok, iters = max(counts.items(), key=lambda kv: kv[1])
    for lines in loops:
        for i, l in enumerate(lines):
            if "label(" in l and "TargetToken(%s)" % tok in l:
                ops = guards = steps = 0
                for l2 in lines[i + 1:]:
                    if l2.startswith("debug_merge_point"):
                        steps += 1
                        continue
                    mm = re.match(r"^\+\d+: (?:\w+ = )?(\w+)\(", l2)
                    if not mm:
                        continue
                    op = mm.group(1)
                    if op in ("label", "jump"):
                        break
                    ops += 1
                    if op.startswith("guard_"):
                        guards += 1
                return {"iters": iters, "ops": ops, "guards": guards, "steps": steps}
    return None


def analyze(rdir):
    raw = json.load(open(os.path.join(rdir, "raw.json")))
    local = lambda p: os.path.join(rdir, "logs", os.path.basename(p))
    out = {"date": raw["date"], "runs": raw["runs"], "time": {}, "jit": {},
           "warm_runs": len(next(iter(raw["logs"].values()))["min"])}
    for k, v in raw["times"].items():
        out["time"][k] = {"min": min(v["times"]), "median": statistics.median(v["times"]),
                          "output": v["output"], "rc": v["rc"]}
    for k, v in raw["logs"].items():
        ftop, _ = sections(local(v["full"]))
        kinds = [kind(inner) for n, _, _, inner in ftop if n == "jit-tracing"]
        warm, sums = [], []
        for m in v["min"]:
            top, body = sections(local(m["path"]))
            sums.append(summary(body))
            start = min(t[1] for t in top if t[0] == "gc-hardware")
            end = [t[1] for t in top if t[0] == "jit-summary"][0]
            tr = [t for t in top if t[0] == "jit-tracing"]
            # abort が無ければ最初のトレースは必ずループ
            loop_ends = [tr[0][2]] if tr else []
            warm.append({
                "first_loop": (loop_ends[0] - start) / TSC_HZ if loop_ends else None,
                "last_compile": (tr[-1][2] - start) / TSC_HZ if tr else None,
                "compile": sum(t[2] - t[1] for t in tr) / TSC_HZ,
                "total": (end - start) / TSC_HZ,
                "wall": m["wall"],
            })
        med = lambda key: (statistics.median([w[key] for w in warm])
                           if all(w[key] is not None for w in warm) else None)
        s = sums[0]
        counts = lambda x: dict((a, b) for a, b in x.items() if a not in ("Tracing", "Backend", "TOTAL"))
        if any(counts(x) != counts(s) for x in sums):
            raise SystemExit("jit-summary differs between runs: %s" % k)
        aborts = sum(int(v2[0]) for k2, v2 in s.items() if k2.startswith("abort"))
        if aborts:
            raise SystemExit("aborts present, first trace may not be a loop: %s" % k)
        out["jit"][k] = {
            "loops": int(s["Total # of loops"][0]), "bridges": int(s["Total # of bridges"][0]),
            "aborts": aborts, "full_traces": len(kinds), "min_traces": int(s["Tracing"][0]),
            "summary": s, "hot": hot_loop(local(v["full"])),
            "warm": {key: med(key) for key in
                     ("first_loop", "last_compile", "compile", "total", "wall")},
        }
    return out


def f(x, fmt="%.3f"):
    return "—" if x is None else fmt % x


def ok(r):
    return r["rc"] == 0 and r["output"] != "error"


def tables(d):
    T, J = d["time"], d["jit"]
    L = []
    L.append("# 計測結果\n")
    L.append("- 計測日時: %s / WSL2 Ubuntu (AMD Ryzen 7 7730U), `taskset -c 2` で 1 コアに固定" % d["date"])
    L.append("- 時間は各 %d 回実行の最小値 (秒)。プロセス起動から終了までの壁時計時間" % d["runs"])
    L.append("- バイナリは WSL のネイティブ FS (`~/metajit_bench`) にコピーして実行")
    L.append("- `error` は実装がエラーを出力して終了したもの (CPS 版 `sum` は C スタック溢れ)\n")

    L.append("## 1. 実行時間と JIT による速度向上比\n")
    L.append("### 1-a. 実行時間 (秒, 最小値)\n")
    L.append("| 例題 | CEK-nojit | CEK-jit | CPS-nojit | CPS-jit | 3imp-nojit | 3imp-jit |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for ex in EXAMPLES + ["empty"]:
        row = [LABELS.get(ex, "`(display 0)`（起動コスト）")]
        for im in IMPLS:
            for mo in ("nojit", "jit"):
                r = T["%s-%s/%s" % (im, mo, ex)]
                row.append(f(r["min"]) if ok(r) else "error")
        L.append("| " + " | ".join(row) + " |")
    L.append("\n### 1-b. 速度向上比 (nojit ÷ jit)\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        row = [LABELS[ex]]
        for im in IMPLS:
            a, b = T["%s-nojit/%s" % (im, ex)], T["%s-jit/%s" % (im, ex)]
            row.append("%.1f 倍" % (a["min"] / b["min"]) if ok(a) and ok(b) else "error")
        L.append("| " + " | ".join(row) + " |")
    L.append("\n### 1-c. 速度向上比 (起動コストを差し引いた場合)\n")
    L.append("`(display 0)` の時間を各バイナリの起動コストとみなして差し引いた比。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        row = [LABELS[ex]]
        for im in IMPLS:
            a, b = T["%s-nojit/%s" % (im, ex)], T["%s-jit/%s" % (im, ex)]
            a0, b0 = T["%s-nojit/empty" % im], T["%s-jit/empty" % im]
            if ok(a) and ok(b):
                row.append("%.1f 倍" % ((a["min"] - a0["min"]) / (b["min"] - b0["min"])))
            else:
                row.append("error")
        L.append("| " + " | ".join(row) + " |")

    def jrow(ex, fn):
        row = [LABELS[ex]]
        for im in IMPLS:
            j = J["%s/%s" % (im, ex)]
            row.append(fn(j) if ok(T["%s-jit/%s" % (im, ex)]) else "error")
        return "| " + " | ".join(row) + " |"

    sv = lambda j, k, i=0: int(float(j["summary"][k][i]))

    L.append("\n## 2. ガード数\n")
    L.append("### 2-a. 生成された全トレース (ループ + ブリッジ) の合計\n")
    L.append("`jit-summary` の `guards` (トレース記録時) と `opt guards` (最適化後) を「記録 → 最適化後」で示す。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: "%d → %d" % (sv(j, "guards"), sv(j, "opt guards"))))
    L.append("\n### 2-b. 最も多く回ったループ 1 周あたりのガード数 (最適化後)\n")
    L.append("`jit-log-opt` と `jit-backend-counts` を有効にした別の実行から取った値。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: str(j["hot"]["guards"]) if j["hot"] else "—"))

    L.append("\n## 3. 命令数\n")
    L.append("### 3-a. 生成された全トレースの IR 命令数の合計\n")
    L.append("`jit-summary` の `recorded ops` (トレース記録時) と `opt ops` (最適化後) を「記録 → 最適化後」で示す。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: "%d → %d" % (sv(j, "recorded ops"), sv(j, "opt ops"))))
    L.append("\n### 3-b. 最も多く回ったループ 1 周あたりの IR 命令数 (最適化後)\n")
    L.append("`label` / `jump` / `debug_merge_point` を除いた命令数。括弧内はその 1 周に含まれる"
             "インタプリタのステップ数 (`debug_merge_point` の数 = 合流点を通過した回数)。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: "%d (%d)" % (j["hot"]["ops"], j["hot"]["steps"]) if j["hot"] else "—"))

    L.append("\n## 4. ウォームアップ時間\n")
    L.append("JIT ありバイナリを最小限のログ (`gc-hardware,jit-tracing,jit-summary`) で %d 回走らせた中央値 (秒)。"
             "時刻は TSC (1996.198 MHz) から換算し、起点は GC 初期化 (`gc-hardware`)。\n" % d["warm_runs"])
    L.append("### 4-a. 起動から最初のループのコンパイル完了まで\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: f(j["warm"]["first_loop"], "%.4f")))
    L.append("\n### 4-b. 起動から最後のトレースのコンパイル完了まで (JIT が安定するまで)\n")
    L.append("括弧内は実行全体に占める割合。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: "%s (%.0f%%)" % (f(j["warm"]["last_compile"], "%.4f"),
                                                     100 * j["warm"]["last_compile"] / j["warm"]["total"])
                      if j["warm"]["last_compile"] is not None else "—"))
    L.append("\n### 4-c. JIT コンパイルに費やした時間の合計 (トレース記録 + 最適化 + 機械語生成)\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: f(j["warm"]["compile"], "%.4f")))

    L.append("\n## 参考: 生成されたトレースの数\n")
    L.append("「ループ / ブリッジ / abort」。\n")
    L.append("| 例題 | CEK | CPS | 3imp |")
    L.append("| --- | ---: | ---: | ---: |")
    for ex in EXAMPLES:
        L.append(jrow(ex, lambda j: "%d / %d / %d" % (j["loops"], j["bridges"], j["aborts"])))
    L.append("\n2-a, 3-a と上の表は、4 と同じ最小ログの実行の `jit-summary` から取った (%d 回とも同じ値)。" % d["warm_runs"])
    for k, j in sorted(J.items()):
        if j["full_traces"] != j["min_traces"]:
            L.append("\n**注意 (%s)**: ログの種類によって生成されるトレースの数が変わる "
                     "(最小ログ %d 本、`jit-log-opt` などを有効にすると %d 本)。"
                     "設定ごとには毎回同じなので乱数的なばらつきではなく、ログ出力に伴うヒープ確保の変化で"
                     "JIT の判断がずれていると考えられる。2-b / 3-b はトレース数が違う方の実行から取っている。"
                     % (k, j["min_traces"], j["full_traces"]))
    return "\n".join(L) + "\n"


def main():
    import logtool
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    rdir = arg if arg and os.path.isdir(arg) else logtool.run_dir(logtool.resolve_run(arg))
    d = analyze(rdir)
    with open(os.path.join(rdir, "summary.json"), "w") as fp:
        json.dump(d, fp, indent=1, ensure_ascii=False)
    md = tables(d)
    with open(os.path.join(rdir, "tables.md"), "w", encoding="utf-8") as fp:
        fp.write(md)
    print(md)


if __name__ == "__main__":
    main()
