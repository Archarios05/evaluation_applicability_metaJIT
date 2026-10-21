; slambda (関数位置の lambda) と letrec を使うループ
(define count
  (lambda (n)
    (letrec ((loop (lambda (i acc)
                     (if (zero? i)
                         acc
                         ((lambda (j) (loop j (+ acc 1))) (- i 1))))))
      (loop n 0))))
(display (count 10000000))
