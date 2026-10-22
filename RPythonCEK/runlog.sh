cd /mnt/c/B4/research/eval_applicability_metaJIT/RPythonCEK
for f in countdown let-loop fib sum; do
  PYPYLOG=jit-log-opt,jit-summary:/mnt/c/Users/hiyay/AppData/Local/Temp/claude/c--B4-research-eval-applicability-metaJIT/471ca3e5-4a0c-4f88-9ecd-9df770a2e462/scratchpad/$f.log ./target-c examples/$f.scm; echo " <- $f"
done
