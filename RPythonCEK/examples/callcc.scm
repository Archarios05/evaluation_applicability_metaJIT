(define product
  (lambda (l)
    (call-with-current-continuation
      (lambda (return)
        (letrec ((loop (lambda (l)
                         (if (null? l)
                             1
                             (if (zero? (car l))
                                 (return 0)
                                 (* (car l) (loop (cdr l))))))))
          (loop l))))))
(display (product (cons 1 (cons 0 (cons 3 '())))))
