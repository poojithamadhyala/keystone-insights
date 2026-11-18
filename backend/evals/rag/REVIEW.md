# RAG eval spot-check
For each item, replace `verdict: ?` with `verdict: ok` or `verdict: bad <reason>`. Bad = the question is ambiguous, unanswerable from the evidence, or the answer is wrong. Then run `make rag-review` to record precision and drop bad items.

## q004 (house_rules, paraphrase)

**Q:** At Magnolia Lofts, how much does a resident pay monthly to park a second car beyond their assigned spot?

**A:** $75 per month

**Evidence** (Magnolia Lofts House Rules > 3. Parking and Vehicles):

> Additional vehicles require a parking permit at $75 per month.

verdict: ?

## q006 (house_rules, paraphrase)

**Q:** At Briar Place, if a resident wants to bring a big dog, at what weight do they need the community manager to sign off in writing?

**A:** Dogs over 90 lb need written approval from the community manager.

**Evidence** (Briar Place House Rules > 2. Pets):

> Dogs over 90 lb require written approval from the community manager.

verdict: ?

## q007 (house_rules, keyword)

**Q:** At Cypress Gardens, how many consecutive nights can a guest stay before they need to be added to the lease?

**A:** Up to 10 consecutive nights (and no more than 20 nights in any six-month period)

**Evidence** (Cypress Gardens House Rules > 6. Guests):

> Guests may stay up to 10 consecutive nights, and no more than 20 nights in any six-month period, without being added to the lease.

verdict: ?

## q008 (house_rules, paraphrase)

**Q:** At Alder Flats, how long can a visitor leave their car in the guest spots before it becomes a problem?

**A:** 72 consecutive hours

**Evidence** (Alder Flats House Rules > 3. Parking and Vehicles):

> Guest parking is limited to 72 consecutive hours.

verdict: ?

## q009 (house_rules, keyword)

**Q:** Harbor Flats replacement fob cost for fitness center access?

**A:** $50

**Evidence** (Harbor Flats House Rules > 5. Pool and Amenities):

> Replacement fobs cost $50.

verdict: ?

## q011 (house_rules, keyword)

**Q:** What does a parking permit for an additional vehicle cost at Cedar Commons?

**A:** $25 per month

**Evidence** (Cedar Commons House Rules > 3. Parking and Vehicles):

> Additional vehicles require a parking permit at $25 per month.

verdict: ?

## q012 (house_rules, paraphrase)

**Q:** How much advance notice does management need to give residents at Riverside Station before changing the house rules?

**A:** 30 days' written notice

**Evidence** (Riverside Station House Rules > Overview):

> Management may update them with 30 days' written notice.

verdict: ?

## q027 (house_rules, keyword)

**Q:** What days is trash collected at Hawthorne Lofts?

**A:** Mondays, Wednesdays and Fridays

**Evidence** (Hawthorne Lofts House Rules > 4. Trash and Recycling):

> Trash is collected Mondays, Wednesdays and Fridays.

verdict: ?

## q030 (lease, paraphrase)

**Q:** How often is Jerome White in Linden Terrace 1708 supposed to swap out the air filters for heating and cooling?

**A:** Every 90 days

**Evidence** (Lease 10940: Linden Terrace Unit 1708 > 6. Maintenance and Repairs):

> Resident is responsible for replacing HVAC filters every 90 days

verdict: ?

## q038 (lease, paraphrase)

**Q:** If Eric Jones in Juniper Station 605 never tells us whether he's staying or leaving when his lease ends, what happens to his rent?

**A:** The lease goes month-to-month at the then-current market rent plus a 10% premium.

**Evidence** (Lease 3351: Juniper Station Unit 605 > 7. Renewal and Notice):

> If neither party gives notice, the lease converts to month-to-month at the then-current market rent plus a month-to-month premium of 10%.

verdict: ?

## q046 (lease, paraphrase)

**Q:** For Cory Stone's studio at Lakeview Station unit 906, which utilities does the owner cover versus what the tenant has to set up themselves?

**A:** Landlord covers water, sewer and trash; resident must set up and pay all other utilities, including electricity and internet, starting on the lease start date.

**Evidence** (Lease 15665: Lakeview Station Unit 906 > 5. Utilities):

> Landlord provides water, sewer and trash. Resident is responsible for establishing service for, and paying, all other utilities including electricity and internet, effective on the start date.

verdict: ?

## q053 (lease, keyword)

**Q:** What is the square footage of Cypress Gardens unit 1503 under lease 2266?

**A:** Approximately 1057 square feet (2br)

**Evidence** (Lease 2266: Cypress Gardens Unit 1503 > 1. Premises):

> a 2br unit of approximately 1057 square feet

verdict: ?

## q054 (lease, paraphrase)

**Q:** Who is the landlord entity on Sarah Morgan's lease for unit 1307 at Summit Lofts, and is it a new lease or a renewal?

**A:** Summit Lofts Owner LLC; it is a renewal of a prior lease.

**Evidence** (Lease 5979: Summit Lofts Unit 1307 > Overview):

> made between Summit Lofts Owner LLC ("Landlord") and Sarah Morgan ("Resident"), and is a renewal of a prior lease.

verdict: ?

## q055 (lease, keyword)

**Q:** What is the early termination fee for Lease 13351 at Harbor Flats Unit 1204?

**A:** $5,220.58 (two months' rent), plus 60 days' written notice

**Evidence** (Lease 13351: Harbor Flats Unit 1204 > 8. Early Termination):

> payment of an early termination fee equal to two months' rent ($5,220.58)

verdict: ?

## q064 (lease, paraphrase)

**Q:** How long do we have to give Alec Lucero his deposit back after he moves out of Elm Heights 309?

**A:** Within 30 days after he vacates and returns all keys (less lawful deductions).

**Evidence** (Lease 6253: Elm Heights Unit 309 > 4. Security Deposit):

> within 30 days after Resident vacates and returns all keys

verdict: ?

## q068 (maintenance_sop, paraphrase)

**Q:** If a make-ready on a vacant unit is running past its deadline, who is the tech supposed to bump it up to?

**A:** The maintenance supervisor, with the reason recorded in the work order.

**Evidence** (Maintenance SOP 09: Unit Turnover Make-Ready > Escalation):

> the technician escalates to the maintenance supervisor and records the reason in the work order

verdict: ?

## q070 (maintenance_sop, paraphrase)

**Q:** If a tech can't fix an after-hours emergency within the expected response window, who do they kick it up to and what do they need to note?

**A:** They escalate to the maintenance supervisor and record the reason in the work order.

**Evidence** (Maintenance SOP 13: After-Hours Emergency Escalation > Escalation):

> the technician escalates to the maintenance supervisor and records the reason in the work order

verdict: ?

## q074 (maintenance_sop, paraphrase)

**Q:** Does the clogged drain/toilet procedure apply to shared spaces like lobby restrooms, or just tenant apartments?

**A:** It applies to both occupied units and common areas at every property.

**Evidence** (Maintenance SOP 05: Clogged Drain or Toilet > Purpose and Scope):

> It applies to occupied units and common areas at every property.

verdict: ?

## q082 (maintenance_sop, paraphrase)

**Q:** When a tech can't get a repair finished within the required response window for its urgency level, who do they kick it up to and what do they need to note?

**A:** They escalate to the maintenance supervisor and record the reason in the work order.

**Evidence** (Maintenance SOP 14: Vendor Dispatch and Approval > Escalation):

> the technician escalates to the maintenance supervisor and records the reason in the work order.

verdict: ?

## q083 (maintenance_sop, keyword)

**Q:** Does Maintenance SOP 03 for active water leak requests apply to common areas or just occupied units?

**A:** It applies to both occupied units and common areas at every property.

**Evidence** (Maintenance SOP 03: Active Water Leak > Purpose and Scope):

> It applies to occupied units and common areas at every property.

verdict: ?

## q101 (vendor_contract, keyword)

**Q:** Under the Harris Electric Inc agreement for Willow Heights, who dispatches Harris Electric for electrical services and how?

**A:** Owner's maintenance staff dispatches them through work orders.

**Evidence** (Vendor Agreement: Harris Electric Inc / Willow Heights > 1. Scope of Services):

> as dispatched by Owner's maintenance staff through work orders

verdict: ?

## q105 (vendor_contract, keyword)

**Q:** What is the trip charge per visit for Floyd Property Services Group at Birch Terrace?

**A:** $45 per visit

**Evidence** (Vendor Agreement: Floyd Property Services Group / Birch Terrace > 3. Rates and Fees):

> with a trip charge of $45 per visit

verdict: ?

## q113 (inspection_report, keyword)

**Q:** Who conducted the April 2026 annual inspection at Willow Heights in Lindsaymouth, ND, and on what date?

**A:** Peter Gibson, on April 12, 2026

**Evidence** (Inspection Report: Willow Heights, April 2026 > Overview):

> conducted on April 12, 2026 by Peter Gibson.

verdict: ?

## q116 (inspection_report, paraphrase)

**Q:** After the August 2026 inspection at Cypress Gardens, how long do we have to go back and recheck the apartments that had problems?

**A:** Within 30 days

**Evidence** (Inspection Report: Cypress Gardens, August 2026 > Follow-Up):

> A re-inspection of units with findings will be completed within 30 days.

verdict: ?

## q118 (inspection_report, paraphrase)

**Q:** What did the inspector do about the apartment at Magnolia Lofts where they saw a pet that wasn't allowed?

**A:** Unit 503 was issued a lease violation notice.

**Evidence** (Inspection Report: Magnolia Lofts, April 2026 > Unit Findings):

> | 503 | unauthorized pet observed | lease violation notice issued |

verdict: ?
