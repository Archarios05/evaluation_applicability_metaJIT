# -*- coding: utf-8 -*-
# 最適化前 (jit-log-noopt) と最適化後 (jit-log-opt) のトレースを同じ実行で採取する
#   python3 bench/collect_noopt.py [--run RUN]
# 結果は計測回 (既定は最新) の logs/<実装>-<例題>.noopt.log
import argparse
import os
import shutil
import time

import logtool
import run_bench as rb

LOG = "jit-tracing,jit-log-noopt,jit-log-opt,jit-summary,jit-backend-counts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="追加先の計測回 (既定は最新)")
    a = ap.parse_args()
    rdir = logtool.run_dir(logtool.resolve_run(a.run))
    out = os.path.join(rdir, "logs")
    if not os.path.isdir(os.path.join(rb.WORK, "examples")):
        rb.prepare()
    meta = logtool.load_meta(rdir)
    for name, _, _, _ in rb.IMPLS:
        b = "%s-jit" % name
        h = logtool.sha256(os.path.join(rb.WORK, b))
        old = (meta.get("binaries") or {}).get(b)
        if old and old != h:
            print("注意: %s が計測回 %s のときと異なるバイナリです" % (b, meta["id"]))
        meta.setdefault("noopt_binaries", {})[b] = h
    for name, _, _, _ in rb.IMPLS:
        for ex in rb.EXAMPLES:
            p = os.path.join(rb.WORK, "logs", "%s-%s.noopt.log" % (name, ex))
            _, o, _ = rb.run("%s-jit" % name, ex, {"PYPYLOG": LOG + ":" + p})
            shutil.copy(p, out)
            print("%s %s -> %s" % (name, ex, o[:20]))
    meta.setdefault("pypylog", {})["noopt"] = LOG
    meta["noopt_date"] = time.strftime("%Y-%m-%d %H:%M")
    kinds = meta.setdefault("log_kinds", [])
    if "noopt" not in kinds:
        kinds.append("noopt")
    logtool.save_meta(rdir, meta)


if __name__ == "__main__":
    main()
