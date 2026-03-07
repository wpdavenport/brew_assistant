# Old Crown Lazy Lager - BOS Upgrade v2 (BJCP 3C)

## SOURCE IMPORT
- Imported from: `recipes/beer_xml_imports/old crown lazy lager.bsmx`
- Original style tag: Czech Premium Pale Lager (BJCP 2021 3C)
- Original recipe baseline:
  - 100% Bohemian Pils malt
  - Saaz-only hop bill
  - OG target ~1.050
  - 60 min boil, 148.0F (64.4C) mash

## INTENT
Turn the imported recipe into a competition-ready 3C Czech Premium Pale Lager by tightening bitterness quality, malt depth, fermentation cleanliness, and repeatability on the Grainfather G40 + GF30 setup.

This update explicitly separates:
- BOS path (style-authentic, requires buying fresh Saaz + lager yeast)
- Stock-aware fallback path (brewable with current hop inventory, but less clone-authentic)

## TARGET PARAMETERS
- Style: BJCP 2021 3C Czech Premium Pale Lager
- Batch size (into fermenter): 5.0 gal (19.0 L)
- OG: 1.050
- FG: 1.012-1.014
- ABV: 4.8-5.1%
- IBU: 38-42 (firm but rounded)
- SRM: 4-5
- Carbonation: 2.4-2.6 vols
- Mash pH (room temp): 5.30-5.40

## FERMENTABLES
Base grist (recommended):
- Bohemian Pilsner Malt: 9.30 lb (4.22 kg)
- Light Munich Malt (6-10L): 0.50 lb (0.23 kg)

Optional foam-boost variant (if desired):
- Bohemian Pilsner Malt: 9.10 lb (4.13 kg)
- Light Munich Malt (6-10L): 0.50 lb (0.23 kg)
- Chit Malt: 0.20 lb (0.09 kg) (~2%)

Notes:
- Small Munich addition increases malt depth without drifting out of 3C.
- Keep color and toast low; this is still a pale lager.
- Chit malt is optional, not mandatory. Use it only if you consistently miss foam/head goals.

## HOPS - BOS PRIMARY (AUTHENTIC 3C)
Use fresh Czech Saaz, target lot AA ~3.5-4.5% (do not use old low-AA stock for BOS path).

- 60 min: Saaz 1.70 oz (48 g)
- 30 min: Saaz 1.10 oz (31 g)
- 10 min: Saaz 0.70 oz (20 g)
- Whirlpool at 170.0F (76.7C) for 15 min: Saaz 0.70 oz (20 g)

## HOPS - STOCK FALLBACK (CURRENT INVENTORY)
Current stock has Saaz lot around 2.2% AA and only ~3.85 oz (109 g).  
If brewing now without buying hops:

- 60 min: Warrior 0.25 oz (7 g) (14.2% AA)
- 30 min: Saaz 1.75 oz (50 g) (2.2% AA)
- 10 min: Saaz 1.00 oz (28 g) (2.2% AA)
- Whirlpool at 170.0F (76.7C) for 15 min: Saaz 1.10 oz (31 g) (2.2% AA)

Notes:
- This fallback preserves noble late-hop character, but bittering is less style-authentic than all-Saaz.
- This path is brewable with current stock, but not the preferred BOS path.
- Recalculate IBUs in your software with actual lot AA before brew day and adjust bittering if needed.

## YEAST AND PITCHING
Primary (authentic/BOS):
- Czech lager strain (e.g., WY2278 / WLP802 class), fresh and healthy

House fallback:
- German lager 34/70-type strain from house library

Pitch target:
- ~350B cells for 5.0 gal (19.0 L) at 1.050

Starter / prep guardrails:
- Liquid yeast: build starter to reach ~350B cells (often ~2.0-2.5 L total depending on freshness).
- Dry yeast option: 2 rehydrated packs minimum; 3 packs for conservative competition pitch.
- Vitality starter: use when yeast age/viability is uncertain (especially for repitches older than ~7 days).
- Avoid using ale strains for this recipe if the target is true 3C medal profile.
- Log yeast generation every batch (G0 fresh pack, G1+ repitch) and source batch/date for any repitch.

## WATER (RO BUILD, SOFT + ROUNDED BITTERNESS)
Target profile (ppm):
- Ca 45
- Mg 5
- Na 0-10
- Cl 50-55
- SO4 50-60
- HCO3 0-30

For total brewing liquor ~9.5 gal (36.0 L), starting from RO:
- Gypsum (CaSO4): 0.08 oz (2.3 g)
- Calcium Chloride (CaCl2): 0.14 oz (4.0 g)
- Epsom Salt (MgSO4): 0.07 oz (1.9 g)

Water note:
- Keep sulfate restrained; if bitterness reads sharp, reduce sulfate first before changing hop schedule.

## VOLUME PLAN (G40 CALIBRATED)
Using equipment profile boil-off 1.76 gal/hr with 90 min boil:
- Post-boil target (pre-chill): ~5.7 gal (21.6 L)
- Pre-boil target: ~8.3 gal (31.6 L)
- Total liquor target: ~9.5 gal (36.0 L)

## MASH PROGRAM (COMPETITION BIAS)
Hochkurz-style step mash (recommended on G40 for malt complexity + attenuation control):
1. 144.0F (62.2C) for 20 min
2. 152.0F (66.7C) for 40 min
3. 168.0F (75.6C) for 10 min mash out

Process checks:
- 10-15 min into mash: measure room-temp pH and correct to 5.30-5.40.
- Keep recirculation steady to avoid channeling.

Optional German technique:
- If you want additional malt depth, run a short single decoction: pull thick mash (~25%), boil ~10 min, return to hit second rest.
- This is optional; do not add complexity if repeatability is your priority.

## BOIL
- Duration: 90 min
- Start hop timing when 60 min remain in the boil; keep all hop additions at their listed times.
- Add hops exactly on the selected schedule (BOS or stock-fallback).
- No sugar additions.
- Whirlpool charge at 170.0F (76.7C), hold 15 min.

## FERMENTATION SCHEDULE
1. Chill to 48.0-50.0F (8.9-10.0C), oxygenate once at pitch to ~8-10 ppm dissolved O2.
2. Hold 50.0F (10.0C) through active primary until ~50-60% apparent attenuation (about SG 1.028-1.032 for this recipe), not by fixed day count.
3. Raise to 58.0-60.0F (14.4-15.6C) and hold until terminal gravity is reached and stable for 2 days.
4. Run warm forced VDK check; if any butter/butterscotch remains, hold warm and re-check in 24 hr.
5. Crash to 34.0F (1.1C) after clean VDK, hold 48-72 hr.
6. Lager at 34.0-36.0F (1.1-2.2C) for 4-6 weeks before competition service.

## PACKAGING + COMPETITION GATE
- Closed transfer only.
- Carbonation target: 2.4-2.6 vols.
- Competition gate requirements:
  - No detectable diacetyl.
  - Firm, clean bitterness (no harsh sulfate bite).
  - Rich but clean bready malt character.
  - Brilliant clarity and lasting white head.

## WHY THIS SHOULD SCORE HIGHER THAN THE IMPORTED VERSION
- Better malt layering: slight Munich support instead of one-dimensional base-only profile.
- Better bitterness structure: still noble-led, but shaped for smooth firmness.
- Cleaner fermentation execution: explicit VDK gate + lagering window.
- Process tuned to your calibrated boil-off and full-volume G40 workflow.

## SHOPPING LIST FOR TRUE BOS PATH (FROM CURRENT STOCK STATE)
- Fresh Czech Saaz to support full all-Saaz schedule (current stock is low-AA and short for BOS plan).
- True lager yeast (Czech lager preferred, or clean German lager fallback) since current stock is ale-focused.
