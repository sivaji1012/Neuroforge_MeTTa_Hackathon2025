; Sample MeTTa knowledge base: flight facts + preferences
; (duration hours), (cost USD), (layovers 0) for direct edges.

(flight-route "Toronto" "NewYork" "AirCanada" (duration 1.5) (cost 220) (layovers 0))
(flight-route "Toronto" "London" "AirCanada" (duration 7.2) (cost 520) (layovers 0))
(flight-route "NewYork" "London" "Delta"     (duration 6.8) (cost 480) (layovers 0))
(flight-route "NewYork" "Paris"  "Delta"     (duration 7.1) (cost 510) (layovers 0))
(flight-route "London"  "Paris"  "BA"        (duration 1.1) (cost 120) (layovers 0))
(flight-route "London"  "Frankfurt" "Lufthansa" (duration 1.4) (cost 140) (layovers 0))
(flight-route "Frankfurt" "Paris" "Lufthansa"   (duration 1.2) (cost 130) (layovers 0))
(flight-route "Toronto" "Frankfurt" "Lufthansa" (duration 7.5) (cost 540) (layovers 0))
(flight-route "Paris" "Rome" "AirFrance"        (duration 2.0) (cost 160) (layovers 0))
(flight-route "Frankfurt" "Rome" "Lufthansa"    (duration 2.0) (cost 150) (layovers 0))

; Preferences (illustrative)
(user-preferences "User1" (prioritize cost))
(user-preferences "User2" (prioritize duration))

; Convenience query: normalize facts into simple tuple
(= (flight $from $to $airline $dur $cost $lay)
   (flight-route $from $to $airline (duration $dur) (cost $cost) (layovers $lay)))

; Get all direct routes between two cities
(= (getDirectRoutes $start $end)
   (match &self
     (flight-route $start $end $airline (duration $dur) (cost $cost) (layovers $lay))
     ($airline $dur $cost $lay)))

; List neighbors from a city (returns (to airline duration cost layovers))
(= (neighbors $city)
   (match &self
     (flight-route $city $to $airline (duration $dur) (cost $cost) (layovers $lay))
     ($to $airline $dur $cost $lay)))

; Weight by a simple criteria atom (duration|cost|layovers)
(= (weight-by-criteria (duration $d) (cost $c) (layovers $l) duration)
   $d)
(= (weight-by-criteria (duration $d) (cost $c) (layovers $l) cost)
   $c)
(= (weight-by-criteria (duration $d) (cost $c) (layovers $l) layovers)
   $l)

; Edge-weight utility returning a number given a criteria symbol
(= (edge-weight $from $to $airline (duration $d) (cost $c) (layovers $l) $criteria)
   (weight-by-criteria (duration $d) (cost $c) (layovers $l) $criteria))
