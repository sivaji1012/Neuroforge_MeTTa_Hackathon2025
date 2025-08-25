; Illustrative MeTTa algorithm helpers and a functional Dijkstra sketch.
; This file is intended as a **learning aid**. The Python backend uses NetworkX Dijkstra
; for production-grade routing, while you can evolve these MeTTa definitions if you want
; a fully in-MeTTa solver.

; Tuple & list helpers (very lightweight)
(= (cons $x $xs) (pair $x $xs))
(= (head (pair $x $xs)) $x)
(= (tail (pair $x $xs)) $xs)
(= (nil) ())

; Path helpers
(= (path-start (pair $x $xs)) $x)
(= (path-end $p)
   (if (== (tail $p) ())
       (head $p)
       (path-end (tail $p))))

(= (append $xs $ys)
   (if (== $xs ())
       $ys
       (cons (head $xs) (append (tail $xs) $ys))))

; Expand all outgoing edges for a frontier node
; Returns a list of (to airline duration cost layovers)
(= (expand $city)
   (neighbors $city))

; Compute total weight of a path given a criteria
; Here path is a list of nodes: (A B C ... Z)
(= (path-weight (pair $a (pair $b $rest)) $criteria)
   (+ (match &self
        (flight-route $a $b $airline (duration $d) (cost $c) (layovers $l))
        (edge-weight $a $b $airline (duration $d) (cost $c) (layovers $l) $criteria))
      (path-weight (pair $b $rest) $criteria)))
(= (path-weight (pair $x ())) 0)
(= (path-weight ()) 0)

; Dijkstra (Uniform-Cost Search) — functional sketch:
; This enumerates paths in increasing cost order and picks the minimum to the target.
; NOTE: For large graphs, prefer Python backend for performance.
(= (extend-paths (pair $path $restPaths) $criteria)
   (append (extend-single $path $criteria) (extend-paths $restPaths $criteria)))
(= (extend-paths () $criteria) ())

; Extend one path by one hop to each neighbor
(= (extend-single (pair $lastNode $prefix) $criteria)
   (match &self
     (neighbors $lastNode)
     (cons (cons (head (match &self (neighbors $lastNode) ($to $air $d $c $l)))  ; next node
                 (pair $lastNode $prefix))
           ())))

; The above is kept deliberately simple. For full correctness you would:
; - prevent revisiting nodes already in path
; - use a best-first queue ordered by (path-weight ... $criteria)
; - stop when you first pop the goal node

; API: (dijkstra $start $end $criteria) -> a minimal-cost path (list of nodes)
; This is a schematic placeholder; implementers are encouraged to refine it.
(= (dijkstra $start $end $criteria)
   (if (== $start $end)
       (pair $start ())
       (choose-min
         (map (lambda ($n)
                 (dijkstra $n $end $criteria))
              (neighbors $start))
         (lambda ($p) (path-weight (cons $start $p) $criteria)))))

; Argmin/choose-min and map/lambda are not part of the core here.
; They can be provided by your MeTTa standard library or implemented similarly.
; Treat this as a guide to structure your MeTTa-only solution.
