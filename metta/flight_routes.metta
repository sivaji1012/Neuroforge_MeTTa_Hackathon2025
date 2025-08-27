; -----------------------------
; Flight facts (DATA ONLY)
; Format:
; (flight-route "FROM" "TO" "AIRLINE" (duration HOURS) (cost USD) (layovers 0))
; -----------------------------

(flight-route "Toronto"   "NewYork"   "AirCanada" (duration 1.5) (cost 220) (layovers 0))
(flight-route "Toronto"   "London"    "AirCanada" (duration 7.2) (cost 520) (layovers 0))
(flight-route "Toronto"   "Frankfurt" "Lufthansa" (duration 7.5) (cost 540) (layovers 0))

(flight-route "NewYork"   "London"    "Delta"     (duration 6.8) (cost 480) (layovers 0))
(flight-route "NewYork"   "Paris"     "Delta"     (duration 7.1) (cost 510) (layovers 0))

(flight-route "London"    "Paris"     "BA"        (duration 1.1) (cost 120) (layovers 0))
(flight-route "London"    "Frankfurt" "Lufthansa" (duration 1.4) (cost 140) (layovers 0))

(flight-route "Frankfurt" "Paris"     "Lufthansa" (duration 1.2) (cost 130) (layovers 0))
(flight-route "Frankfurt" "Rome"      "Lufthansa" (duration 2.0) (cost 150) (layovers 0))

(flight-route "Paris"     "Rome"      "AirFrance" (duration 2.0) (cost 160) (layovers 0))
; reverse legs (westbound) for demo completeness
(flight-route "London"    "NewYork"   "Delta"      (duration 7.0) (cost 500) (layovers 0))
(flight-route "Paris"     "NewYork"   "Delta"      (duration 7.3) (cost 520) (layovers 0))
(flight-route "Frankfurt" "Toronto"   "Lufthansa"  (duration 7.6) (cost 540) (layovers 0))
(flight-route "Paris"     "London"    "BA"         (duration 1.1) (cost 120) (layovers 0))
(flight-route "Frankfurt" "London"    "Lufthansa"  (duration 1.4) (cost 140) (layovers 0))
(flight-route "Paris"     "Frankfurt" "Lufthansa"  (duration 1.2) (cost 130) (layovers 0))
(flight-route "Rome"      "Frankfurt" "Lufthansa"  (duration 2.0) (cost 150) (layovers 0))
(flight-route "Rome"      "Paris"     "AirFrance"  (duration 2.0) (cost 160) (layovers 0))
(flight-route "London"    "Toronto"   "AirCanada"  (duration 7.2) (cost 520) (layovers 0))
(flight-route "NewYork"   "Toronto"   "AirCanada"  (duration 1.5) (cost 220) (layovers 0))
