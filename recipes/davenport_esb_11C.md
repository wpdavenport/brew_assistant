# Davenport ESB (Fuller's Clone - Clone-Forward Iteration)

## INTENT
Competition-calibrated Fuller's ESB clone iteration targeting a more authentic house-signature profile: layered English malt, smooth firm bitterness, expressive 1968-type fermentation, and a clearer orange-marmalade hop/ester interplay than Copper Crown Batch 1.

## COMPETITION ENTRY
- BJCP Category: 11C Strong Bitter
- Declared Commercial Example: Fuller's ESB
- Declared Base Style: 11C Strong Bitter

## TARGET PARAMETERS
- OG: 1.057
- FG: 1.013
- ABV: 5.8%
- IBU: ~37
- Color: 11 SRM
- Mash pH (room temp): 5.30

## FERMENTABLES
- 9.04 lb (4.10 kg) Maris Otter Pale Malt
- 0.62 lb (0.28 kg) English Medium Crystal Malt (Thomas Fawcett)
- 0.35 lb (0.16 kg) UK Amber Malt
- 0.18 lb (0.08 kg) Torrified Wheat
- 0.35 lb (0.16 kg) Invert Sugar No.2 (add at 10 min left in boil)

## HOPS (TARGET: ~37 IBU)
Note: East Kent Goldings is now listed in `libraries/inventory/stock.json` at 6.1% AA. Rebalance late-addition weights if a future lot differs materially.

### Boil / Whirlpool
- 0.88 oz (25 g) Target (9.6% AA) - 60 min
- 0.35 oz (10 g) Northdown (7.3% AA) - 20 min
- 0.53 oz (15 g) East Kent Goldings (6.1% AA) - 20 min
- 0.53 oz (15 g) East Kent Goldings (6.1% AA) - 10 min
- 0.53 oz (15 g) East Kent Goldings (6.1% AA) - flameout, 10 min steep

### Kettle Additions
- Whirlfloc: 1 tablet at 10 min

## YEAST
- Wyeast 1968 London ESB Ale (G1 repitch from fridge slurry) or WLP002 equivalent
- Target pitch: ~200B cells for 5.0 gal (19.0 L) at OG 1.057
- Track generation every batch: `G0` = fresh pack, `G1+` = repitch.
- Record repitch source batch ID/date.

## STARTER PLAN (D-2 TO D-1)
- Preferred plan: direct pitch healthy `G1` Wyeast 1968 slurry from cold storage
- If slurry age/health is uncertain: build a small vitality starter instead of assuming a fresh pack
- Optional Zinc Buddy: label dose only
- Direct pitch target: enough fresh slurry to reach ~200B cells
- Vitality starter fallback: ~1.0 L, 18-24 hr, then decant and pitch active slurry on brew day

## WATER PROFILE (RO SOURCE)
Total brewing liquor for this recipe: 8.45 gal (32.0 L)

Target ions (approx):
- Ca: 90 ppm
- Mg: 4 ppm
- Na: 15 ppm
- SO4: 115 ppm
- Cl: 90 ppm
- HCO3: 40 ppm

Salt additions for 8.45 gal total liquor:
- 0.18 oz (5.0 g) Gypsum (CaSO4)
- 0.22 oz (6.1 g) Calcium Chloride (CaCl2)
- 0.04 oz (1.1 g) Epsom Salt (MgSO4)
- Acid adjust to mash pH 5.30 as needed

## BREW DAY PROCESS (FULL-VOLUME NO-SPARGE)
1. Measure 8.45 gal (32.0 L) RO liquor.
2. Add all salts to total liquor and mix thoroughly.
3. Heat to strike temperature and mash in.
4. Mash 60 minutes at 151.0 F (66.1 C).
5. Mash out 10 minutes at 168.0 F (75.6 C).
6. At 10-15 minutes into mash, cool sample and measure pH (room-temp read), target 5.30.
7. Drain basket ~8-12 minutes. Avoid aggressive squeezing/pressing.
8. Pre-boil targets: 7.2-7.4 gal and 1.042-1.044.
9. Boil 60 minutes and run hop schedule as written.
10. At 10 minutes left, add Invert Sugar No.2 + Whirlfloc + EKG.
11. Flameout: add EKG and steep 10 minutes.
12. Chill to 65.0 F (18.3 C), transfer clear wort, oxygenate once (60-90 sec), pitch decanted starter slurry.

## FERMENTATION SCHEDULE
1. Day 0-2: hold 65.0-66.0 F (18.3-18.9 C).
2. Day 3-4: let rise to 67.0-68.0 F (19.4-20.0 C).
3. Day 5-7: hold 68.0 F (20.0 C), gently rouse yeast once if gravity movement slows.
4. Day 7-9: verify stable terminal gravity and perform forced VDK check before crash decision.
5. Crash to 42 F (5.6 C) for 48-72 hr only after stable terminal gravity and clean VDK.

## PACKAGING + COMPETITION CHECKPOINTS
- Closed transfer only.
- Carbonation target: 1.9-2.1 vols CO2.
- No packaging until terminal gravity is stable for 48 hr and forced VDK is clean.
- Best judging window: 3-6 weeks post-package.

## CLONE-SPECIFIC EXECUTION NOTES
- Keep late-hop expression English and orange-leaning, not modern citrus.
- Do not ferment too cold for the full primary; Fuller's-like character needs restrained but present ester development.
- Keep the finish rounded, not minerally; this profile is intentionally softer than Copper Crown Batch 1.
- Serve and evaluate at 50-55 F (10-12.8 C); over-chilling hides marmalade and ester interplay.

## CRITICAL RISKS TO AVOID
- Premature yeast drop and diacetyl carryover (1968/WLP002 risk).
- Over-squeezing grain bed and creating harsh bitterness/mineral bite.
- Late hop drift that reads floral-herbal only, without the orange-marmalade clone cue.
- Oxygen pickup post-pitch or during transfer/packaging.
