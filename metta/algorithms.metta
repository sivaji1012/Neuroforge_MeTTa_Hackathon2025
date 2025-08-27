; ----------------------------------------------------------------------
; MeTTa algorithms over flight-route facts
; Facts are provided in flight_routes.metta like:
; (flight-route "A" "B" "Carrier" (duration 1.5) (cost 220) (layovers 0))
; ----------------------------------------------------------------------

; -- Helpers ------------------------------------------------------------

(= (edge $from $to $air $dur $cost $lay)
   (flight-route $from $to $air (duration $dur) (cost $cost) (layovers $lay)))

(= (neighbors $city)
   (match &self
     (edge $city $to $air $d $c $l)
     ($to $air $d $c $l)))

; Simple arithmetic helpers (MeTTa numbers are atoms; rely on host math)
; We’ll aggregate using host math by returning numeric atoms directly.

; Compute one edge’s weighted score given user weights:
;   weight = w_d * duration + w_c * (cost/100) + w_l * 1 (per hop penalty)
(= (edge-weight $d $c $w_d $w_c $w_l)
   (+ (* $w_d $d) (* $w_c (/ $c 100)) (* $w_l 1)))

; Sum list of numbers
(= (sum ()) 0)
(= (sum (pair $x $xs)) (+ $x (sum $xs)))

; Reverse list
(= (rev ()) ())
(= (rev (pair $x $xs)) (append (rev $xs) (pair $x ())))

; Append
(= (append () $ys) $ys)
(= (append (pair $x $xs) $ys) (pair $x (append $xs $ys)))

; ----------------------------------------------------------------------
; UNIFORM-COST SEARCH (Dijkstra behavior) with max-layover bound
; Returns (best-path best-score) where best-path is (from ... to)
; ----------------------------------------------------------------------

; Expand a frontier item (path so far, score so far), producing next paths.
(= (ucs_expand (pair $path $score) $w_d $w_c $w_l $max_hops)
   (let (($last (head (rev $path))))
     (if (< (length (rev $path)) (+ $max_hops 1))         ; hops <= max
         (match &self
           (neighbors $last)
           (let (($to  (head (neighbors $last)))
                 ($air (head (tail (neighbors $last))))
                 ($d   (head (tail (tail (neighbors $last)))))
                 ($c   (head (tail (tail (tail (neighbors $last))))))
                 ($l   (head (tail (tail (tail (tail (neighbors $last))))))))
             (let (($w (edge-weight $d $c $w_d $w_c $w_l)))
               (pair (append $path (pair $to ())) (+ $score $w)))))
         ())))

; Pick the min by score from a list of (path,score) pairs
(= (pick_min (pair (pair $p $s) $rest))
   (pick_min_acc $p $s $rest))
(= (pick_min_acc $best_p $best_s ())
   (pair $best_p $best_s))
(= (pick_min_acc $best_p $best_s (pair (pair $p $s) $rest))
   (if (< $s $best_s)
       (pick_min_acc $p $s $rest)
       (pick_min_acc $best_p $best_s $rest)))

; Main UCS loop
(= (ucs_loop $goal () $w_d $w_c $w_l $max_hops $visited)
   (pair () 999999)) ; no route
(= (ucs_loop $goal $front $w_d $w_c $w_l $max_hops $visited)
   (let (($best (pick_min $front)))
     (let (($path (head $best))
           ($cost (head (tail $best)))
           ($last (head (rev (head $best)))))
       (if (== $last $goal)
           (pair $path $cost)
           (let (($new (ucs_expand (pair $path $cost) $w_d $w_c $w_l $max_hops)))
             (ucs_loop $goal
                       (append (filter_new $new $visited) (remove_one $best $front))
                       $w_d $w_c $w_l $max_hops
                       (pair $last $visited)))))))

; Remove one item from frontier
(= (remove_one $x ()) ())
(= (remove_one $x (pair $y $ys))
   (if (== $x $y) $ys (pair $y (remove_one $x $ys))))

; Filter out paths whose head is already visited
(= (filter_new () $visited) ())
(= (filter_new (pair (pair $p $s) $rest) $visited)
   (let (($last (head (rev $p))))
     (if (member $last $visited)
         (filter_new $rest $visited)
         (pair (pair $p $s) (filter_new $rest $visited)))))

; member
(= (member $x ()) false)
(= (member $x (pair $y $ys)) (if (== $x $y) true (member $x $ys)))

; Public: (best-route $from $to $w_d $w_c $w_l $max_layovers)
; Frontier starts with path=($from) cost=0
(= (best-route $from $to $w_d $w_c $w_l $max_layovers)
   (ucs_loop $to (pair (pair (pair $from ()) 0) ()) $w_d $w_c $w_l $max_layovers ()))

; ----------------------------------------------------------------------
; A* (admissible heuristic = great-circle time lower bound)
; For portability we approximate heuristic as 0 here.
; You can override (h_est $node $goal $w_d) from Python via facts if desired.
; ----------------------------------------------------------------------

(= (h_est $node $goal $w_d) 0)

(= (astar_expand (pair $path $g) $goal $w_d $w_c $w_l $max_hops)
   (let (($last (head (rev $path))))
     (if (< (length (rev $path)) (+ $max_hops 1))
         (match &self
           (neighbors $last)
           (let (($to  (head (neighbors $last)))
                 ($d   (head (tail (tail (neighbors $last)))))
                 ($c   (head (tail (tail (tail (neighbors $last)))))))
             (let (($w (edge-weight $d $c $w_d $w_c $w_l)))
               (pair (append $path (pair $to ())) (+ $g $w) (+ $g $w (h_est $to $goal $w_d))))))
         ())))

; take min by f value in triples (path, g, f)
(= (pick_min_f (pair (pair $p (pair $g (pair $f ()))) $rest))
   (pick_min_f_acc $p $g $f $rest))
(= (pick_min_f_acc $bp $bg $bf ())
   (pair $bp (pair $bg (pair $bf ()))))
(= (pick_min_f_acc $bp $bg $bf (pair (pair $p (pair $g (pair $f ()))) $rest))
   (if (< $f $bf)
       (pick_min_f_acc $p $g $f $rest)
       (pick_min_f_acc $bp $bg $bf $rest)))

(= (astar_loop $goal () $w_d $w_c $w_l $max_hops $visited) (pair () 999999))
(= (astar_loop $goal $open $w_d $w_c $w_l $max_hops $visited)
   (let (($best (pick_min_f $open)))
     (let (($p (head $best))
           ($g (head (tail $best)))
           ($last (head (rev (head $best)))))
       (if (== $last $goal)
           (pair $p $g)
           (let (($exp (astar_expand (pair $p $g) $goal $w_d $w_c $w_l $max_hops)))
             (astar_loop $goal
                         (append (filter_new_astar $exp $visited) (remove_one $best $open))
                         $w_d $w_c $w_l $max_hops
                         (pair $last $visited)))))))

(= (filter_new_astar () $visited) ())
(= (filter_new_astar (pair (pair $p (pair $g (pair $f ()))) $rest) $visited)
   (let (($last (head (rev $p))))
     (if (member $last $visited)
         (filter_new_astar $rest $visited)
         (pair (pair $p (pair $g (pair $f ()))) (filter_new_astar $rest $visited)))))

(= (a-star-route $from $to $w_d $w_c $w_l $max_layovers)
   (astar_loop $to (pair (pair (pair $from (pair 0 (pair (h_est $from $to $w_d) ()))) ()) ) $w_d $w_c $w_l $max_layovers ()))
