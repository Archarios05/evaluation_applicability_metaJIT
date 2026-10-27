; 末尾再帰ループ。スタックは伸びない
(define loop (lambda (n) (if (zero? n) 0 (loop (- n 1)))))
(display (loop 10000000))
