# House Brewing Calculations (Authoritative)

Use these formulas and conventions whenever calculations are needed. If project files provide different assumptions, follow the project files.

---

## Units & Conventions
- 1 gal = 3.785 L
- °C = (°F − 32) × 5/9
- Points = (SG − 1.000) × 1000
- °P (approx) = 259 − (259 / SG)
- Report gravity as SG (and °P if helpful)

Default assumptions unless overridden in profiles/equipment.yaml:
- Batch size: 5.0 gal (19 L)
- Brewhouse efficiency: 70%
- Boil time: 60 min
- Typical homebrew losses apply if not specified

---

## ABV
### Basic ABV (good default)
ABV% = (OG − FG) × 131.25

Example intermediate reporting:
- OG 1.060, FG 1.012
- Δ = 0.048
- ABV = 0.048 × 131.25 = 6.30%

---

## Apparent Attenuation
Apparent Attenuation % = (OG_points − FG_points) / OG_points × 100

Example:
- OG 1.060 → 60 pts
- FG 1.012 → 12 pts
- AA% = (60 − 12)/60 × 100 = 80%

---

## Strike Water Volume (mash thickness method)
Given:
- Mash thickness T (qt/lb)
- Grain weight G (lb)

Strike volume (qt) = T × G  
Strike volume (gal) = (T × G) / 4

Typical default mash thickness (unless overridden): 1.5 qt/lb

---

## Strike Water Temperature (infusion approximation)
T_strike = (0.2 / R) × (T_target − T_grain) + T_target

Where:
- R = qt/lb
- T_grain = grain temp (°F), assume 68°F (20°C) if unknown
- T_target = desired mash rest temp (°F)

Note: This is an approximation. For systems with known thermal mass, prefer calibrated values.

---

## Pre-boil Volume
Pre-boil volume = Target into fermenter
+ trub_loss
+ kettle_deadspace
+ boil_off_rate × (boil_time_hr)

All values should come from profiles/equipment.yaml when available.

---

## Dilution / Gravity Adjustment
### Points-based dilution
Total points = Volume_gal × Points

If you have current volume V1 and gravity P1, and want target gravity P2:
V2 = (V1 × P1) / P2

Water to add = V2 − V1

---

## Carbonation (Priming Sugar)
Use as a starting point; prefer a priming calculator for final numbers if needed.

Rule of thumb (corn sugar / dextrose):
- ~0.5 oz per gal per additional 1.0 vol CO2 (approximate)

Because temperature, residual CO2, and sugar type matter, if bottling:
- Ask for beer temperature at packaging and target vols CO2
- Then calculate precisely (or direct to a known priming table)

---

## Water Chemistry: ppm and salt additions (high-level)
ppm = (mg/L)

To increase a mineral by X ppm in volume V (L):
Total mg needed = X × V

Then convert mg to grams: grams = mg / 1000

Common salts (for reference; use carefully):
- Gypsum: CaSO4·2H2O (adds Ca and SO4)
- Calcium chloride: CaCl2·2H2O (adds Ca and Cl)
- Epsom salt: MgSO4·7H2O (adds Mg and SO4)
- Baking soda: NaHCO3 (adds Na and HCO3)
- Chalk: CaCO3 (poorly soluble; only with CO2/acid management)

Important:
- Always state the target profile (ppm) and the reason (flavor balance, mash pH).
- If mash pH is a priority and alkalinity is unknown/variable, recommend measuring mash pH.

---

## IBU
IBU depends heavily on model and utilization assumptions.
If no software is used:
- Provide a conservative estimate and encourage verifying in a calculator.
- State the utilization model assumption if you compute (e.g., Tinseth).

If you do compute:
- Show inputs: AA%, hop weight, boil time, post-boil volume, OG
- Show intermediate utilization and final IBU

---

## Reporting standard (what to show)
When you calculate:
1) Formula
2) Inputs
3) Intermediate result (brief)
4) Final result