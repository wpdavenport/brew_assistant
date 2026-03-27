# Robert the Bruce Clone - In Development (BJCP 34A / 17C Base)

Artifact Chain: Robert the Bruce Clone (34A Clone Beer)
Primary:
  [x] Research        libraries/beer_research/17C_wee_heavy.md
  [x] BJCP overlay    libraries/bjcp_overlays/bjcp_17C_2021_overlay.md
  [x] Recipe          recipes/in_development/robert_the_bruce_clone_34A.md  (Draft / In Development)
  [ ] Brew day sheet  brewing/brew_day_sheets/robert_the_bruce_clone_brew_day_sheet.html  (not yet created)

Side chains:
  [x] Equipment   profiles/equipment.yaml  (verified 2026-01-15)
  [x] Inventory   libraries/inventory/stock.json
  [x] Water       profiles/water_profiles.md
  [x] Yeast lib   libraries/yeast_library.md

Lifecycle: Research -> Recipe Draft -> Competition Lock -> Brew Day Sheet Generated -> Brewed -> Archived
Current stage: Recipe Draft

## INTENT
First-pass 3 Floyds Robert the Bruce clone built for iterative calibration, not for premature lock.

This version is clone-first:
- declared commercial target drives the build
- base-style guardrails come from 17C Wee Heavy
- malt structure is intentionally layered to respect 3 Floyds' "10 unique malts" framing without letting the beer collapse into muddy sweetness

## COMPETITION ENTRY
- BJCP Category: 34A Clone Beer
- Declared Commercial Example: 3 Floyds Robert the Bruce
- Declared Base Style: 17C Wee Heavy

## TARGET PARAMETERS
- Batch size (into fermenter): 5.0 gal (19.0 L)
- OG: 1.074-1.076
- FG: 1.015-1.017
- ABV: 7.5-7.8%
- IBU: 31-33
- SRM: 20-22
- Carbonation: 2.1-2.3 vols
- Mash pH (room temp): 5.30-5.40

## CLONE TARGET
Commercial target as of 2026-03-24:
- 7.5% ABV
- 32 IBU
- Scottish-style ale positioning
- tasting-note direction: roasted biscuit, toffee, caramel, molasses
- brewery note: brewed with 10 unique malts

## FORMULATION LOGIC
Source-backed:
- Base malt must carry the beer.
- Biscuit/Victory needs restraint or it overwhelms.
- Amber and brown can add dry toast/nut/bread depth.
- Black malt should be a razor-thin structural/color tool, not a flavor pillar.

Inference for this draft:
- Use a clean American-style fermentation path rather than a highly expressive English profile.
- Build layered malt complexity from pale ale malt plus toasted and caramel malts.
- Keep hop flavor nearly absent; use bitterness only to shape the finish.

## FERMENTABLES
- Maris Otter or other English Pale Ale Malt: 10.90 lb (4.94 kg)
- Light Munich Malt (8-10L): 1.20 lb (0.54 kg)
- Amber Malt: 0.50 lb (0.23 kg)
- Biscuit/Victory Malt: 0.35 lb (0.16 kg)
- Brown Malt: 0.30 lb (0.14 kg)
- Crystal 60L: 0.55 lb (0.25 kg)
- Crystal 120L: 0.30 lb (0.14 kg)
- Special B: 0.20 lb (0.09 kg)
- Pale Chocolate Malt: 0.15 lb (0.07 kg)
- Black Malt: 0.05 lb (0.02 kg)

Total grist:
- 14.50 lb (6.58 kg)

## GRAIN BILL RATIONALE
- Pale ale malt provides the depth and bread foundation a neutral 2-row base would not.
- Munich supplies rich malt weight without forcing sweetness.
- Amber, biscuit, and brown create the roasted-biscuit / baked-bread / nutty structure the commercial description implies.
- Crystal is split so the beer gets toffee and darker caramel without relying on one blunt crystal note.
- Pale chocolate and black are present only to tighten the dark edge and color.

## PARAMETER SANITY CHECK
OG math at 72% brewhouse efficiency, 5.0 gal into fermenter:
- Estimated total gravity points from grist: ~370
- 370 / 5.0 = 74 points
- Predicted OG: ~1.074

FG math using house Chico strain attenuation range (78-82%) from libraries/yeast_library.md:
- At 78% apparent attenuation: 74 x 0.22 = 16.3 points remaining -> FG ~1.016
- At 80% apparent attenuation: FG ~1.015
- This draft intentionally targets the lower end of Chico attenuation via mash design and cool early fermentation to preserve clone-like richness.

## HOPS
Primary schedule (clone-safe, low-hop-expression):
- Magnum, 12% AA, 60 min: 0.75 oz (21 g)
- East Kent Goldings, 5% AA, 20 min: 0.25 oz (7 g)

IBU note:
- At typical Tinseth assumptions for this gravity and volume, this lands around 32 IBU.
- Recalculate with actual lot AA before brewing.

## YEAST AND PITCHING
Primary:
- Chico (US-05 equivalent) from house library

Why this strain:
- Cleaner than the house English Ale option
- Better chance of matching a modern American craft Scottish strong ale interpretation
- Lower risk of 1968-type under-attenuation and excess ester drift

Pitch target:
- ~260B cells for 5.0 gal at 1.075

Starter / prep guidance:
- Fresh liquid culture: build to roughly 260B cells
- Dry yeast: use two fresh packs if using a dry Chico-equivalent route
- Oxygenate once at knockout; do not re-oxygenate after fermentation is underway

## WATER (RO BUILD, MALT-SUPPORTIVE BUT NOT SWEET)
Target profile (ppm):
- Ca: ~65
- Mg: ~5
- Na: 0-15
- Cl: ~75
- SO4: ~70
- HCO3: 0-20

For total brewing liquor ~10.0 gal (37.9 L), starting from RO:
- Gypsum (CaSO4): 0.12 oz (3.5 g)
- Calcium Chloride (CaCl2): 0.21 oz (6.0 g)
- Epsom Salt (MgSO4): 0.07 oz (2.0 g)

Water notes:
- This is not a house style target; it is specific to this recipe.
- Do not add chalk by default.
- Measure mash pH 10-15 min after mash-in and correct only if needed.

## VOLUME PLAN (G40 CALIBRATED)
Using equipment profile boil-off 1.76 gal/hr with 90 min boil:
- Total liquor target: ~10.0 gal (37.9 L)
- Pre-boil target: ~8.3-8.4 gal (31.4-31.8 L)
- Post-boil target (pre-chill): ~5.7 gal (21.6 L)
- Into fermenter target: 5.0 gal (19.0 L)

## MASH PROGRAM
- Mash in for 154.0F (67.8C) and hold 60 min
- Mash out 168.0F (75.6C) for 10 min

Process checks:
- 10-15 min into mash: measure room-temp pH and correct to 5.30-5.40
- Keep recirculation steady and avoid compacting the basket

Why this mash:
- The clone needs body and finish richness
- Lower rests risk drying the beer past the commercial target

## BOIL
- Duration: 90 min
- No sugar additions
- Keep late hopping restrained
- Do not chase kettle caramelization theatrics; the grist should carry the malt complexity

## FERMENTATION SCHEDULE
1. Chill to 62.0F (16.7C), oxygenate once, and pitch full yeast charge.
2. Hold 62.0-63.0F (16.7-17.2C) for the first 72 hours.
3. Allow rise to 65.0-66.0F (18.3-18.9C) through terminal gravity.
4. When gravity is within 2 points of expected finish, raise to 67.0-68.0F (19.4-20.0C) for cleanup.
5. After terminal gravity is stable for 2 days, crash to 42.0F (5.6C), aligned to the validated GF30 floor.
6. Hold cold 7-14 days before packaging; longer conditioning is acceptable if flavor remains bright and clean.

## PACKAGING + CLONE SCORING CHECKPOINTS
- Closed transfer only
- Carbonation target: 2.1-2.3 vols
- Package only after the beer reads rich and smooth, not rough or yeasty
- Side-by-side against a fresh commercial Robert the Bruce before any next recipe move is mandatory

## WHAT TO WATCH IN CALIBRATION
- If the beer reads too sweet:
  - reduce Crystal 120 or Special B first
  - or move chloride down slightly before changing base malt
- If the beer reads too dry:
  - reduce bittering slightly or increase Munich modestly
- If the beer reads too roasty:
  - cut black malt first, then pale chocolate
- If the beer lacks the "roasted biscuit" signature:
  - increase amber slightly before increasing biscuit/Victory
- If the beer reads too English:
  - tighten fermentation temperature and keep Chico as the house path

## CRITICAL RISKS TO AVOID
- Overusing biscuit/Victory and creating a dry peanut-shell note
- Too much dark crystal causing syrupy finish
- Too much black malt drifting toward porter
- Underbittering the beer and losing structure
- Fermentation roughness from underpitching or warm early fermentation

## NEXT ITERATION NOTES PLACEHOLDER
- Parent recipe: none; this is the first in-development clone draft
- What changed: n/a
- Why: n/a
- Expected outcome: clone baseline should land close on bitterness, malt depth, and finish without over-roast or cloying sweetness
- Actual outcome: fill post-brew
- Verdict: fill post-brew
