; 非末尾再帰。フレームが n 段積まれる
(define sum (lambda (n) (if (zero? n) 0 (+ n (sum (- n 1))))))
(display (sum 1000000))
