# Manhattan Belgian Dark Strong Ale

## Intent
- Style: Belgian Dark Strong Ale (BJCP 26D)
- Goal: Cherry and dark-fruit expression with clean attenuation
- Last noted result: "Amazing cherry smell and flavor"

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
