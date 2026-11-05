# 02 — Verdicts and Worlds

**Owns:** the verdict taxonomy, the meaning of each verdict, and the decision rules. Part 11 enforces these rules on the submitted result in code; part 12 encodes the verdict in the data contract; part 13 only displays it.

## 1. The measured quantity

Everything reduces to one primary measurement, produced by code (never estimated by a model):

- **Apparent gravity** `g_app ± σ` (m/s²): the acceleration fitted to the unsupported (or vertical, on a wall) segment, converted from pixels using the measured scale, **assuming the clip plays at its true speed**.
- Where relevant, a **clock rate**: the measured rate of an independent natural rhythm in the scene (see §4), expressed as the playback stretch it implies.

Playback convention. Let `s` = presented duration ÷ real duration (`s > 1`: slowed down; `s < 1`: sped up). Retiming stretches all durations by `s`, so accelerations scale by `1/s²`:

```
g_app = g_true / s²        ⇒        s = sqrt(g_true / g_app)
```

Display wording uses factors > 1 in both directions: "Slowed down ×1.5" means `s = 1.5`; "Sped up ×1.5" means the clip plays 1.5× too fast, `s = 1/1.5`.

## 2. Candidate worlds come from the scene

Reference gravities (m/s²): **Earth 9.81, Moon 1.62, Mars 3.71**. (This table is physics, not a hint: it defines the worlds, never which one applies.)

The agent must **not** test every world against every clip. It first determines, **from what is visible in the frames**, which worlds are plausible candidates, and must state, for each world it rules out, **what in the frames rules it out**. Example: a street scene with trees, wind-blown foliage, and people walking normally rules out the Moon; a suited astronaut on a grey regolith plain with a black sky rules out Earth and Mars as *locations* (Earth/Mars gravity could still be *simulated* there only via retiming — which is exactly what §3 tests).

The ruled-out-worlds-with-evidence list is a mandatory part of the result (checked in part 11, displayed in part 13). A verdict that names a world inconsistent with its own scene analysis is invalid.

## 3. Verdict taxonomy

Every analysis ends in exactly one verdict. The verdict always displays **the number and the world/factor**, e.g. "g = 1.73 ± 0.23 m/s², fits Moon (Earth ruled out)".

| Label (as displayed) | Meaning | Requires |
|---|---|---|
| **Moon gravity** — or whichever world fits: *Earth gravity / Mars gravity / Moon gravity* | At native speed, `g_app` fits exactly one scene-allowed world, and all other worlds are excluded (by fit and/or by scene evidence). | §4 fit test passed for one allowed world; no unresolved ambiguity. |
| **Slowed down ×k** / **Sped up ×k** | No scene-allowed world fits at native speed, but one scene-allowed world fits under a single global retiming `s`, **and** the retiming is corroborated per §5. | Unique allowed world (or unique fit) under retiming + clock corroboration per §5. |
| **Physically impossible** | No scene-allowed world at **any** single playback speed explains the motion — because the independent clock is normal, or the retiming that would fix gravity would make the clock unnatural (§5), or the motion violates the vertical-surface rule outright (part 01 §4). | Clock evidence, or an outright rule violation > threshold (part 03 sets the test's threshold). |
| **Undetermined** | Measurement was impossible, too imprecise to separate the candidates, ambiguous between retiming and impossibility, or stopped by budget. **Always with a reason** (e.g. "undetermined: no scale reference", "undetermined: budget"). | A stated reason from the controlled list in part 11/12. |

There is no fifth outcome and no confidence percentage. Uncertainty is expressed through `σ` and through abstention.

## 4. Fit test (at any candidate speed)

A world `W` fits `g_app ± σ` at stretch `s` if the retimed measurement agrees with `g_W` within combined uncertainty — operationally `|g_app · s² − g_W| ≤ 2σ` (with `σ` scaled by `s²` likewise) **and** `σ` is small enough that the fit separates `W` from every other scene-allowed world. If two allowed worlds both fit, or `σ` is too large to separate them, the outcome is **undetermined (ambiguous)**, never a coin flip.

## 5. The independent-clock rule (retimed vs. impossible)

"No world fits at native speed" never, by itself, means "retimed". A retiming claim needs an **independent clock**: something in the scene with a known natural rhythm that retiming would distort equally — people's step rate/cadence, a pendulum, dripping/swinging objects, rotor rates, etc. The clock is measured by code like everything else and implies its own stretch `s_clock ± σ_clock`.

Decision logic, in order:

1. **A scene-allowed world fits at `s = 1`** → that world's verdict (subject to §4).
2. **No allowed world fits at `s = 1`, and a clock exists:**
   - Compute `s_grav` (the stretch that would make `g_app` fit an allowed world) and `s_clock`.
   - If they **agree** within combined uncertainties for a unique allowed world → **Slowed down / Sped up ×k**.
   - If the clock reads **normal** (`s_clock` consistent with 1) → **Physically impossible**: the motion would need a retiming the clock contradicts.
   - If applying `s_grav` would make the clock **unnatural** (the clock's corrected rate falls outside its plausible natural range) → **Physically impossible**.
3. **No allowed world fits at `s = 1`, and no clock exists:**
   - If the scene alone pins **exactly one** plausible world (e.g. the lunar surface) and the implied `s` is physically sensible → **Slowed down / Sped up ×k**, with the result explicitly noting that no independent clock was available. (This is the Apollo-B case; see part 03.)
   - Otherwise → **Undetermined**: retiming-to-an-unknown-world and impossibility cannot be separated honestly.
4. **Outright violation:** a segment that breaks the governing rule directly (e.g. vertical motion along a wall that deviates from `g` far beyond uncertainty while in contact, per part 01 §4) with a normal clock → **Physically impossible**, regardless of the above.

Where a clip contains multiple measurable segments (e.g. free flight *and* a wall segment), each segment is tested; the overall verdict is the strongest supported conclusion, and any segment-level disagreement that cannot be reconciled yields undetermined, not cherry-picking (part 11 checks this).

## 6. What every verdict must be accompanied by

- `g_app ± σ` and how it was measured (segment, scale, provenance — part 12).
- The scene analysis: candidate worlds, and for each excluded world the visual evidence excluding it.
- If retimed: the factor `k`, the world it retimes *to*, and the clock evidence (or the explicit "no clock available; scene-pinned world" note).
- If impossible: which constraint kills every world/speed (clock reading, or the violated rule and by how many σ).
- If undetermined: the reason.

## 7. Wording rules for display (binding on part 13)

- Show the number and the label together; never the label alone, never a bare number.
- "Physically impossible" is a physics claim, not a fakery claim: display copy must phrase it as *"no world at any playback speed explains this motion"*, never as "fake".
- "Undetermined" must display its reason in plain words next to the label.

## 8. Owner addendum (2026-10-29): one world from the scene; realistic or not

Part 01's addendum of 2026-10-29 makes the clip's own question the product's question. For verdicts that means:

- **One world, from the scene (replaces §2's listing).** The scene names exactly one world, and `worlds.candidates` holds that world only; `worlds.excluded` stays empty. A second candidate is added only when the clip's question itself names a second world; it is then tested like the first, never "ruled out by the scene". No world is listed just to be excluded.
- **The decision logic of §5 is unchanged**, run over that one world.
- **Display wording (replaces the label column of §3; the four kinds stay):**

  | Kind | Label | Example |
  |---|---|---|
  | world fit at native speed | **Realistic on Earth** (on the Moon, on Mars) | "Realistic on the Moon: g = 1.66 ± 0.22 m/s², the Moon's 1.62 within 0.2σ" |
  | retimed | **Not realistic at this speed: slowed down ×k** (or sped up) | "Not realistic at this speed: slowed down ×1.5; at real speed it fits the Moon (clock agrees)" |
  | impossible | **Not realistic on Earth** (the scene's world) | "Not realistic on Earth: the wall segment breaks free fall by 6σ under a normal clock" |
  | undetermined | **Undetermined** | "Undetermined: scale rests on one reference" |

- **§7 still binds:** the label always comes with the number; "not realistic" is a physics claim, never "fake"; it is glossed as "no playback speed makes this motion fit the scene's world".

## 9. Owner addendum (2026-10-29): range checks and how parts combine

Part 01's second addendum of 2026-10-29 adds range checks: one measured quantity against a sourced real range.

- **One range check:** measured `value ± σ` against `[min, max]` from a source. **Inside:** the 2σ interval `[value − 2σ, value + 2σ]` overlaps `[min, max]`. **Outside:** the whole 2σ interval lies beyond `min` or beyond `max`; the distance of the measured value from the nearer bound is reported in σ ("48 ± 2 % is 2.5σ below the human minimum of 53 %"); outside means that distance exceeds 2. A range check with no measured value or no sourced bound is not counted.
- **Combining parts into the verdict** (the gravity part is §3–§5 over the scene's world; each range check is one part):
  - any part not realistic (gravity `impossible`, or a range check outside) → kind `impossible`, label "Not realistic on <world>", reason naming that part;
  - gravity `retimed` with no range check outside → kind `retimed` as before;
  - at least one part realistic (gravity `world` fit, or a range check inside) and none not realistic → kind `world`, label "Realistic on <world>";
  - otherwise → `undetermined` with the reason of the first undetermined part.
- **Labels and numbers:** a verdict decided by a range check shows that check's number with its range ("palm/hand 48 % ± 2 %, human range 53–68 %"); `g_measured` and `sigma_g` are null when there is no gravity part.
