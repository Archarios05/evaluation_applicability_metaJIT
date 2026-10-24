# -*- coding: utf-8 -*-
# WSL 上の python3 で実行する計測スクリプト
#   python3 bench/run_bench.py [--runs N] [--tag TAG] [--note "メモ"]
# バイナリをネイティブ FS にコピーし、時間計測とログ採取を行って JSON に書き出す
# 結果は計測回ごとに bench/results/runs/<日時>[-TAG]/ に置く (一覧・比較は logtool.py)
import argparse
import json
import os
import platform
import shutil
import subprocess
import time

import logtool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.expanduser("~/metajit_bench")
CPU = "2"

IMPLS = [
    ("CEK", "RPythonCEK", "target-c-nojit", "target-c"),
    ("CPS", "continuation_passing_interpreter", "target-c-nojit", "target-c"),
    ("3imp", "RPython_3imp", "3imp-c-nojit", "3imp-c"),
]
EXAMPLES = ["countdown", "let-loop", "fib", "sum"]
EMPTY = "empty"

MIN_LOG = "gc-hardware,jit-tracing,jit-summary"
FULL_LOG = "gc-hardware,jit-tracing,jit-log-opt,jit-abort,jit-summary,jit-backend-counts"


def prepare():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "examples"))
    os.makedirs(os.path.join(WORK, "logs"))
    for name, d, nojit, jit in IMPLS:
        for b in (nojit, jit):
            dst = os.path.join(WORK, "%s-%s" % (name, "jit" if b == jit else "nojit"))
            shutil.copy(os.path.join(ROOT, d, b), dst)
            os.chmod(dst, 0o755)
    for ex in EXAMPLES:
        shutil.copy(os.path.join(ROOT, "RPythonCEK", "examples", ex + ".scm"),
                    os.path.join(WORK, "examples"))
    with open(os.path.join(WORK, "examples", EMPTY + ".scm"), "w") as f:
        f.write("(display 0)\n")


def run(binary, ex, env=None):
    e = dict(os.environ)
    e.pop("PYPYLOG", None)
    if env:
        e.update(env)
    cmd = ["taskset", "-c", CPU, os.path.join(WORK, binary),
           os.path.join(WORK, "examples", ex + ".scm")]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
    t = time.perf_counter() - t0
    return t, p.stdout.decode("utf-8", "replace").strip(), p.returncode


def bench_times(runs):
    res = {}
    for name, _, _, _ in IMPLS:
        for mode in ("nojit", "jit"):
            b = "%s-%s" % (name, mode)
            for ex in EXAMPLES + [EMPTY]:
                run(b, ex)
                ts = []
                out = None
                for _ in range(runs):
                    t, out, rc = run(b, ex)
                    ts.append(t)
                res["%s/%s" % (b, ex)] = {"times": ts, "output": out, "rc": rc}
                print("%-12s %-10s min=%.4f out=%s" % (b, ex, min(ts), out[:20]))
    return res


def collect_logs(warm_runs):
    res = {}
    for name, _, _, _ in IMPLS:
        b = "%s-jit" % name
        for ex in EXAMPLES:
            full = os.path.join(WORK, "logs", "%s-%s.full.log" % (name, ex))
            run(b, ex, {"PYPYLOG": FULL_LOG + ":" + full})
            mins = []
            for i in range(warm_runs):
                p = os.path.join(WORK, "logs", "%s-%s.min%d.log" % (name, ex, i))
                t, _, _ = run(b, ex, {"PYPYLOG": MIN_LOG + ":" + p})
                mins.append({"path": p, "wall": t})
            res["%s/%s" % (name, ex)] = {"full": full, "min": mins}
            print("logged %s %s" % (name, ex))
    return res


def cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except IOError:
        pass
    return platform.processor()


def meta(rid, a):
    bins = dict((os.path.basename(p), logtool.sha256(p)) for p in
                sorted(os.path.join(WORK, f) for f in os.listdir(WORK)
                       if os.path.isfile(os.path.join(WORK, f))))
    exs = dict((f, logtool.sha256(os.path.join(WORK, "examples", f)))
               for f in sorted(os.listdir(os.path.join(WORK, "examples"))))
    return {"id": rid, "date": time.strftime("%Y-%m-%d %H:%M"), "note": a.note,
            "runs": a.runs, "warm_runs": a.warm_runs,
            "impls": [i[0] for i in IMPLS], "examples": EXAMPLES,
            "log_kinds": ["full"] + ["min%d" % i for i in range(a.warm_runs)],
            "pypylog": {"full": FULL_LOG, "min": MIN_LOG},
            "cpu": "%s (taskset -c %s)" % (cpu_model(), CPU), "host": " ".join(platform.uname()),
            "binaries": bins, "examples_sha256": exs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--warm-runs", type=int, default=5)
    ap.add_argument("--tag", default="", help="計測回 ID の末尾に付ける名前")
    ap.add_argument("--note", default="", help="計測回のメモ")
    ap.add_argument("--out", help="出力先 (既定は results/runs/<日時>[-TAG])")
    a = ap.parse_args()
    rid = os.path.basename(a.out.rstrip("/")) if a.out else logtool.new_run_id(a.tag)
    a.out = a.out or logtool.run_dir(rid)
    if os.path.exists(a.out):
        raise SystemExit("既にあります: %s" % a.out)
    prepare()
    times = bench_times(a.runs)
    logs = collect_logs(a.warm_runs)
    shutil.copytree(os.path.join(WORK, "logs"), os.path.join(a.out, "logs"))
    for v in logs.values():
        v["full"] = os.path.join(a.out, "logs", os.path.basename(v["full"]))
        for m in v["min"]:
            m["path"] = os.path.join(a.out, "logs", os.path.basename(m["path"]))
    with open(os.path.join(a.out, "raw.json"), "w") as f:
        json.dump({"date": time.strftime("%Y-%m-%d %H:%M"), "runs": a.runs,
                   "times": times, "logs": logs}, f, indent=1)
    logtool.save_meta(a.out, meta(rid, a))
    print("-> %s" % a.out)


if __name__ == "__main__":
    main()
