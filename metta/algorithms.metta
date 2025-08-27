; Illustrative MeTTa algorithm helpers and a functional Dijkstra sketch.
; Python handles production routing; this remains for study/extension.

(= (cons $x $xs) (pair $x $xs))
(= (head (pair $x $xs)) $x)
(= (tail (pair $x $xs)) $xs)
(= (nil) ())

(= (path-start (pair $x $xs)) $x)
(= (path-end $p)
   (if (== (tail $p) ())
       (head $p)
       (path-end (tail $p))))

(= (append $xs $ys)
   (if (== $xs ())
       $ys
       (cons (head $xs) (append (tail $xs) $ys))))

(= (expand $city)
   (neighbors $city))

(= (path-weight (pair $a (pair $b $rest)) $criteria)
   (+ (match &self
        (flight-route $a $b $air (duration $d) (cost $c) (layovers $l))
        (edge-weight $a $b $air (duration $d) (cost $c) (layovers $l) $criteria))
      (path-weight (pair $b $rest) $criteria)))
(= (path-weight (pair $x ())) 0)
(= (path-weight ()) 0)

; Dijkstra sketch (not production)
(= (extend-paths (pair $path $restPaths) $criteria)
   (append (extend-single $path $criteria) (extend-paths $restPaths $criteria)))
(= (extend-paths () $criteria) ())

(= (extend-single (pair $lastNode $prefix) $criteria)
   (match &self
     (neighbors $lastNode)
     (cons (cons (head (match &self (neighbors $lastNode) ($to $air $d $c $l)))
                 (pair $lastNode $prefix))
           ())))

(= (dijkstra $start $end $criteria)
   (if (== $start $end)
       (pair $start ())
       (choose-min
         (map (lambda ($n) (dijkstra $n $end $criteria))
              (neighbors $start))
         (lambda ($p) (path-weight (cons $start $p) $criteria)))))
