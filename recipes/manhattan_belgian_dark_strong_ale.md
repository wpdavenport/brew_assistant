# Manhattan Belgian Dark Strong Ale

## Intent
- Style: Belgian Dark Strong Ale (BJCP 26D)
- Goal: Cherry and dark-fruit expression with clean attenuation
- Last noted result: "Amazing cherry smell and flavor"
- Side-by-side target: Westvleteren 12 clone fidelity, not just generic 26D quality

## Competition Tracking
- Competition: Spirit Of Free Beer
- Entry status: entered
- Results date: by 12:00 PM on April 13, 2026

## Fermentables
- 17.0 lb Pale Malt
- 11.0 oz CaraMunich II
- 11.0 oz CaraMunich III
- 1.0 lb Dark Candi Sugar (split)
  - 0.3 lb (30%) at 10 min left in boil
  - 0.7 lb (70%) at high krausen (~40% attenuation)

## Hops
- 1.00 oz Hallertauer (4.8% AA) at 60 min
- 1.00 oz Styrian Goldings (5.4% AA) at 60 min
- 0.55 oz Hallertauer (4.8% AA) at 15 min
- 0.55 oz Styrian Goldings (5.4% AA) at 15 min

## Yeast
- Strain: WLP540 Abbey IV Ale Yeast (Rochefort)
- Starter: 2 packs in 2.0 L starter, stir plate for 3 days with nutrient
- Last run note: pitched full 2.0 L starter (no decant)
- Next-run preference: cold crash and decant starter before pitch

## Water Profile (as run)
- 0.035 oz Gypsum
- 0.113 oz Calcium Chloride
- 4 ml Phosphoric Acid (kettle)

## Mash and Boil (recorded)
- Kettle volume: 8.3 gal
- Pre-boil volume: 7.1 gal
- Pre-boil gravity: 1.073
- Boil time: 60 min
- Post-boil gravity: 1.088
- Kettle addition: Whirlfloc at 10 min

## Fermentation Schedule
1. Pitch at 70F for 3 days
2. Free rise with 80F ceiling
   - Log note: temp was low on Day 3, manually raised to 75F and held for 7 days
3. Add remaining 70% candi sugar + 2 g Fermaid-O when ~40% sugar is consumed
4. Condition with a 6-day slow ramp down to 46F

## Coach Notes (from batch history)
- Raising to 75F on Day 3 likely prevented a stall and supported ester profile
- The 30/70 sugar split supported attenuation
- Kettle phosphoric addition likely smoothed bitterness and improved break
- Side-by-side with Westvleteren 12 showed strong clone proximity before final calibration changes

## Post-Packaging Clone Calibration
- Commercial comparison: Westvleteren 12
- Packaged sensory finding: overall beer was nearly a dead ringer side-by-side once the sample was adjusted with 3 drops of lactic acid per 12 oz pour
- Aroma: cherry notes were prominent on both beers
- Appearance: Westvleteren 12 presented slightly darker and cloudier; Manhattan was a bit cleaner and more polished
- Mouthfeel: close match
- Flavor: lactic-acid-adjusted Manhattan matched closely in core flavor
- Palate shape:
  - Westvleteren 12 hit earlier and faster on the palate
  - Westvleteren 12 finished with a slight bitterness plus tartness
  - Manhattan presented more uniformly across the palate

## Proposed Next Iteration Spec (Not Yet Locked)
- Keep unchanged:
  - WLP540 / Rochefort-family yeast direction
  - cherry / dark-fruit fermentation profile
  - 30/70 candi sugar split
  - 60 min bittering structure
- Proposed formulation and process changes:
  - Fermentables:
    - reduce CaraMunich II from 11.0 oz to 8.0 oz
    - increase CaraMunich III from 11.0 oz to 14.0 oz
    - keep total crystal weight unchanged; aim is slightly deeper color, not more caramel weight
  - Kettle pH / finish shaping:
    - stop using a blind fixed acid dose as the final target
    - measure end-of-boil pH and target 5.05-5.10 at room-temp sample
    - keep the acid move process-side rather than dosing packaged beer
  - Clarity / presentation:
    - reduce Whirlfloc from 1 tab to 1/2 tab at 10 min
    - keep cold conditioning at 42F (5.6C) but avoid extended polish-conditioning beyond what is needed for clean transfer
  - Finish definition:
    - target packaged carbonation at 3.0-3.1 vol CO2 to sharpen the front-palate hit and support the slight bitter-tart finish
- Hold unless retest says otherwise:
  - do not increase bittering hops yet
  - do not broaden the specialty malt bill
  - do not use packaged-beer lactic dosing as the production solution

## Ranked Change Candidates
1. End-of-boil pH target and packaged-beer pH logging
2. Slight color shift via CaraMunich II / III rebalance
3. Less polished presentation via reduced kettle fining
4. Higher clone-appropriate carbonation before any bitterness rewrite

## System Calibration Update (G40)
- Current equipment baseline in `profiles/equipment.yaml`: `boil_off_rate_gal_per_hour: 1.76`
- With pre-boil 7.1 gal and 60 min boil, expected boil-off is ~1.76 gal
- Expected post-boil volume from that assumption is ~5.34 gal (pre-chill)

## Next Brew Calibration Gate
Record these on next Manhattan brew to fully lock recipe math to the new baseline:
- Measured pre-boil volume
- Measured pre-boil gravity (temp-corrected)
- Measured post-boil volume (pre-chill)
- Measured OG into fermenter and volume into fermenter

Then update this recipe with final locked targets for:
- Total liquor
- Pre-boil volume/gravity band
- Post-boil volume/gravity band
