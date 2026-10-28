# RATE-SPEC v0 builder domain

Construction only; runtime unverified. All inputs are JSON-compatible dictionaries.
`price_shipment(contract, shipment, fuel_index) -> list[dict]` and
`price_contracts(contracts, shipment, fuel_index) -> list[dict]` live in
`freightrec.engine.engine`, with `ENGINE_VERSION` binding semantic changes.
Contract-list selection belongs to `price_contracts`; overlap/gap refuses.
Codes: LH, FS, DETENTION, LIFTGATE. Entitlements contain code, stop_seq,
expected_cents (null on unknown), clause_id, trace, missing_facts, reason_code,
evidence_pointers. LH/FS use stop_seq=0. Accessorials use delivery stop_seq.

## Wire shape
Contract: contract_id, carrier, effective_from/effective_to (ISO dates, half-open),
basis (pickup default or delivery), origin_zone, destination_zone,
clause_id, evidence_pointers; bands=[{min_lb,max_lb,rate_per_cwt}], minimum_cents;
fuel={clause_id,brackets:[{low,high,percent}]};
detention={clause_id,free_minutes,increment_minutes,max_billable_minutes,
hourly_rate,allow_without_preauthorization};
liftgate={clause_id,amount_cents,requires_authorization};
accessorial_cap_cents and accessorial_priority (exact permutation of
DETENTION,LIFTGATE). Decimal rates/bracket bounds/percent are strings.
Integers are strict nonnegative, booleans and floats refused.

Shipment: carrier, shipment_id, origin_zone, destination_zone, weight_lb
(strict integer pounds), pickup_ts, pickup_timezone, delivery_ts,
delivery_timezone, evidence_pointers, stops=[{stop_seq,timezone,arrive_ts,
depart_ts,detention_authorized,liftgate_requested,liftgate_authorized,
liftgate_performed,evidence_pointers}]. Stops are delivery stops with unique
positive stop_seq. Service states are explicit boolean or null/missing.

Fuel index list: {publication_date,index_value,evidence_pointers}; index_value
is a decimal string. Latest publication on/before pickup local date; duplicate
publication dates refuse. No invoice date is consulted.

Missing/invalid inputs produce cannot_determine entitlements; consumers must
not turn unknown into zero. Known disallowed service has zero entitlement.
Invalid contracts refuse the entire result. Missing service facts affect that
service; an unknown capped service makes other accessorial allocations unknown
because consuming an unknown amount cannot establish remaining cap.
Sources are passed through for DL2 resolver verification, never invented here.

Pure helpers have no I/O. Timezone consistency uses the supplied offset and IANA
zone at that instant; UTC elapsed seconds govern detention. Dependency packaging
must lock tzdata before runtime validation on Windows/Docker.

## Builder arithmetic illustrations (not executed or independent oracle)

| Boundary | Arithmetic / intended result |
|---|---|
| Minimum masks weight rate | 500 lb at $12/cwt = $60; $75 minimum yields 7500 cents |
| Band upper endpoint | 1000 lb excluded from [0,1000), included in [1000,2000) |
| Fuel base | 7500 linehaul cents at 12.5% yields 938 cents half up |
| Pickup fuel decoy | Monday publication after Sunday pickup is ineligible |
| Detention | 7201 UTC seconds less 120 free minutes leaves one second; 15-minute increment yields 15 minutes |
| Spring offset transition | 01:30 -05:00 to 03:30 -04:00 is 3600 UTC seconds |
| Cap priority | DETENTION 6000 then LIFTGATE 3000 under 7000 cap allocates 6000 then 1000 |
| Unknown earlier entitlement | Later positive accessorial remains null while cap remainder is uncertain |
| Zero eligibility | Explicit unauthorized service is zero; absent authorization is unknown |

These are builder-owned explanatory arithmetic, not held-out cases or gate evidence.
Deferred: import/integration execution, all boundary/runtime tests, tzdata packaging
and lock verification, DL2 provenance/dependency binding and complete CLI journey.
