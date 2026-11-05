# 13 — Player Template

**Owns:** `player/` (the frozen static template) and `src/pagebuild/` (per-clip page build + gallery build, invoked by part 15). **This part reproduces a specific prototype the owner built and approved for the Moon jump.** Where this part describes appearance or behaviour, it is normative — "reproduces this experience" means these elements, in these places, with these colours. The rejected first attempt (a web page with a side menu, paragraphs of calculation, overlays not sitting on the video) is the anti-pattern.

The player contains no physics and no verdict logic: every number it prints is in `result.json`/`summary.json` (part 12) or is pure display arithmetic over them (percentages of σ², frame↔time at the measured fps).

## 0. The approved look (binding visual reference)

The owner approved this look. Muse Wonder wrote the description below from the approved screenshots; the images themselves are not part of this repository. It is the visual target for every state, at 1440×900 and in the stacked phone layout. **Precedence:**
- for visual style (layout, sizes, fonts, colours, opacity, placement, what each state shows), §0 wins over older wording in §§1–12;
- for behaviour and data, §§13–17 win. In particular:
  - number formats follow §13 and §17.7;
  - calculation steps are grouped by event per §17.8; the step names in §0 are examples;
  - chronophotograph figures are spread left to right by time per §17.5, with height real.
- Data seen in the screenshots (clip B, a second jump, ground-truth reveal, side-by-side) appears only when the result has it (§§10–11).

### 0.1 Page layout, 1440×900 viewport

| Region | Position / size (px) | Size (% viewport) | Style |
|---|---|---|---|
| Page | 0,0 – 1440×900 | 100×100% | bg ≈`#04070C`; no page scroll in single-clip view |
| Header | x≈0, y≈0, 1440×≈56 px | 100% × ≈6.2% | bg ≈`#060B13`; bottom border 1px ≈`#162233` |
| Header title | x≈24, centred vertically | — | left-aligned, never wraps |
| Tabs | start x≈310, same row as title | — | items ≈28 px apart; active item has 2px cyan underline, offset ≈14 px below text |
| Stage (single clip) | x≈18, y≈70, w≈985, h≈738 | 1.3%,7.8%; 68.4% × 82.0% | radius ≈4 px; border 1px ≈`#1B2A3C`; bg `#000`; `overflow:hidden` |
| Side panel | x≈1015, y≈70, w≈407, h≈738 | 70.5%,7.8%; 28.3% × 82.0% | radius ≈4 px; border 1px ≈`#1B2A3C`; bg ≈`#070C14` |
| Gap stage↔panel | ≈12 px | ≈0.8% | page bg shows through |
| Control bar (single clip) | x≈18, y≈822, w≈985, h≈52 | 1.3%,91.3%; 68.4% × 5.8% | no card; controls on page bg; vertically centred |
| Control bar, side-by-side | x≈18, w≈1404 | 97.5% wide | spans both stages |

- Side-by-side: two stages each ≈49.2% of content width, gap ≈12 px, height ≈56% viewport; below them control bar, then two panels side-by-side each ≈49.2% wide, height ≈27% viewport. No right sidebar in this view.
- Vertical/stacked variant (phone width, e.g. 390×844): single column, full-width stage (≈16:10 crop preserved), then chart panel, then steps; control bar sticky at bottom; header replaced by large title block above stage. Same colours/type as desktop.
- Intro, Scale, Apex, Landing, Verdict states do **not** resize stage, panel, or control bar; only overlays inside them change.

### 0.2 Typography

Families: sans = system sans / Inter-like (`-apple-system,"Segoe UI",Roboto`); mono = ui-monospace / JetBrains-Mono-like; maths = serif italic (KaTeX/Times-like). No other families.

| Role | Font | Size | Weight | Case / colour |
|---|---|---|---|---|
| Header title | sans | ≈16 px | 700 | sentence case, `#E8EEF4` |
| Tabs | sans | ≈13 px | 400 (active 500) | sentence case; active `#E8EEF4`, inactive ≈`#7A8798`; active underline `#4FE3F0` |
| HUD line on video | mono | ≈11 px | 400 | `frame NNN/NNN  t = X.XXX s  NN.NN fps`, `#C7D2DE`; leading status dot Ø≈8 px |
| HUD “Freeze frame” suffix | mono | ≈11 px | 700 | as written, amber ≈`#FFB54D`, ≈12 px gap after fps |
| Badge “SAM N masks” | mono | ≈10 px | 600 | uppercase as shown, cyan `#4FE3F0` |
| Intro headline | sans | ≈42 px | 800 | ≈1.05 line-height, `#EDF3F8`, max 2 lines |
| Intro sub-headline | sans | ≈14 px | 400 | ≈1.5 line-height, ≈`#9AA8B8` |
| Card eyebrow (“What we see”, “By eye…”) | sans | ≈11 px | 400 | sentence case, ≈`#7A8798` |
| Card body | sans | ≈12–13 px | 400–600 | `#D5DEE8`; secondary line ≈11 px `#7A8798` |
| Big eye-estimate numbers | mono | ≈30 px | 700 | format `~X.XX` / `~X.X`, `#EDF3F8` |
| Event title (Scale/Apex/…) | sans | ≈24 px | 700 | title case, `#FFF` |
| Event caption line | sans | ≈13 px | 400; embedded numbers mono 700 `#FFF` | sentence case, ≈`#C7D2DE` |
| Chronophotograph heading | sans | ≈16 px | 700 | `#FFF`; sub-line ≈12 px `#C7D2DE` with mono bold interval |
| Chips/pills on video & verdict | mono | ≈10–11 px | 600 | as written, colours §0.6 |
| Ghost labels, chart end-labels | sans | ≈10–11 px | 600 | `#FFF` on `#000` chip, coloured 3px left bar |
| I-beam / scale value chips | mono | ≈13 px | 700 | black `#0A0A0A` on solid amber |
| Panel headings (chart, steps) | sans | ≈13 px | 700 | title case, `#E8EEF4` |
| Chart unit (top-right) | mono | ≈11 px | 400 | `m / s` spaced, ≈`#7A8798` |
| Chart ticks | mono | ≈9–10 px | 400 | 1 decimal, ≈`#66788C` |
| Step titles | sans | ≈13 px | 700 active / 500 collapsed | active `#E8EEF4`, collapsed ≈`#5F7085` |
| Step frame marker (right) | mono | ≈10 px | 400 | `frame NNN`, ≈`#66788C`, right-aligned |
| Step body / explainer | sans | ≈11–12 px | 400 | ≈1.45 line-height, ≈`#9AA8B8` |
| Formulas | serif italic | ≈14–15 px | 400 | `#D5DEE8`; stacked fractions, subscripts lowered; result `=` in same line |
| Result chips (in steps) | mono | ≈12–13 px | 700 | §4; padding ≈4×8 px |
| Timeline labels above/below | mono/sans | ≈9 px | 400 | ≈`#66788C`, centred on segment |
| Time readout | mono | ≈12 px | 400 | `X.XX / XX.XX s`, `#C7D2DE` |
| Verdict `g =` headline | mono | ≈38–42 px | 700 | value `#FFF`; `± X.XX m/s²` ≈18 px ≈`#8A99AB` |
| Verdict stamp | sans, condensed | ≈30–34 px | 800 | uppercase, §0.3.5 |
| Number formats everywhere | — | — | — | heights `X.XXX ± X.XXX m`; scale `X.XXX ± X.XXX cm/px`; times `X.XX ± X.XX s`; airtime counts integer frames over fps; `g` `X.XX ± X.XX m/s²`; σ as `X.Xσ`; percents `X.X%`; always unit after a space, `±` spaced both sides |

### 0.3 Overlays on the video

Common: HUD top-left inset ≈18 px; badge top-right inset ≈18 px; both sit above video, below no other overlay. Event caption bottom-left inset ≈18 px. All overlay text has either solid/translucent black backing or strong shadow — never bare text on bright video except HUD.

#### 0.3.1 First screen (Intro)
- Video dimmed to ≈35–45% brightness (dark overlay ≈`#04070C` at ≈55% over frame).
- Headline block: x≈5% of stage width, y≈28% of stage height, width ≈62%.
- Below headline, two cards in a row, each ≈49% of a ≈92%-wide row, gap ≈14 px, bg ≈`#0A111C` at ≈88% opacity, border 1px ≈`#22344A`, radius ≈2 px, padding ≈14 px. Left card: eyebrow, bold statement, muted provenance line, then pill chips (mono ≈10 px, 1px border ≈`#3A4F68`, radius ≈10 px, padding ≈3×8 px, transparent bg). Right card: eyebrow, two big mono estimates side-by-side with 10px grey unit labels under each, then muted note.
- CTA button under left card: solid cyan ≈`#4FE3F0`, black 700 sans ≈14 px, padding ≈12×18 px, radius ≈3 px, `▶` glyph + label; muted ≈11 px note text ≈14 px to its right, baseline-aligned.
- No outline, ruler, ghosts, or caption block in this state. Chart shows empty axes (§0.4).

#### 0.3.2 Tracked-body outline (Scale, Apex, Landing, normal playback)
- Outline only, **no fill**: stroke ≈2 px solid cyan `#4FE3F0` following the body mask, plus outer glow ≈6–8 px blur of same colour at ≈50% opacity. Interior remains original video pixels.
- Status dot in HUD is amber ≈`#FFB54D` when frozen at an event, cyan when playing normally.

#### 0.3.3 Scale state
- Vertical ruler: x≈13% of stage width, spanning exactly the reference object's pixel height; stroke 2px amber, end caps ≈10 px wide, intermediate ticks ≈6 px wide every ≈1/5 length, all amber `#FFB54D`.
- Reference outline: the reference object (backpack stack) gets its own amber outline ≈2 px, inside the cyan body outline; bottom edge emphasised ≈3 px.
- Chips stacked left of ruler, left-aligned: (a) solid amber chip, black mono 700 ≈13 px, format `X.XX m = NN px`, padding ≈4×8 px, radius ≈2 px; (b) below it ≈6 px, black translucent chip (≈75%) with 3px amber left bar, white mono ≈12 px, format `1 px = X.XX cm`.
- Takeoff-level line (also Apex/Landing): dashed 1px ≈`#C7D2DE` at ≈50% opacity, full stage width, at takeoff centre-of-mass height; label `takeoff level` mono ≈10 px lowercase ≈`#C7D2DE` right of centre, sitting on the line with dark backing.
- Reference card: top-right, below badge (top ≈17% of stage height), right inset ≈2.5%, width ≈38% of stage; bg ≈`#070C14` at ≈92%, border 1px ≈`#22344A`, top border 2px amber, radius ≈2 px, padding ≈16 px. Contents: 11px grey eyebrow, 14px 700 title, huge mono amber `X.XXX` ≈28 px with `± X.XXX m` grey, 11px grey caption, then two source rows (mono amber value ≈12 px left column ≈28% wide; quoted serif/sans italic text ≈11 px `#9AA8B8` right), a pill `sum of two sources`, final 11px grey confidence line. Long quotes may fade/clip at card bottom — card height fixed by stage, never grows over caption block.
- Caption block (§0.3.6) reads Scale.

#### 0.3.4 Apex state with ghosts
- Real body centre-frame with §0.3.2 outline. Two ghost copies of the same silhouette, same scale (100%), same baseline ground line:
  - Fill and outline numbers below are superseded by the §18.4.5 recipe (§20.1).
  - Earth ghost: offset ≈−1.0 body-width left (partly cropped by stage edge allowed), fill periwinkle ≈`#8A8FFF` at ≈18–22% opacity over desaturated copy, outline ≈1.5 px periwinkle at ≈80%.
  - Moon ghost: offset ≈+1.0 body-width right, fill amber ≈`#FFB54D` at ≈18–22% opacity, outline ≈1.5 px amber at ≈80%.
  - Vertical rule: each ghost is drawn at its model-predicted height at this instant (so ghosts sit at different heights from the real body and from each other); they are **not** feet-aligned copies.
  - Ghost labels: black chip (≈80% opacity), 3px left bar in ghost colour, white 600 ≈11 px text (`Earth`/`Moon`), placed above the ghost's shoulder/head, inset from stage top ≈13% height; never overlapping HUD.
- Centre-of-mass marker: cyan dot Ø≈6 px with glow on real body at hip height; faint dashed horizontal amber line from dot to the right ≈120 px.
- I-beam bracket: left of real body at COM height, vertical amber line ≈2 px with ≈8 px horizontal serifs top/bottom; its height = measured rise. Adjacent solid amber chip (as §0.3.3a) with format `X.XX m`. Bracket does not touch the outline.
- Caption block reads Apex with COM-rise and feet-clearance numbers.

#### 0.3.5 Landing — chronophotograph
- Frame darkened overall to ≈50–60% brightness; the composited figures stay full brightness.
- Figures: Clip-A style ≈5 figures, Clip-B style ≈7–8 figures (one every ≈0.2 s of flight), each at original video scale/position, overlapping neighbours by ≈45–60% of body width, ordered left→right in time. Each figure keeps a ≈1 px cyan outline at ≈60% opacity; fills are the real video cut-outs, slightly translucent where they overlap so later figures remain readable.
- Trajectories drawn over figures at COM height: measured = solid cyan ≈2 px through the dots; Moon model = dashed amber ≈2 px; Earth model = solid periwinkle ≈2 px, ending much earlier/lower. Vertical dotted drop-lines (1px, model colour, ≈60%) from each model's landing point down to the time axis.
- Time axis: 1px ≈`#8A99AB` horizontal line at ≈84% of stage height, width ≈62% of stage, starting under first figure. Ticks below at `0.0 / 0.5 / 1.0 s` (mono ≈10 px grey). Landing labels under axis: black chips with 3px coloured left bar, white ≈11 px, format `Earth X.XX s`, `Moon X.XX s`, `in the clip X.XX s`; labels are **staggered onto two rows** (second row ≈18 px lower) so Earth/Moon/clip labels never collide; each label is horizontally centred on its drop-line tick (coloured dot Ø≈5 px on the axis).
- Heading top-left below HUD: cyan 3px left bar, `Chronophotograph` 16px 700, sub-line 12px `The astronaut every X.XX s. Time runs left to right, height goes up`.
- No event caption block in this state; heading replaces it.

#### 0.3.6 Event caption block (Scale, Apex, and other single events)
- Container bottom-left: bg `#000` at ≈72% opacity, no border, radius 0–2 px.
- Title row: 3px solid left bar (amber for measurement events, cyan for chrono/verdict-adjacent), title 24px 700 white, padding ≈6×12 px, its own black strip.
- Numbers line directly below: ≈13 px, padding ≈6×12 px, format e.g. `PLSS + OPS stack: X.XX m = NN px, so 1 px = X.XX cm`, numbers mono 700 white, text sans ≈`#C7D2DE`.

#### 0.3.7 Verdict card and stamp
- Card: centred horizontally, bottom inset ≈4% of stage height, width ≈88% of stage, bg ≈`#05090F` at ≈94%, border 1px ≈`#2A3C52`, radius ≈2 px, padding ≈20×24 px. Video behind dimmed to ≈30%.
- Inside: 12px grey `Verdict`; `g = X.XX` mono 700 ≈40 px white + `± X.XX m/s²` grey; then a log-scale g-axis (1px ≈`#3A4F68`, ticks at 0.5,1,2,5,10 labelled mono 9px grey, unit `g, m/s²` at right): world pins = dot Ø≈8 px on ≈18 px vertical stem in world colour with 700 12px label above (`Moon X.XX` etc.); measured marker = cyan vertical line ≈22 px with triangle pointer, surrounded by translucent cyan 2σ band rect ≈10 px tall (`band = 2σ` mono 9px grey at left).
- Sentence line 13px `#C7D2DE` under axis; then σ-chips row: pills radius ≈10 px, padding ≈4×10 px, mono ≈11 px, transparent bg, 1px border in world colour, coloured dot, format `Moon X.Xσ ✓` / `Earth NNσ ✗` (✓ in-world colour if within 2σ else ✗ red ≈`#FF5A5A`).
- Divider 1px ≈`#22344A`, then either a `Reveal the ground truth` outline button (1px ≈`#3A4F68`, transparent, 12px `#D5DEE8`, padding ≈8×14 px) or, after reveal, Ground-truth block: 11px grey eyebrow, red ≈`#FF5A5A` 600 ≈13 px statement (wraps ≤2 lines), then 12px `#D5DEE8` line starting cyan `✓`.
- Stamp: absolutely positioned overlapping card's top-right corner, straddling border by ≈50% of its height, rotated ≈−6°, size ≈34% card width × ≈64 px. Double border (≈3 px outer + 1 px inner, distressed/grunge edge), transparent dark fill ≈85%. Text: uppercase 800 ≈32 px, sub-line mono ≈11 px. Moon verdict: amber border/text; Slowed verdict: red ≈`#FF4D4D` border/text. Stamp never covers the `g =` value.
- Side-by-side mini-verdicts: same card scaled down inside each stage bottom (width ≈56% of stage, `g` ≈24 px), stamp ≈45% card width, ≈22 px text.

### 0.4 Side panel

- Internal padding ≈16 px; chart block at top, divider 1px ≈`#162233`, steps below; steps area scrolls vertically, chart fixed.
- Chart: title left 13px 700, unit right mono 11px grey. Plot area height ≈150 px (desktop), ≈200 px vertical variant. Plot bg ≈`#05090F`; gridlines 1px ≈`#141E2C` at each tick; axis line 1px ≈`#22344A`. X ticks: time `0.0…X.X` step 0.5 s; Y ticks: height 1 decimal (may be negative). Tick labels mono ≈9 px ≈`#66788C`, outside plot.
- Curves: measured = cyan dots Ø≈4 px `#4FE3F0` with ≈4 px glow, one per frame; fit = dashed white ≈1.5 px at ≈70% through dots; Moon = dashed amber ≈2 px; Earth = solid periwinkle ≈2 px; Mars (verdict context only) not in this chart. In Intro, plot empty with centred 11px grey text `waiting for takeoff` and a flat 0-line ≈`#3A4F68`.
- End-of-curve labels: black chips (≈85%) with 3px coloured left tick, white ≈10 px, format `Earth X.XX s` / `Moon X.XX s` / `in the clip X.XX s`, placed just below/right of each curve's landing point, offset so they never overlap dots or each other (clip label highest, Earth lowest). Small vertical tick marks (coloured, ≈8 px) mark landing x on the curves. Early Apex state uses tiny inline legend labels (`measured/Moon/Earth`) above curves instead, same chip style, ≈9 px.
- Steps list: vertical timeline rail at x≈8 px: 1px line ≈`#1E2C3E`; node dots Ø≈9 px — active = filled cyan with glow, inactive = hollow 1px ≈`#3A4F68` on panel bg. Step rows separated ≈14 px.
- Expansion rule superseded by §20.2 (passed steps stay open). Former wording, for the look only — expanded vs collapsed per state: Intro → only *Time from frames* expanded. Scale → *Scale* expanded (preceding steps collapsed, partially scrolled). Apex → *Scale* retained above, *Jump 1* expanded to current sub-part. Landing → current *Jump* fully expanded incl. cross-checks; *Jump 2 / Uncertainty / Verdict* collapsed below. Verdict → *Uncertainty of g* and *Verdict* expanded; *Ground truth* collapsed until reveal, then expanded. Collapsed step = title row only (title + right `frame NNN`), body height 0.
- Formula rendering: serif italic ≈14 px, fractions stacked with 1px fraction bar, `=` aligned; each sub-result on its own line with 11px grey sans label above it. Primary result chip: solid amber bg, black mono 700 ≈13 px, padding ≈4×8 px, radius ≈2 px (used for scale factor and final `g`). Secondary result chip: transparent, 1px cyan border, cyan mono 700, same padding (frame-times, cross-check `g`, sole clearance). Warning/correction note: block with 3px amber left bar, bg ≈`#FFB54D` at ≈8%, 11px ≈`#D8C9A8` text.
- In Verdict step, σ-chips repeat §0.3.7 style but rectangular (radius ≈3 px): amber/red-tinted border+text for pass/fail.
- Error-budget bars (inside *Uncertainty of g*, verdict states): rows label-left (≈11 px ≈`#9AA8B8`, ≈55% width), bar track ≈90×5 px bg ≈`#16222F`, fill cyan `#4FE3F0` width ∝ %, percent mono ≈11 px `#E8EEF4` right-aligned (≈12% width). Below rows, total formula serif ≈13 px with `= X.X%`.

### 0.5 Control bar

Left→right, gap ≈10 px, all vertically centred in ≈52 px bar:
- Play/pause: circle Ø≈40 px, bg ≈`#DCE6EF`, black `▶`/`❚❚` ≈14 px centred.
- Step-prev / step-next: ≈32×32 px squares, radius ≈4 px, border 1px ≈`#2A3C52`, bg ≈`#0A111C`, grey `|◀`/`▶|` icons ≈11 px.
- Timeline: flexible width, track 2px ≈`#22344A`; played portion 2px cyan. Jump segments: thicker ≈5 px teal ≈`#1F6E73` spans with 9px labels above (`Jump 1`, `Jump 2`); event ticks: 2×≈12 px amber vertical marks with 9px labels below (`Scale` under its tick, `Verdict` under its). In side-by-side, only `Verdict` tick labelled below.
- Time readout mono ≈12 px `X.XX / XX.XX s`.
- Speed select: dark select ≈62×28 px, border 1px ≈`#2A3C52`, bg ≈`#0A111C`, mono ≈12 px `×1` with `▾`.
- Checkboxes: ≈14 px squares, radius ≈2 px; checked = cyan fill, black ✓; unchecked = border ≈`#3A4F68` transparent. Labels sans ≈11 px ≈`#9AA8B8`: `Pause on events`, `Full calculation`. ≈18 px between the two groups.

### 0.6 Colour palette (all ≈)

| Role | Hex | Used for |
|---|---|---|
| Measured / active / CTA / fit dots | `#4FE3F0` cyan | body outline, measured dots, primary buttons, active dots/underlines |
| Moon / fitting world / primary result | `#FFB54D` amber | Moon ghost+curve, scale ruler, result chips, stamp (pass) |
| Earth model | `#8A8FFF` periwinkle | Earth ghost, Earth curve, Earth pins/chips |
| Mars | `#FF7A4D` orange-red | Mars pin/chip only |
| Warning / correction | `#FFB54D` amber on ≈8% amber bg | notes, Freeze-frame |
| Fail / slowed / ground-truth fake | `#FF4D4D`–`#FF5A5A` red | Slowed stamp, ✗ chips, ground-truth text |
| Page bg | `#04070C` | — |
| Header / panel bg | `#060B13` / `#070C14` | — |
| Card bg on video | `#05090F` at 88–94% | verdict, reference, intro cards |
| Borders | `#1B2A3C` outer, `#22344A` inner | — |
| Gridlines | `#141E2C` | chart |
| Text primary / secondary / muted | `#E8EEF4` / `#9AA8B8` / `#66788C` | — |

Colour is never the only distinction: models also differ by dash pattern (Moon dashed, Earth solid, measured dotted) and by text label.

### 0.7 State changes vs invariants

| State | Video overlay | Chart | Side panel expanded |
|---|---|---|---|
| Intro | dimmed frame, headline, 2 cards, CTA; no outline | empty axes, `waiting for takeoff` | Time from frames |
| Scale (freeze) | cyan outline + amber reference outline/ruler/chips, reference card, caption | single cyan dot at origin | Scale (+Jump 1 takeoff start) |
| Takeoff/Apex (freeze) | outline, COM dot, I-beam + value chip, takeoff line, Earth+Moon ghosts+labels, caption | dots + 3 model curves with inline legend, up to current t | Jump 1 (apex sub-part) |
| Landing (freeze) | chronophotograph (§0.3.5), trajectories, time axis | full curves + landing chips | current Jump full calc incl. cross-checks |
| Verdict pre-reveal | verdict card + stamp, dimmed video, no caption | full curves + landing chips | Uncertainty bars, Verdict σ-chips; Ground truth collapsed with reveal button in card |
| Verdict revealed | + Ground-truth block inside card | unchanged | Ground truth expanded (red) |
| Side-by-side | both stages at matched event, each own outline/ghosts/mini-verdict+stamp | combined chart: Clip A cyan dots, Clip B white hollow dots/dashed white fit + models; bottom-right shared log-g verdict axis with both clips' markers | replaced by bottom chart + verdict panels |

Invariants: header/tabs, stage geometry, HUD/badge positions, control bar, chart position, step rail, fonts, palette. During playback the video carries the live layers of §18.4 (trail, strobe rings, outline, ghosts, takeoff level, apex ruler); each event adds its hold animation on top (§18.1, §18.5), with `Freeze frame` in the HUD.

### 0.8 Never do

- Never put a filled/translucent mask over the tracked body — outline + glow only; ghosts are the only filled silhouettes and must stay beside, not on, the real body.
- Never let overlay text overlap other overlay text: landing labels stagger to two rows; chart end-labels offset vertically; ghost labels clear the HUD; the stamp straddles the card edge but never covers `g = …`.
- Never squeeze the chronophotograph into a column: figures keep video scale and overlap horizontally; if space is short, crop the frame edges, don't shrink figures.
- Never place a label without a dark chip/backing over bright video, and never set text under ≈9 px.
- Never use the same colour+style for two models, or colour alone without a text label.
- Never let the reference card or verdict card cover the event caption, HUD, or badge — reference card top-right, caption bottom-left, verdict bottom-centre below mid-height.
- Never change stage/panel size, chart axes, or control layout between states; only overlay and curve content changes.
- Never show a result number without unit and (where applicable) `±` uncertainty; never use proportional sans for measured values — mono only.

## 1. Overall look and layout

- **Dark, cinematic page. Nothing white.** Background deep navy (`#0b1220`-family); panels a step lighter with **thin hairline borders**; text off-white at ≥ 4.5:1 against its background. There is no light mode.
- **Top bar:** the clip's title (from the result's first-look question/short title) on the left; when the page build assembles **related clips** (§11), tabs on the right: "Clip A · Clip B · Side by side".
- **Below:** the **video stage** (left, ≈ ⅔ width) and the **sidebar** (right, ≈ ⅓). A **control bar** sits directly under the video stage.
- **Phone (narrow) stacking order:** title, video with overlays, chart, the current step, and the **controls pinned to the bottom** of the viewport. No horizontal scroll at 360 px.
- **Type:** a clean sans for text; a **monospace for every number**, the HUD, the chart axes, and all big readouts. Formulas are typeset with **KaTeX, pinned version, from CDN** (script and its stylesheet, same version: the page's only allowed external requests, §23.1); if KaTeX fails to load (offline, `file://` restrictions), each formula shows its part-12 `fallback` string in monospace and the layout must not shift or break.
- **Colours (fixed semantics):** measured = **cyan**; Moon = **amber**; Earth = **blue-violet**; Mars = **orange-red**; impossible/fake = **red**; final results = **amber-filled chips**, intermediate results = **cyan-outlined chips**. Verdict colours: world fits = its world colour/green family, retimed = amber, impossible = red, undetermined = grey. Colour is never the only signal — every coloured thing is also labelled.

## 2. Inputs and page assembly

- Per clip, the page build inlines `result.json` + `summary.json` (part 12) into the page as JSON script blocks (works from `file://`; no `fetch()`), plus the assets of part 12 §12: H.264 page video (§12 below), poster frame, mask-check image(s), and **object cut-outs** for ghosts/chronophotograph with their bboxes/anchors.
- One frozen template for all clips; per page only the inlined data, video, and assets change. Template SHA-256 recorded in every page (HTML comment + "how this was made" drawer); a page whose hash doesn't match `player/`'s recorded hash is a build failure (part 15).

## 3. Everything is drawn on the video

The stage is the heart of the product: the viewer watches the measurement happen **on the footage**. All geometry arrives in **source-video pixels** (part 12 §0) and is drawn in an SVG layer in the video's own pixel-coordinate space:

- an SVG whose `viewBox` is the **display-pixel space** (`coded_width × SAR` by `coded_height` — clip A: ≈321.5×240), positioned **exactly over the displayed picture content rect** (see §5), `preserveAspectRatio="none"` against that rect so one SVG unit = one display pixel;
- source-pixel `x` maps to display `x × SAR_num/SAR_den`; `y` is unchanged. Stroke widths and glow are specified in display pixels (`vector-effect` / explicit scaling) so lines don't fatten under the SAR squeeze.

### 3.1 HUD

Top-left, monospaced: `● frame 254/465  t = 8.475 s  29.97 fps` (fps = measured, from the result). While paused on an event: a second line/segment **"Freeze frame" in amber**. Top-right: a small outlined badge **"SAM 3 masks"** (shown when the overlays come from SAM masks, per provenance; otherwise the badge names the actual source or is absent).

### 3.2 Mask outline

A **glowing cyan contour** around the tracked object, **every frame**, drawn from the segment's per-frame `overlay` polygons. At the Scale event the reference object's outline is drawn too (its own colour), from `references[].mask.outline`.

### 3.3 Tracked point, trail, fit curve

The tracked point and its **trail building up** behind the playhead, with strobe rings at a fixed time step (§18.4) — nothing from the future is ever drawn. The fitted curve (`fit_curve_px`) appears once its segment begins. A scale bar (a round number of metres from `m_per_px`) and the frame/time HUD are always present during playback.

### 3.4 Event captions (on the video)

Bottom-left on the stage: a **large event title with an amber bar on its left** ("Scale", "Takeoff", "Apex", "Landing", "Verdict") and **one line under it with the numbers in bold monospace**, e.g. "Centre of mass 0.083 ± 0.002 m above takeoff; feet 0.39 m off the ground". The caption belongs to the video, not the sidebar.

### 3.5 Takeoff level and apex

- A **dashed horizontal line around the jumper** (not across the frame, §18.4.1) at `takeoff_level_y_px`, labelled "takeoff level", from takeoff onward.
- At the Apex freeze: an **I-beam bracket** from the takeoff level to the apex point with an amber chip "**0.08 m**" (the measured rise, from `apex_info`).

### 3.6 Ghosts — figures, not dots

**Translucent silhouettes of the real object** (the page-build cut-outs, §2), tinted per world and **labelled** ("Earth" blue-violet, "Moon" amber, "Mars" orange-red), placed where the same jump would put the body **at this moment** under each ghost's gravity: same takeoff, same rise, the fall follows that world's `g`. They **move with playback**, anchored by the tracked point, scaled by the segment's mask bbox. The ghost set is exactly the segment's `ghosts` array (part 12 §5):

- a Moon-fitting clip shows the **Earth** ghost ("On Earth he would have landed here") plus the **Moon** ghost where it differs;
- an Earth verdict has an empty array — the fitted curve is labelled as Earth's path instead;
- an impossible clip shows where Earth physics would have put the body;
- wall segments: no ghosts.

A ghost that has already "landed" rests at its landing marker while the real body is still airborne — that contrast is the point of the device.

### 3.7 Chronophotograph (Landing freeze)

At the landing freeze: **real cut-outs of the object every ~0.2 s** (interval from the result's segment duration; page-build assets) composited left-to-right over the **darkened** frame, each with its glowing outline; **over them the trajectories** — measured (cyan, solid), fitting world (amber, dashed), Earth (blue-violet); **under them a time axis from takeoff** with landing markers "**Earth 0.40 s**", "**Moon 0.97 s**", "**in the clip 1.03 s**" (from `world_outcomes`, part 12 §5) and dotted drop lines to the axis. If the masks don't allow cut-outs, the chronophotograph is omitted — the trajectories and axis still show.

## 4. Playback, freezes, and the control bar

- Playback starts from the first screen's button (§9) or `autoplay=1`. Speeds **×1, ×0.5, ×0.25**.
- **Freeze frames (holds):** playback pauses by itself at each event (Scale, Takeoff, Apex, Landing, Verdict), zooms, dims and animates, then resumes by itself. Durations, camera and animations are in §18.1–18.6. **Pressing play skips** the remainder; the **"Pause on events"** toggle (control bar, on by default) turns holds off. The Verdict hold **stays until the viewer acts**.
- **Control bar** (under the video; pinned to the bottom on phone): a **round play button**; **previous/next event**; a **timeline** with events on it — **segments shaded as ranges labelled above** ("Jump 1", "Jump 2"), **point events as ticks labelled below** ("Scale", "Verdict") — and an elapsed/total readout "**8.48 / 15.52 s**" in monospace; a **speed select**; the **"Pause on events"** toggle; the **"Full calculation"** checkbox (off by default).
- **Timeline labels never overlap** (a named defect of the first attempt): the builder lays labels out in lanes above/below the timeline, measuring text widths and shifting/staggering until no two label boxes intersect and none is clipped by the stage edge; if a label cannot fit it is shortened by rule (drop to the shortest unambiguous form), never overlapped and never cut off.
- **Keyboard:** space = play/pause; **left/right arrows = frame step**; **up/down arrows = previous/next event**. Documented in one line on the page.
- **URL parameters set the state**: `frame=<n>`, `event=<id>`, `autoplay=0|1` — screenshots and shared links land exactly (part 15's review is built on these). State changes update the URL via `history.replaceState`.

## 5. Overlay registration (hard requirement)

Overlays that don't sit on the footage are the worst defect this page can have. Requirements:

1. All geometry is stored in source-video pixels (part 12 §0); the player maps it onto the **displayed picture**, accounting for (a) element scaling, (b) **letterboxing** — the SVG overlays the picture content rect, not the `<video>` element box, and (c) **non-square pixels** via `video.sample_aspect` (clip A: SAR 200:219; its display shape is 4:3-ish, *not* 352:240). If SAR is absent, 1:1 is assumed and the HUD/steps make no claim otherwise.
2. The mapping is computed from the video element's rendered content rect (after layout, on resize, on orientation change) — never from hard-coded aspect ratios.
3. **Test (part 13's own, `tests/player/`):** render a known source point (e.g. the tracked point at a fixture frame) through the mapping and assert it lands on the expected displayed pixel within 1 CSS px, for SAR 1:1 and for 200:219, with and without letterboxing. This test uses the **real clip-A fixture and clip** (§10), not invented coordinates.

## 6. The Scale freeze (a whole scene, specified)

At the scale frame, frozen:

- a **vertical ruler with tick marks drawn right next to the reference object, along exactly the measured extent** (between `references[].extent_px` endpoints, source px), ticks at round subdivisions of the extent;
- an **amber chip "0.87 m = 67 px"** and below it **"1 px = 1.30 cm"** (from `scale`, rounded per §13);
- at the right of the frame, a **reference card**: "Size reference"; the object name; the size **huge in monospace** ("0.874 ± 0.020 m"); the extent type ("vertical height, rear view"); then **each source**: its value, the **verbatim quote with the number highlighted**, the source domain; the derivation tag ("sum of two sources"); and the blind-check line "**mask check (Spark, blind): PLSS + OPS stack, confidence 0.9**" (from `mask_check`, part 12 §3).
- With a second reference, a second card (or a second section) with its own check line; with none, one line stating **why there is none**.

The same cards live permanently in the sidebar's reference section (§8) — the freeze-frame card is the same component, not a duplicate design.

## 7. The verdict freeze (specified)

**Centred over the dimmed frame**, a verdict card:

- "Verdict", then the headline number **very large in monospace**: "g = 1.55 ± 0.07 m/s²" (retimed verdicts headline the factor, e.g. "slowed ×1.5 to fit Moon"; undetermined headlines the word "Undetermined").
- A **log-scale g axis (0.5 … 10 m/s²)** with **only the worlds this result tested** marked and labelled ("Moon 1.62", "Mars 3.71", "Earth 9.81"), the measurement as a marker with its **2σ band** shaded.
- A **rotated rubber stamp** across a corner of the card, derived from the verdict by rule: world fit → "**MOON ✓ g within 2σ**" in the world's colour; retimed → "**SLOWED ×1.4 if this is the Moon**" (or SPED) in red; impossible → "**PHYSICALLY IMPOSSIBLE**" in red; undetermined → "**UNDETERMINED**" in grey. The stamp never says "fake"; "physically impossible" is always glossed as *"no world at any playback speed explains this motion"*.
- The **one-sentence verdict** (`sentence`, verbatim).
- **Chips per tested world**: "Moon 0.9σ ✓", "Mars 30σ ✗", "Earth 116σ ✗" (from `worlds.candidates[].delta_sigma`).
- The scene-excluded worlds listed with the cue that ruled each out ("why not the Moon: …").
- For **acceptance/demo pages only**: a "**Reveal the ground truth**" button (§10).

The same verdict block (minus the stamp's rotation) is the sidebar's final step (§8).

## 8. The sidebar

Two parts; on desktop it sits right of the stage, on phone it stacks below it (chart, then current step).

### 8.1 The chart (fixed on top)

"**Height vs time after takeoff**", monospace axes, units "**m / s**" at the right. Contents, all appearing **in sync with playback**:

- **measured points as cyan dots**, appearing as the video reaches them;
- the **fitting world's curve** (amber dashed for Moon) and the **Earth curve** (blue-violet) — i.e. the same ghost set as §3.6, as height curves;
- **landing markers with labels** for each (coloured dots on the time axis with the world's name);
- before the segment starts, the chart area reads "**waiting for takeoff**" (dimmed).

Chart labels must never be clipped by the chart's edge or overlap each other (named defect): labels are placed with measured bounding boxes, clamped inside the chart, and staggered vertically on collision; the headless tests (§14) check the rendered boxes.

### 8.2 The steps timeline (scrolls in sync)

A **vertical timeline of steps** below the chart, fed by `calculation_steps` (part 12 §6) plus the player's own Time/Verdict framing where the contract names them:

- steps like "Time from frames", "Mask check", "Scale", "Jump 1", "Jump 2", "Uncertainty of g", "Verdict" — each with "**frame N**" on the right in dim monospace;
- **future steps dimmed**; the **current step has a filled cyan dot**; the panel **scrolls itself to keep the current step in view**; **clicking a step seeks the video** to its frame (and freezes there if it's an event);
- inside a step: the part-12 blocks in order — **typeset formulas with the real numbers substituted**, each followed by its **result chip** (final amber-filled, intermediate cyan-outlined); caveats and corrections in a **box with an amber left border**;
- the **Uncertainty step** renders the error budget as **horizontal bars with percentages** and the line "σ_g/g = √Σεᵢ² = 4.6 %";
- steps are **short by default**; the control bar's "**Full calculation**" checkbox swaps in each step's `full` blocks (longer derivations and cross-checks);
- a step whose data a run lacks shows its one contract-provided line saying so (§13) — the sidebar never renders a broken or empty step.

### 8.3 Reference cards and "how this was made"

- The **reference card(s)** of §6 (permanent home).
- A collapsed "**How this was made**" drawer: model, turns, SAM frames billed, searches, mask checks, **tools the agent built and how each was verified** (part 10 registry data), cost in dollars, wall time — from `summary.json` + `result.self_built_tools`. Plus the frozen-template hash.

## 9. First screen (before play)

Over the **dimmed first frame**:

- the **question as a big headline** ("Does the physics add up to the Moon?"), one line of detail (the `first_look` summary);
- two cards: "**What we see**" (scene, place/date, confidence, object chips — from `scene_card`) and "**By eye, before measuring**" (big monospace estimates — jump in m, airborne in s — and one line of reasoning, explicitly labelled as pre-measurement, "Spark scene card, before any search");
- a bright "**▶ Watch the analysis**" button.

If `by_eye` or parts of `scene_card` are absent, the card shows what exists and one line for what doesn't — never an invented estimate.

## 10. Ground-truth reveal (acceptance pages only)

For pages the harness builds for acceptance clips, a "**Reveal the ground truth**" button appears on the verdict card (and a "Ground truth" position exists in the steps timeline). The truth — the expected label/facts and whether the analysis got it right — comes from a **harness sidecar injected by the page build**, never from `result.json` (part 12 §1) and never present in anything the agent saw. The reveal shows the truth plainly (red where the truth is "fake/impossible") and the analysis-vs-truth judgement. Pages built without a sidecar simply don't render the button or the step.

## 11. Related clips: tabs and side-by-side

When the page build is given a **related set** (e.g. clips A and B of the same event), the page's top bar carries tabs "**Clip A · Clip B · Side by side**":

- each clip tab is that clip's full player (stage + sidebar) with its own data;
- "**Side by side**" plays **both videos in sync** (shared transport: one play/pause, one timeline on the master clock; on drift > 1 frame the lagging video is seeked; each stage keeps **its own overlays, freezes and verdict**; on phone the two stages stack);
- the relation between clips exists **only at page-build level** — no result file references another run (part 12 §1), so nothing about the pairing can reach an agent.

Single-clip pages render no tabs.

## 12. Assets and weight

- Per page: the template (frozen, hash-checked), inlined data, the **H.264 video copy** (transcoded from the analysis input per skill video-ffmpeg; HEVC shows black in Chrome — the transcode is presentation-only, never analysed), poster frame, mask-check image, ghost/chronophotograph cut-outs.
- **Page weight without the video < 1 MB**, cut-outs included. The build caps cut-out count/size (chronophotograph interval first, then ghost-frame density) and logs any trim; verdict data is never trimmed.
- KaTeX (script and stylesheet, §23.1) is loaded from CDN (pinned) and is not counted in the weight; the offline fallback (part 12 `fallback` strings) keeps the page fully readable without it.

## 13. Presentation and degradation rules (binding)

- **Numbers rounded for people, one formatting function**: σ to two significant decimals, value to matching decimals; factors "×1.5"; percentages whole. A raw float repr anywhere is a defect.
- All text is real text (never baked into images), contrast ≥ 4.5:1 on the navy theme; chart/overlay lines distinguished by colour **and** label/dash.
- Reduced motion: no ease/zoom animations, no count-ups; final states shown immediately.
- **Honest degradation** (kept from the previous draft): the player opens any valid part-12 file, including synthesised undetermined ones. Missing segment → no overlays, and the affected steps/events carry their one contract line saying what's missing; empty `ghosts` → no silhouettes (Earth verdict: fit labelled as Earth's path); no clock → the clock step says so; no cut-outs → no chronophotograph, trajectories still drawn. A JS error on a valid result file is a template defect, full stop.

## 14. Tests owned by this part (`tests/player/`, `tests/pagebuild/`)

- **Real-data preview:** the page built from the **converted clip-A fixture + the real clip** (part 12 §11) renders the astronaut's outline on the actual footage at sampled frames; the synthetic fixtures render for edge cases (undetermined, impossible).
- **Registration:** §5's known-point test at SAR 1:1 and 200:219, letterboxed and not.
- **Label geometry:** headless checks that no stage caption, chart label, or timeline label is clipped by its container or overlaps another label (bounding-box assertions), at desktop and phone widths.
- **Behaviour:** freezes fire/skip/expire; tabs and side-by-side sync (drift correction) where a related set exists; ground-truth UI absent without a sidecar; KaTeX-blocked rendering still shows every formula's fallback; both fixtures open with zero JS errors.

## 15. Owner review of the second attempt (2026-10-27) — must not recur

Seen on the real clip-A page (1440×900). Registration was right (the tracked point sits on the helmet). Everything below was wrong; each item gets a headless test in `tests/player/` that renders the real clip-A page at the named frame or event:

1. **Overlay text and strokes are sized in CSS pixels, not video pixels.** Labels 12–14 px, event titles ~28 px, strokes 1.5–2 px, whatever the video's scale. Seen: "takeoff level" and "1.0 m" at ~30 px, ghost labels ~28 px. Test: computed font size of every overlay label ≤ 16 px except the event title.
2. **The mask outline is drawn every frame** of the segment as a glowing cyan path (§3.2). Seen: none. Test: at the apex frame the outline path has ≥ 20 points.
3. **Ghosts are silhouettes at full body size** from cut-outs with real pixels (§3.6). Seen: 10-px squares; cut-out PNGs of ~530 bytes (empty). Test: each cut-out has ≥ 30 % opaque pixels in its bbox; the drawn ghost's height matches the object's mask height within 10 %.
4. **No two overlay labels overlap** (ghost labels included; the §4 lane rule applies on the stage too). Seen: "Moon" over "Earth (landed)".
5. **Freezes happen**: `event=scale` shows the ruler along the reference extent, the amber "m = px" chip and the reference card; `event=apex` shows the I-beam bracket and chip; `event=landing` shows the chronophotograph and landing markers; `event=verdict` shows the verdict card with the stamp. Seen: at the scale frame nothing but the playing video. Test: each event URL renders its elements.
6. **`frame=N` renders the full state up to N**: trail, chart dots up to N, world curves, landed markers. Seen: an empty chart mid-flight. Test: at the apex frame the chart has ≥ 5 measured dots and both world curves.
7. **One rounding function for every number on the page** (§13). Seen: "0.01362468513853904 m/px". Scale is shown as people read it: "1 px = 1.36 cm", "1.80 m = 126 px". Test: no rendered text contains a number with more than 4 decimals.
8. **The control-bar timeline is full width and readable**: labels ≥ 11 px, event ticks visible, segments shaded. Seen: a squeezed timeline with ~6-px labels.
9. **Loading a URL with parameters never scrolls the page**: the title stays visible.

**Browser tests and screenshots, by the coding agent itself.** Tests that start a browser use the installed Google Chrome (§16.2) and run when `PHYSICS_PROOF_BROWSER=1` is set; without it they skip with a one-line reason. The dev loop runs this part with the browser available (part 15 §8). The coding agent therefore **runs the browser tests itself, and also takes screenshots and looks at them**. A helper `tests/player/shots.py` builds the clip-A fixture page and saves 1440×900 and 390×844 PNGs of the first screen and of every `?event=` state; it waits for the video to finish seeking before each shot. Before finishing, the agent opens every PNG and checks it against §0 (the approved look) and §§15–17. It fixes what differs and repeats. In its final message it lists, per shot, what it checked.

## 16. Owner review of the third attempt (2026-10-27) — must not recur

Big step forward: mask outline, reference cards with quotes, ruler, live chart with both worlds, verdict card with stamp, error-budget bars. Still wrong, each with a host-only browser test on the real clip-A page:

1. **The picture must be the frame the overlays describe.** `event=` and `frame=` (and every event jump, step click, frame step) seek the `<video>` to that frame and draw only after `seeked`; HUD, overlays and picture always show the same frame. Seen: the video stayed at t = 0 for every event while the overlays showed frames 253–465. Test: after `?event=apex`, `video.currentTime` is the apex frame / fps within half a frame.
2. **Browser tests use the installed Google Chrome** (Playwright `channel="chrome"`): Playwright's bundled Chromium has no H.264 and cannot play the page video, which is how item 1 slipped through. No Chrome installed → skip with a reason. `playwright` is a declared dev dependency (part 04).
3. **Ghosts are tinted silhouettes only**: no rectangles around them; tint per §18.4.5; the label sits above the silhouette (§17.2).
4. **The chronophotograph keeps each cut-out's aspect ratio** and places it where the object really was at that moment, so the figures spread along the actual path; no rectangles. Seen: cut-outs squeezed into overlapping vertical strips.
5. **Rounding, everywhere, one function**: σ multiples with one decimal ("0.5σ", "34.7σ"), times two decimals ("1.17 s"), lengths per §13. Seen: "0.4629σ", "34.7315σ", "1.1678 s", "1.2346 s".
6. **A label is never wrapped into a narrow column**: "in the clip 1.17 s" is one line; move it, don't squeeze it.
7. **Event captions are bright**: white bold title, numbers line at ≥ 4.5:1 contrast. Seen: dim grey on the frame.
8. **Error-budget rows have human names** ("reference size", "pixel measurement", "parabola fit", "jump-to-jump spread", "tracked point ≠ centre of mass"), never field names like `pixel_scale`.
9. **Chart**: the unit label appears once; landing labels sit clear of the curves (below the axis), never crossed by a line.
10. **HUD legible on any footage**: a dark translucent backdrop behind the HUD line.

## 17. Owner review of the fifth attempt (2026-10-27) — must not recur

Seek works now: picture, HUD and overlays show the same frame. Compared with the approved look (§1), the stage is still wrong. Its tests passed because they checked test ids and computed styles, not what is on screen. **From now on a test measures what the viewer sees:** client rects of drawn elements converted to source pixels, rects of every rendered text node, the visible text, and pixels of a screenshot. A test id alone proves nothing. Each item gets a host-only browser test on the real clip-A page, at 1440×900 and at 390×844. §15 and §16 tests stay, except that §17.5 replaces §16.4.

1. **The tracked object stays visible.** Its mask is drawn as the glowing outline only, with no fill or tint over the body. Seen: the jumper washed out under a pale-blue fill. Test: at `event=apex`, screenshot the stage with the overlay layer shown and with it hidden. Everything drawn over the picture lives under one element, `[data-testid="stage-overlay"]`. Inside the jumper's mask bbox shrunk by 20 %, the mean pixel difference between the two shots is < 10 of 255 at 1440×900. At 390×844 the outline and labels take a larger share of the small body, so there the test checks only that nothing fills the body (the mask's fill is none and no tinted layer covers it).
2. **Ghost placement is a translation, not an anchor.**
   - **Image.** A ghost is the object's cut-out nearest the current frame, at the same size.
   - **Offset.** It is shifted by (ghost point(t) − tracked point(t)) in source pixels and drawn at that offset. The tracked point is whatever body point the track follows (on clip A, the helmet top). The ghost is never centred or bottom-aligned on that point.
   - **Sides.** Ghosts stand beside the real object, as in the approved look. Earth goes one mask-bbox width to the left, a fitting world one width to the right. If a side would leave the frame, both go on the side that fits.
   - **Label.** Each ghost's label sits just above its own silhouette.
   - **Seen.** Both ghosts were drawn ~90 source px too high, cut by the frame top and lying over the HUD. The "Moon"/"Earth" labels sat on the jumper's chest.
   - **Test.** At `event=apex`, each ghost's top, converted to source px, equals the mask top + (ghost y(t) − track y(t)) ± 3 px. Its height is within 10 % of the mask height. Its horizontal overlap with the jumper bbox is < 15 %.
3. **One tracked-point marker, on the tracked point.** Seen: a cyan dot near the flag that marks nothing, at apex and at landing. Test: at `frame=253` exactly one tracked-point marker is visible. Its centre lies within 2 source px of the track point for that frame.
4. **No text overlaps text, and nothing covers the HUD.** This covers the stage, chart, control bar and verdict card. Seen: "in the clip" and "Moon 1.17 s" printed over each other at the landing line. Tests:
   - in every state (first screen, each event), the client rects of all non-empty rendered text nodes are pairwise disjoint (1 px tolerance);
   - `elementFromPoint` at the centre of the HUD and of the badge returns the HUD or the badge.
5. **Chronophotograph (replaces §16.4).** This is the approved Landing look.
   - **Layout.** Time runs left to right and height is real. Cut-outs every ~0.2 s are spread across ~60 % of the stage width. Each cut-out is at video scale with its aspect kept, and its vertical position is the object's real height at that moment.
   - **Overlap.** Neighbours may overlap. On clip A the body barely moves sideways, so real x positions would stack every figure on one spot.
   - **Over them.** The measured, fitting-world and Earth trajectories, drawn with the same time-to-x mapping.
   - **Under them.** A time axis with ticks in seconds, plus landing markers with drop lines. The marker labels sit on separate rows when they would collide.
   - **Background.** The frame is darkened.
   - **Seen.** One small figure in the top-left corner and no time axis.
   - **Test.** At `event=landing`:
     - ≥ 5 cut-outs whose heights are within 10 % of the mask height;
     - their x centres strictly increase;
     - all cut-outs and the axis lie inside the video rect.
6. **The Scale freeze is one card, not a wall.**
   - **Card.** One reference card covers the reference used for the scale, with value, source quote and mask check. The second reference is a single "check:" line inside that card.
   - **Card bounds.** The card spans ≤ 40 % of the stage width and ≤ 60 % of its height, on the side away from the reference object.
   - **Outline.** The reference object's outline is drawn in amber.
   - **Ruler.** The ruler stands beside the object's bbox (≥ 6 display px away) and never runs through the body. Its two chips read "1.80 m = 132 px" and "1 px = 1.36 cm".
   - **Seen.** Two full-height cards covering the right half of the picture, and a ruler drawn through the body.
   - **Test.** Card count and the size bounds; the ruler rect does not intersect the mask bbox shrunk by 10 %.
7. **Numbers in formulas and chips are rounded too.** Formula `latex` and chip text arrive from the result unrounded. Before rendering, the player passes every decimal with ≥ 3 decimals through the §13 rounding:
   - next to σ: one decimal ("0.5σ");
   - followed by `s`: two decimals ("1.17 s");
   - otherwise: three significant figures.
   - `^2` becomes "²" and the word `sigma` becomes "σ".
   - Seen: "1.1678 s", "0.4629σ", "px/s^2".
   - Test: in every state, the visible text contains no `\d\.\d{4,}`, no `\d\.\d{2,}σ`, no `\d\.\d{3,} s` and no `^`.
8. **The calculation panel follows the events**, as in the approved look.
   - **Grouping.** Steps are grouped under the event they belong to, in timeline order:
     - Scale: `mask_check`, `scale`;
     - Takeoff: `segment`;
     - Apex: `fit`;
     - Landing: `time_from_frames`;
     - Verdict: `measured_g`, `clock`, `uncertainty`, `verdict`.
     - An unknown id goes to the event nearest its `frame`.
   - **Expansion.** Superseded by §20.2: steps the playhead has passed stay open, later steps are title rows. Former rule: only the current event's group is expanded. The others show one line each (title and frame) unless "Full calculation" is on.
   - **Scrolling.** The current group scrolls into view inside the panel. The page itself never scrolls.
   - **Seen.** Every step expanded at once, and "Time from frames" highlighted at apex.
   - **Test.** Replaced by the rail test of §20.4.
9. **Event captions really look bright.** They show at full opacity at once on a freeze, with no fade-in still running. Seen: the "Apex" title grey on screen while its computed colour was white. Test: at `event=apex`, `elementFromPoint` at the title's centre returns the title. The product of the opacities of it and its ancestors is 1, and `document.getAnimations()` has no running animation on it.
10. **Chart reads like the approved one.**
    - **Axes.** Both axes carry numeric ticks: height in m, time in s, at least three each. The unit text appears once.
    - **Labels.** Each curve carries a short label at its end ("measured", "Moon", "Earth"). The landing marker reads "in the clip 1.17 s".
    - **Seen.** "m / s" printed twice, and no tick values.
    - **Test.** Count text nodes in the chart containing "m / s" (= 1), and count numeric tick texts per axis (≥ 3).
11. **Control-bar timeline.** Segment names go above the bar and standalone events (Scale, Verdict) below it, each on one line. A segment's own events (takeoff, apex, landing) are ticks whose names show as tooltips. Seen: "Takeoff/Apex/Landing/Scale" stacked in a column. Test: the §17.4 overlap test plus a timeline height of ≤ 64 px.
12. **Verdict card.** The stamp lies wholly inside the card and is not clipped. Number-line labels sit above or below the axis line, never on it. Seen: the stamp cut at the card edge, and "9.81" struck through by the axis. Test: the stamp rect is inside the card rect, and no label rect intersects the axis line.

## 18. Motion: how the approved player plays (owner review of v8, 2026-10-28) — binding

Owner, after v8: "too few frames; in the original it slowed down, many frames were inserted, the trajectory was drawn on the main frame, not only in the side panel; it paused, zoomed onto the body, drew the path on it, showed its position on every frame, measured the height over the frame." v8's stills were close to the approved look, but in motion it is a different product. This section describes the approved player's behaviour over time. It was written from the approved prototype's code, so the numbers are exact. Where §§0–17 say otherwise, §18 wins; the old lines that conflicted (§0.7 invariants, §3.5, §4 freezes) now point here.

Units in this section: **time** in seconds of wall clock; **source px** are video pixels (part 12 §0) on a 240-px-tall clip, and anything given in source px scales with the clip's height; **screen sizes** (strokes, radii, text, glow) are CSS px for a 720-px-tall stage and scale linearly with the stage height, but text never goes below 9 px.

### 18.1 The ride: holds that pause, animate and resume by themselves

Playback is a guided ride. When the playhead reaches an event frame, the video **pauses exactly on that frame**, the stage switches into that event's **hold** for a fixed time, the overlays **animate in** during the hold, and then the video **resumes by itself**. No click is needed anywhere between the first Play and the verdict.

| Hold | Duration | Camera zoom (§18.2) | Background dim (§18.3) |
|---|---|---|---|
| Scale | 3.8 s | 1.30 on the body | 0.55 |
| Takeoff | 1.5 s | 1.20 on the body at takeoff | 0.42 |
| Apex | 2.8 s | 1.20 on the body at apex | 0.58 |
| Landing | 5.6 s | 1.03, whole frame (the chronophotograph needs it) | 0.74 |
| Verdict | until the viewer acts | 1.03 | 0.80 |

- Two events on the same frame: their holds run one after another (Scale before Takeoff).
- Space or the play button during a hold: skip the rest of it and resume. Space while playing: pause (no hold). Space after the verdict hold: open the ground truth (acceptance pages) or restart.
- "Pause on events" off: no holds; the playhead runs straight through with the live layers of §18.4.
- `event=<id>`, `frame=<n>` on an event frame (or ≤ 2 frames after one), a step click, and the prev/next-event buttons enter that event's hold **without a timer** (sticky), with every animation of that hold already finished. This is the state screenshots use (§17.9: full opacity at once).
- On every hold start (not on a seek): a **flash** over the whole stage, pale cyan-white `#DFF6FF` from 16 % opacity to 0 over 0.45 s; a **hold bar**, 2 px amber with glow along the stage's top edge, fills left to right with the hold's progress; the HUD dot turns amber and "Freeze frame" shows.
- The caption (§3.4) fades in over 0.35 s and rises 6 px during a timed hold; on a sticky hold it is shown at once.
- Speed select ×1, ×0.5, ×0.25 changes only the playback between holds; hold durations stay in wall-clock time.

### 18.2 Virtual camera

The video picture and every overlay share **one camera**: a centre point (source px) and a zoom `z`. Apply it as one transform to one wrapper that holds both the picture and the overlay layer, so registration (§5) holds at any zoom. The camera never shows anything outside the frame: clamp its centre so the zoomed view stays inside the picture.

- **Playback** (no hold): `z = 1.03`, centred on the frame. The 3 % overscan hides edge artefacts and keeps the zoom-out from looking like a jump.
- **Holds:** the target is the body's mask bbox centre at the hold frame, with the zoom from the §18.1 table. Scale shifts the target right by 0.14 × frame height, so the body sits left of centre, away from the reference card (top right).
- **Drift:** during a hold the zoom keeps growing by 0.012 per second (capped after 6 s), a slow push-in.
- **Smoothness:** the camera moves to its target exponentially, never in a jump. Each frame `cam += (target − cam) × (1 − e^(−dt·k))`, with k = 3.2 /s while a hold is on and k = 4.5 /s after it. The zoom-in at a hold start and the zoom-out on resume take ≈ 0.5–0.8 s.
- Reduced motion: no camera moves (z = 1.03, centred), no flash, no drift; final states show at once.

### 18.3 Look of the frame: grade, vignette, dim, spotlight

- **Grade:** the picture is drawn with `contrast(1.06) saturate(0.92)` in every state; tests compare graded with graded.
- **Vignette:** always on. A radial gradient centred on the stage, clear out to 0.35 × stage height, reaching black at 42 % opacity at 0.95 × stage height.
- **Dim:** during holds, the whole frame is covered by `rgba(2,4,8,a)`. `a` eases to the §18.1 value at rate 5 /s and back to 0 after the hold.
- **Spotlight:** while the frame is dimmed, the tracked object's own pixels are drawn back on top at full brightness. The live cut-out is the current video frame clipped to the current frame's mask polygon, at opacity min(1, 2.2 × dim). The body therefore stands out bright against a dark scene. These are the original pixels, not a fill, so §0.8 and §17.1 hold. No mask on this frame → a radial spotlight instead: the dim fades to 10 % in a circle of radius ≈ 85 source px around the tracked point (centre 55 source px below it).
- During the chronophotograph (§18.6) the spotlight fades out, and at the verdict there is none.

### 18.4 Live layers during playback (the main frame, not the side panel)

From 3 frames before takeoff until 75 frames (≈ 2.5 s) after landing, the **video itself** carries these layers on every frame, while it plays as well as when seeked. Only the past is drawn, never the future.

1. **Takeoff level:** a dashed line (dash 5, gap 4; 1 px; `rgba(228,234,241,.5)`) at the takeoff level y. It spans only the area around the jumper: from the left edge of the leftmost ghost to the right edge of the rightmost ghost, or two bbox widths each side when there are no ghosts. The label "takeoff level" (10 px mono, 75 % white) sits above its right end. It is not a line across the whole frame.
2. **Trail:** a cyan polyline (1.8 px, glow 10, 90 % opacity) through the tracked point of **every frame** from takeoff to the current frame (or to landing, whichever is earlier).
3. **Strobe positions:** cyan rings (radius 3.2, stroke 1.6, glow 8) on the trail at every `round(fps × 0.234)` frames from takeoff (7 frames at 29.97 fps). They show where the body was at regular times, and their spacing shows the slow-down at the top.
4. **Body outline:** the glowing cyan contour every frame (85 % opacity while playing, 100 % in a hold). On a frame without a mask, a single cyan dot (radius 4.5, glow 14) on the tracked point instead.
5. **Ghosts** (from takeoff on, not during the Scale hold). For each ghost in the segment's `ghosts` array:
   - **Figure:** placed per §17.2. Before it lands it is the **live cut-out** of the current frame, desaturated (grayscale, brightness 1.15) and tinted with 38 % of the world colour, drawn at **40 % opacity**, so the scene shows through. A thin rim follows (0.9 px, 60 %, glow 8) in the world colour.
   - **Its own trajectory:** a dotted line (dot 1.5, gap 3.5; 1.2 px; world colour, 90 %) from its takeoff position to where it is now. It is sampled at 60 per second of model time, so a falling ghost leaves a visibly different arc beside the real one.
   - **Landing:** when the model's airtime is over, the ghost stays at its landing position as the landing-frame cut-out. At its feet an **impact ring** expands from radius 6, growing 40 per second and fading to 0 over 1.2 s.
   - **Label:** above the figure, a chip with the world name. Once it has landed there are two chips: "landed at 0.40 s" under the world name. The chips never overlap each other or the HUD (§17.4).
6. **Apex ruler** (from the apex frame to the end of the jump's layers). An I-beam (2.2 px amber, glow 10, end ticks ±3.5) stands 9 source px left of the body bbox at apex, from the takeoff level up to the apex level. A dashed amber line (dash 3/3, 80 %) runs at the apex level from the ruler to the body. The value chip "0.08 m" (17 px mono, amber-filled) sits at the ruler's middle. **It stays on screen after the apex** while the body falls.
7. **Scale overlay near the Scale event:** over the 12 frames before the Scale frame it fades in (opacity 1 − distance/12) and is fully on in the hold (§18.5).

### 18.5 What animates in each hold

- **Scale (3.8 s):**
  - **Outlines:** the reference object's amber outline (glow 22) and the body's cyan outline.
  - **Ruler:** it grows from its middle to its full length between 0.25 s and 0.95 s, with ease-out. Fine ticks every 5 or 10 source px appear once it is full.
  - **Chips:** "1.80 m = 132 px" (amber-filled) and "1 px = 1.36 cm" appear once the ruler is 90 % grown.
  - **Reference card:** slides in top right (§17.6).
  - **Camera and ghosts:** the camera pushes in to 1.30. No ghosts.
- **Takeoff (1.5 s):** push-in to 1.20 on the body; takeoff level drawn; caption "Jump 1: frame 232, t = 7.741 s". The trail and ghosts start from here as the video resumes.
- **Apex (2.8 s):**
  - **Ruler:** the I-beam's top grows from the takeoff level to the apex between 0.2 s and 0.8 s, with ease-out. The dashed apex line fades in with it, and the value chip appears at 85 %.
  - **Ghosts:** they stand still at their model heights for this instant, beside the bright body.
  - **Caption:** "Centre of mass 0.083 ± 0.002 m above takeoff; feet 0.39 m off the ground".
- **Landing (5.6 s): the chronophotograph animation**, §18.6.
- **Verdict:** dim 0.80, the jump layers off, and the verdict card (§0.3.7, §7) comes in.

### 18.6 Landing hold: the chronophotograph is an animation

At the landing hold the camera returns to the whole frame. The live layers of §18.4 fade out as the chronophotograph fades in (rate 8 /s in, 4 /s out). The frame is dimmed to 0.74. Times below are seconds since the hold started.

- **Copies:** cut-outs of the body at every strobe frame (`round(fps × 0.234)` frames apart, from takeoff), plus the landing frame. A 1-s jump gives 5–6 copies, a longer one more. They are real pixels at video scale, legs included.
- **Spread:** each copy starts **at the body's real position in its own frame** and slides horizontally to its time position on the axis. Copy i starts at 0.15 + 0.045·i s and moves for 0.85 s with a slight overshoot (ease-back). Its height stays real. The copies are composited with `lighten` blending at 50 %→92 % opacity as they arrive, each with a faint cyan rim (35 %).
- **Time axis:** time maps to x at ≤ 150 source px per second, fitted to the frame width. The axis sits 9 source px below the feet at takeoff (and above the frame bottom). It fades in from 0.1 s to 0.6 s, with ticks every 0.25 s and labels every 0.5 s ("0.5 s"). Over the first 0.6 s the whole layout eases down by up to 16 source px, to free the top for the caption.
- **Arcs, drawn progressively:** measured (cyan, 2.2 px, solid) from 1.15 s to 1.75 s; Earth (periwinkle, solid) from 1.6 s to 2.3 s; the fitting world (amber, dashed 7/4) from 2.0 s to 2.7 s. When a world arc is complete it gets dots at the strobe interval.
- **Landing marks:** as each arc completes, a dotted drop line goes from its end to the axis, plus a dot on the axis and a chip below it: "Earth 0.40 s", "Moon 0.97 s", "in the clip 1.03 s". Chips that would collide go to the next row (row step 27 px).
- **Caption:** at 2.2 s the caption swaps to "Chronophotograph" / "The jumper every 0.23 s. Time runs left to right, height goes up" and moves to the top left.
- **After the hold:** the video resumes and the layers fade back. Ghosts rest landed, then everything of this jump fades out 2.5 s after landing.

### 18.7 v8 defects that remain (from the owner's and the manager's review)

1. **Space does not start playback.** From `?frame=232&autoplay=0`, Space left `currentTime` at 7.741 for 11 s. Space must toggle playback from every state, focus anywhere on the page.
2. **The chart's time zero is at landing, not takeoff.** The chart's x axis is time after takeoff (0 at the takeoff frame), as on the stage.
3. **A "Size reference" block in the sidebar** duplicates the stage's reference card and overflows its box. Remove it; the reference lives in the Scale hold's card and in the Scale step.
4. **Chronophotograph copies have cut legs**, and the live outline is drawn over them. Copies are whole (§18.6), and live layers fade out under the chronophotograph.
5. **Ghosts are solid fills.** They are 40 %-opacity desaturated tints (§18.4.5).
6. **The first screen shows "– · 1.1 s".** No placeholder dashes in visible text.
7. **The verdict card sits mid-stage, and the g number line is linear.** The card goes bottom-centre, below mid-height (§0.8). The number line is **logarithmic** from 0.4 to 14 m/s², with major ticks at 0.5, 1, 2, 5, 10 and minor ticks every 0.1 below 1 and every 1 above.
8. **On the phone (390×844) a chip collides with the ghost labels.** The §17.4 overlap test runs at 390×844 too, in every state.

### 18.8 Tests and self-check for motion

The player exposes a read-only hook `window.__pp = { frame(), hold() → {kind, t, dur} | null, camera() → {x, y, z} }` for tests. Every visual claim is still measured on screen (§17).

1. **Ride:** open `?frame=<scale frame − 15>&autoplay=0` and press Space once. With no further input:
   - the holds come in the event order;
   - each lasts its §18.1 duration ± 0.4 s, with `currentTime` constant within one frame;
   - after each, `currentTime` advances again within 0.5 s;
   - the verdict hold is reached.
2. **Zoom:** in the Apex hold at t ≥ 1 s, `camera().z ≥ 1.18`, and the body outline's on-screen height is ≥ 1.15 × its height at the same frame with "Pause on events" off. During playback, `z ≤ 1.04`. The §5 registration test also passes at `event=apex`.
3. **Trail and strobe on the main frame:** at a mid-air non-event frame reached by playing (and again by `frame=`):
   - the overlay holds a cyan polyline passing within 2 source px of the track point of every frame since takeoff;
   - there are exactly ⌊(f − takeoff)/step⌋ + 1 strobe rings, each within 2 source px of its frame's track point.
4. **Ghosts in motion:**
   - at the same frame, each ghost has a dotted trajectory from the takeoff level to its figure;
   - after the Earth ghost's airtime, its "landed at" chip is visible;
   - inside the ghost figure the picture shows through: pixel variance > 0, and not one flat colour.
5. **Chronophotograph animation:**
   - at Landing hold t = 0.5 s, the copies sit between their real and spread x;
   - at t ≥ 3 s, the §17.5 checks pass, the three landing chips are visible and disjoint, and the caption reads "Chronophotograph".
6. **Hold chrome:** during a timed hold, the hold bar's width grows and "Freeze frame" is visible; the flash runs once per hold start.
7. **Film for the coding agent.** A helper `tests/player/film.py` plays clip A from 1 s before Scale to the verdict at 1440×900. It saves a screenshot every 0.4 s (`film-NN.png`) and a log line per shot: wall time, video time, `hold()`, `camera().z`. Before finishing, the agent opens the film frames as well as the stills (§15 paragraph). Per hold, it checks them against §18.1–18.6: the pause, the push-in, the dim and spotlight, the animation, and the auto-resume; and during playback, the trail, strobe rings and moving ghosts on the video. It lists per hold what it saw.

## 19. Owner review of v9 (2026-10-28): story order and the chronophotograph

v9 plays like the approved player: timed holds with push-in at Takeoff, Apex, Scale and Landing, ghosts beside the body, the apex I-beam, the chronophotograph, the verdict card with its stamp. The film (`tests/player/film.py`) found and fixed real ride bugs. Three differences from the approved player remain. Also, the §18.8 ride test started at "Scale frame − 15", which on clip A (Scale on frame 276, the landing frame) skipped Takeoff and Apex. That was the spec's mistake.

1. **The ride opens with the Scale chapter.** The viewer first learns how pixels become metres, then watches the jump.
   - **Order.** Play from the first screen seeks to `scale.frame`, runs the Scale hold there (on the frame where the reference was measured, with its ruler and card), then seeks to one second before the first takeoff and plays on.
   - **No second hold.** A later pass over `scale.frame` during the same ride does not hold Scale again, and same-frame chaining (§18.1) skips it.
   - **Seeking still works.** `event=scale` and the Scale step still land on `scale.frame`.
   - **Seen.** On clip A the Scale hold came after landing, on frame 276.
2. **Chronophotograph copies are at video scale.** On screen each copy is as tall as the body is during playback (camera 1.03), within 10 %. No copy is cut by the stage edge. If the spread does not fit, the time scale shrinks (fewer px per second), never the figures. Seen: copies about 1.5× the body's playback size, heads cut by the stage top.
3. **The trajectories go through the figures**, as in the approved player.
   - **Shared mapping.** The measured arc and the world arcs use the same time-to-x mapping as the copies and the real heights. The measured arc passes through the tracked point of every copy (the helmet top on clip A), and each world arc starts at the takeoff copy's tracked point.
   - **Axis.** The time axis stays below the feet.
   - **Seen.** The arcs were drawn as a separate small graph along the bottom of the stage, below the figures.
4. **Tests:**
   - **Ride from the first screen** (replaces §18.8.1): open the page with no parameters, press Play once, and with no further input the holds come as Scale, Takeoff, Apex, Landing, Verdict, each for its §18.1 duration ± 0.4 s.
   - **Copy height:** at the Landing hold t ≥ 3 s, every copy's on-screen height is within 10 % of the body's on-screen height at its own frame during playback, and every copy's rect is inside the stage.
   - **Arc through the copies:** the measured arc's polyline passes within 3 CSS px of each copy's tracked-point position.

## 20. Owner review of v10 (2026-10-28): ghost colour, the step rail, hold framing

v10 plays the approved story: Scale first, timed holds with push-in, the chronophotograph at video scale with arcs through the copies, the verdict card and stamp. The film side by side with the approved player leaves these differences. Each is checked against the approved player's code; §20 supersedes any earlier line it names.

1. **Ghosts are clearly coloured** (§18.4.5 recipe, which supersedes §0.3.4's fill and outline numbers).
   - **Recipe.** Draw each ghost on the overlay canvas: the cut-out through `grayscale(1) brightness(1.15)`, then 38 % of the world colour (Earth `#8A8FFF`, Moon `#FFB54D`) filled with `source-atop` so only the silhouette takes it, the result drawn at 0.4 alpha. Rim: the mask contour stroked twice in the world colour, a halo 2.9 px at 0.17 alpha with 8 px glow, then a core 0.9 px at 0.6 alpha with 4 px glow.
   - **No CSS masks.** Never shape a tint with CSS `mask-image`/`-webkit-mask-image`: the page opens from `file://`, where Chrome fetches mask images as CORS requests and drops them. Seen in v10: the tint layer painted nothing, ghosts showed grey with a faint glow.
   - **Impact ring** of §18.4.5 is drawn when a ghost lands (radius 6 + 40·age px, 2 px, alpha 1 − age/1.2, for 1.2 s). v10 drew none.
2. **The step rail accumulates** (supersedes the "Expansion" rule of §17.8 item 8 and the "preceding steps collapsed" wording of §0.4).
   - **Rule.** A step is open once the playback frame has reached its frame, and stays open while playback moves forward; steps ahead of the playhead show the title row only (dimmed). The last open step has the filled cyan dot; other open steps have a cyan ring. Seeking backwards closes the steps after the new frame. The §17.8 grouping of steps by event stays.
   - **Reveal.** A step's body fades in over 0.45 s from 4 px below when it opens; its result numbers count up from 0 over 0.9 s.
   - **Scroll.** When the current step changes, the panel (never the page) scrolls smoothly so the current step's top sits 12 px below the panel top. Do not rebuild the rail's DOM every frame.
   - **Mask-check picture.** The Mask check step shows, for each reference with a `mask_check`, its check image at full panel width (1 px `#24334A` border), a caption of 11.5 px muted text, an amber chip "mask = {answer.covers}" and the check's `answer.reason` in italics. The page build finds the image from the `mask_check.artifact` JSONL: the row whose `npz` basename equals the reference's `mask.artifact` basename gives `sheet`; the image is the file with that basename next to the JSONL. v10 showed no picture: the build copies only `.png`/`.jpg` artifacts, and the artifact is the JSONL.
   - **Seen.** Only the current event's group was open; at the apex the Scale formula and its result had collapsed to one line.
3. **Hold framing follows §18.2:** the camera target at Takeoff, Apex and Landing is the body's mask bbox centre at the hold frame, not the tracked point. Seen: v10 centred on the tracked point (the helmet top on clip A), framing the body low.
4. **Tests** (the page opened from `file://`, as the existing fixtures do):
   - **Ghost colour:** at `event=apex`, compare the median colour inside each ghost's silhouette with the same pixels in a screenshot taken with ghosts hidden: Earth ghost blue minus red rises by ≥ 10, Moon ghost red minus blue rises by ≥ 10. The page's CSS contains no `mask-image`.
   - **Impact ring:** through the §18.8 hook, a landed ghost reports an impact ring for 1.2 s after its landing time.
   - **Rail:** at `event=apex`, every step whose frame ≤ the apex frame has a visible body (height > 0), every later step is a title row; the Mask check image has `naturalWidth > 0` and a rendered width ≥ 200 px.
   - **Framing:** at `event=takeoff` and `event=apex`, the body's mask bbox centre is within 3 % of the stage height from the stage centre on each axis, unless the camera is clamped at the picture edge on that axis.

## 21. Owner review of a real run's page (2026-10-28): the player works on real output

The first accepted live run, built into a page, showed rectangles for ghosts, a coarse polygon for the body, an empty chart, "…landed at" cut by the stage edge, and "1.27 m" at the apex. The data's conventions caused most of it (part 12 §16); the player must also be tested on real output, not only on the clip-A fixture.

1. **Artifacts resolve against the run folder.** The build resolves every artifact path against the folder that holds `result.json`, never the repository root or the working directory. A cited artifact that cannot be found fails the build with its path (no silent rectangle fallback).
2. **Time and level per part 12 §16.** The chart's x is `t_s − times_s.start`; the takeoff line is `takeoff_level_y_px` (through the tracked point at takeoff); the apex I-beam spans from that level to the apex.
3. **Two fixtures.** Every test of §14–§21 that does not name clip A's own numbers runs on both `fixtures/clip-a/` and `fixtures/run-7/` (part 11 §9). For the real run additionally: each ghost is a silhouette (its cut-out's opaque pixels cover 30–90 % of its bbox, not 100 %); the chart shows ≥ 10 measured dots; no overlay label's rect extends past the stage; every hold of the ride runs; the verdict state renders the result's verdict kind (undetermined for run 7).
4. **Test:** building `fixtures/run-7/` from a different working directory gives the same page.

## 22. Owner review of v11 (2026-10-28)

v11 fixed §20: the ghosts are coloured with rims, the Mask check step shows its picture, holds frame the body. Filmed against the approved player, these remain:

1. **The picture always covers the stage.** At the Takeoff and Apex holds the zoomed picture left black bands at the stage's left and top (≈ 95 px and ≈ 45 px): the camera centre was not clamped (§18.2). Clamp it on each axis so the zoomed picture's rect contains the stage rect, during holds and during the moves between them. Test: at `event=takeoff`, `event=apex`, `event=landing`, and at 5 sampled moments of the ride, the picture's transformed rect contains the stage rect.
2. **Labels sit on what they label.** "takeoff level" floated in the top black band, ≈ 200 px above its line. The label sits at the line's right end, its centre within 4 px of the line. Test: at `event=takeoff`.
3. **The Mask check picture is a thumbnail.** The check image (a 2 × 2 grid of frames) filled the panel's whole height at full width and pushed every later step out of view. Show it at most 150 px tall (`object-fit: contain`), and keep §20.2's scroll on every seek and deep link: at `event=apex` the current step (the jump) is in view. Test: at `event=apex`, the current step's title rect is inside the panel's visible rect, and the mask image's rendered height ≤ 150 px.
4. **No live outline over the chronophotograph or the verdict.** At the Landing hold and in the Verdict state the real body's outline from the hold frame was drawn on top of the copies and the dimmed frame. Hide it while the chronophotograph or the verdict card is shown. Test: at `event=landing` (t ≥ 3 s) and `event=verdict`, the overlay draws no body outline.
5. **The stamp keeps σ and stays off the gauge.** CSS `text-transform: uppercase` turned "2σ" into "2Σ". Write the stamp's capitals in the text, never transform symbols. The stamp also covered the gauge's "Earth 9.81" label: place it so it intersects no gauge label or marker. Test: the stamp's text contains "σ" when it names σ; its rect intersects no gauge label rect.
6. **The chronophotograph's time axis is below the feet** (§19.3): the copies' feet hung over the axis. Test: the axis y ≥ every copy's bottom.
7. **The page file is `index.html`.** v11 wrote `page.html`; part 15 publishes `pages/<clip-slug>/index.html`. Test: `build_page` writes `index.html`.

## 23. Owner review of v12 (2026-10-28)

v12 fixed §21 and most of §22: the page builds from the real run, ghosts and the takeoff level agree with the chart, the picture covers the stage. Filmed against the approved player and probed at every event on both fixtures, these remain:

1. **KaTeX needs its stylesheet.** The page loads `katex.min.js` (pinned) but not `katex.min.css`. Without the stylesheet KaTeX's hidden MathML copy shows next to its HTML copy, so every formula in the rail reads twice: "t = N/f = 35/29.97 = 1.17st = N/f = 35/29.97 = 1.17 s". Load `katex.min.css` of the same pinned version next to the script; the script and its stylesheet are the page's allowed external resources (amends §1's "single"). The offline fallback (§10) stays. Test: the page has one KaTeX script and one KaTeX stylesheet with the same version; in the browser, after KaTeX renders, every `.katex-mathml` box in the rail is at most 1 × 1 px. If the CDN is unreachable, skip with that reason.
2. **The Landing hold shows only the chronophotograph** (§18.6). At `event=landing` the stage still drew the scale chips "1.80 m = 132 px" and "1 px = 1.36 cm" with the ruler, an amber body outline 187 × 436 px (the Moon ghost's outline from the Apex hold) under the copies, and a faint rectangle around each copy. §17.4 says no rectangles. Visible during the Landing hold: the dimmed frame, the chronophotograph heading, the copies, the trajectories with their dots, the time axis with its ticks, and the landing labels. Nothing else. Test: at `event=landing` (t ≥ 3 s) on both fixtures, no scale element, ghost outline, apex element or spotlight shape is visible, and no stroked rectangle surrounds a copy.
3. **The chronophotograph heading covers nothing.** On clip A the tracked point is the helmet top, so the trajectory runs along the top of the stage, and the sub-line "The jumper every 0.23 s. Time runs left to right, height goes up" was written across the trajectory dots. The heading takes the first free place of: top-left below the HUD (§0.3.5), top-right below the badge, bottom-left above the time axis labels. A place is free when the heading intersects no trajectory dot, no copy's top quarter and no label. The heading keeps its dark strip. Test: at `event=landing` on both fixtures, the heading's rect intersects no trajectory dot and no label.
4. **No label leaves the stage, at any event.** Probed on both fixtures: at `event=landing` the "Moon 0.97 s" label (`lb-chlanding-fitting`) sat at y 892–910, below the stage's bottom (842), after collision avoidance pushed it down. At `event=scale` the scale chips started at x = −9 and −7, past the page's left edge, and the apex value "0.177 m" showed at y 59–89, above the stage, during the Scale hold, when it belongs only to the Apex hold. Collision avoidance moves a label up or sideways, never out of the stage. A label that still doesn't fit is clamped inside the stage, and chips clamp too. An element shows only in its own hold. Test: at `event=scale`, `takeoff`, `apex`, `landing` and `verdict` on both fixtures, every visible text element in the stage lies inside the stage rect, and at `event=scale` no apex element is visible.
5. **The chart's legend and end labels stay off the data.** The legend ("measured / fit / Earth / Moon") sat on the curves' start in the plot's top-left, and the right end label "in the clip" was cut by the chart's edge. Put the legend in one row outside the plot area: above it next to the title, or below the axis labels. End labels right-align at the plot's right edge when they would overflow. Test: the legend's rect does not intersect the plot area; every text element in the chart lies inside the chart's box.
6. **The gauge's unit is whole.** The verdict gauge axis ends in "g, m/" with the "s²" cut off at the card's edge. Test: every text in the gauge lies inside the gauge's box.
7. **Mask-check chips show the whole claim.** "mask = whole foreground astronaut helmet top to boot soles includin" was cut mid-word. The chip wraps to at most 3 lines. A longer claim ends in "…" at a word boundary, and the full claim stays in the chip's `title`. Test: on clip A no chip's text is clipped without a trailing "…".
8. **A fixture builds without warnings.** Building from `fixtures/clip-a` logged `mask sheet missing`, and from `fixtures/run-7` `mask check image missing`. Both fixtures are now closed (part 12 §17, part 11 §11). Test: `build_page` on both fixtures logs no line containing "missing".
9. **Browser tests wait on page state, never on wall-clock time.** `test_chrome_ride_order` failed once in the full suite (the machine was busy) and passed when run alone. Wait for the page's own state (the current event or hold the page exposes, the `seeked` event), with a generous timeout. Test: the ride-order test passes 3 times in a row inside one pytest session.

## 24. A page carries no local path (owner addendum 2026-10-28)

The eighth run's `summary.json` held the absolute path of its `result.json`, including the operator's home folder, and the page build inlines `summary.json` as is. Part 14 now writes run-relative paths (part 14 §7); the build also guards against them. Before inlining, any string in `result.json` or `summary.json` that is an absolute filesystem path is replaced with its form relative to the run directory, or with its basename if it lies outside the run directory. Test: build from a temporary copy of `fixtures/run-7/` whose `summary.json` has an absolute `result_path`; the built `index.html` contains neither that run directory's absolute path nor the home folder's path.

## 25. Owner review of v13 (2026-10-28): smooth outlines, as in the approved player

The owner, watching the run-8 page: "SAM looks imprecise and poor; the original outlined more smoothly." The masks are the same SAM masks the prototype used. The prototype smoothed them, and v13 draws their pixel staircases at 3.3× zoom (352 × 240 video on a 1062-px stage). This is the prototype's code (`refs/experiments/player/template.html`, `contourFromSpans`, `MaskStore.canvas`, `cutFrom`), as behaviour:

1. **Contours come from the mask, smoothed.** The page build traces every mask it draws (body, reference, ghosts) with marching squares through pixel-edge midpoints, so a staircase becomes 45° steps. It drops loops shorter than 14 px of perimeter, then runs two passes of Chaikin corner cutting: each edge a→b becomes points at a + ¼(b − a) and a + ¾(b − a). The page stores these loops in video pixels with one decimal, and every outline, rim and reference outline is drawn from them. Outline polygons in the result are not drawn as they are.
2. **Cut-outs and ghost fills are drawn at 4× resolution from the smoothed contour.** The mask for a cut-out is the smoothed loops filled (even-odd) at 4 × the video's resolution, edge feathered by a 0.55-video-px blur (`destination-in`, as `cutFrom`). Cut-out images are built at 4× too (within §1's page weight; lower the count before the resolution).
3. **The Moon trajectory stays below the HUD.** On clip A at `event=landing` the amber Moon dots ran through the HUD row ("Freeze frame") at the top of the stage. Trajectory dots and lines are clipped to the stage below the HUD's bottom edge plus 6 px.
4. **The reference card ends cleanly.** Its last paragraph ("no second reference: … background figure and pole are much") was cut mid-line by the card's bottom. Text that doesn't fit ends in "…" at a word boundary, and the full text stays in the card's `title`.
5. **Tests:**
   - at `event=apex` on clip A, no two consecutive segments of the body outline path meet at a right angle (90° ± 5°) when both are longer than 0.5 video px;
   - every cut-out image is at least 3.5 × its mask bbox width in pixels;
   - at `event=landing` no trajectory dot's centre lies above the HUD's bottom edge;
   - the reference card's text is not clipped without a trailing "…".

## 26. Owner review of v13, continued (2026-10-28): a chronological ride, a rail that follows

The owner watched the run-8 page and did not see the Scale hold. The calculations also did not "scroll gradually with the video so everything is on one screen", as they do in the approved player. Probed at 1440 × 780 with Play from the start:

1. **The ride is chronological.** On run 8 the Scale frame (250) comes after Takeoff (244). Play at 0 jumped straight to 8.34 s and held Scale, then rewound to 7.7 s and played into Takeoff. The first 8 s of the clip never played, and the Scale hold came before the viewer had seen anything. Play from 0 plays the clip from 0. Holds fire in frame order, and the player never seeks backwards by itself. §18.1's "Scale before Takeoff" applies only when the two share a frame. Test: on a test copy of the clip-A result whose scale frame is moved 6 frames after the first takeoff, Play from 0 is sampled every 100 ms. `currentTime` never decreases until the verdict, the first sample is below 0.5 s, and holds fire in ascending frame order.
2. **The rail follows the playhead, as in the approved player** (`updateSteps` in the prototype):
   - a step's lines appear one at a time during its hold, 0.35 s apart, each with its count-up;
   - on every new line or step the rail scrolls smoothly (`behavior: "smooth"`), so the current step's top sits 12 px below the rail's top, or, when the step is taller than the rail, so its newest line sits at the rail's bottom;
   - the page itself never scrolls: chart and rail share the right column's height at any window size from 1280 × 720 up.

   Seen: at 1440 × 780 the rail is 330 px tall; it jumped only at hold changes, and at the verdict the current step began 234 px down, so most of it was below the fold. Test: at 1280 × 720 and 1440 × 900, during the Apex and Verdict holds, sampled every 200 ms, the newest visible line of the current step lies inside the rail's visible rect, and `document.scrollingElement.scrollHeight` equals the window height.

## 27. Owner review of v14 (2026-10-28): every motion on the timeline

Owner, on v12: "on the bottom scale Jump 2 did not show." Part 12 §19 added `first_look.motions`: every motion the agent saw, measured or not. Seen on v14 (clip-a fixture: two motions, the second unmeasured): the timeline shows only "Jump one"; the second motion is nowhere on the page.

- **Every entry of `first_look.motions` is a range on the timeline**, from `frame_start` to `frame_end`.
  - A measured motion (`segment_id` set) is labelled with its segment's label and keeps its marks and holds as now.
  - An unmeasured motion (`segment_id` null) is a grey range labelled "not measured". Its tooltip is `description — skip_reason`.
- **The rail gets one line per unmeasured motion** at its `frame_start`, in time order with the other lines (§26), and no hold: "`description`: not measured — `skip_reason`".
- **Several measured motions:** each segment gets its own Takeoff, Apex and Landing holds and its own chronophotograph. All holds play in frame order (§26), and each segment has its own labelled range.
- **A result without `first_look.motions`** (older runs) shows one range per segment, as now.
- **Tests:**
  - the clip-a fixture page has two timeline ranges: one labelled with the segment's label, one grey "not measured" whose tooltip holds the skip reason;
  - a test-made copy of that result whose second motion carries a segment (the first segment's data shifted by +99 frames, label "Jump 2") has two labelled ranges, and Play holds at both takeoffs in frame order.

## 28. Owner review of v14, continued (2026-10-28): a calm rail and a summary at the end

Owner: "the right part blinks all the time. When you show the summary, everything on the right should slide up so it can be opened, and at the bottom there should be the final summary; we duplicate it anyway."

Seen on v14 (clip-a, 1440×900, a MutationObserver on `#steps`):
- During plain playback with no new line due, the rail rewrote text about 300 times a second.
- Over the whole ride it added or removed 21,886 nodes. The rail is re-rendered every frame, and that is the blinking.
- At the verdict hold the steps stay expanded and dimmed, and "How this was made" sits squeezed at the bottom.

- **The rail is built once.**
  - Every line and its typeset formula exist from page load. Playback only toggles classes on them (hidden → revealed → past).
  - A count-up runs once, for 900 ms, when its line is revealed, and then stops.
  - No frame callback writes text or rebuilds nodes in the rail. KaTeX typesets each formula once.
- **The verdict comes last.** The verdict hold plays after the last motion of `first_look.motions` has ended (§27), at the later of the verdict frame and that last `frame_end`. A later motion still plays, and its line still shows.
- **At the verdict the rail folds up.**
  - Every step collapses to its one-line heading: the step title and its result chip.
  - The rail scrolls to the top, so all the headings fit, and each heading expands on click.
  - Below the headings, at the bottom of the rail, a **Summary** block is open. It repeats the stage's verdict card on purpose: g ± σ, the world, the σ chips, the stamp text and the sentence.
  - "How this was made" stays collapsed beneath the Summary block.
- **Tests:**
  - with a MutationObserver on the rail, 3 s of playback in which no line is due shows zero text and child-list mutations;
  - over the whole ride, child-list mutations number at most the line count;
  - after the verdict hold, every step body is collapsed, the rail's `scrollTop` is 0, the Summary block is visible inside the rail with the verdict's g and world, and clicking a heading expands its step;
  - on the clip-a fixture, the unmeasured second motion's line (frames 340–376) is revealed before the verdict hold.

## 29. Self-review of v15 on a portrait clip (2026-10-28): one box for every stage layer, a stamp that fits

Seen on the first wall run, a 720×1280 portrait clip:
- **The freeze-frame layer is too short.** At every hold (Scale, Takeoff and the rest) it covers only the top ~70 % of the stage. Below it, the live video shows through at a different zoom: at Takeoff the carpet's white lines appear twice, at two sizes.
- **The stamp overflows.** At the verdict, "UNDETERMINED" runs past its box, and the stamp's sub-line carries the whole reason over four lines.

- **One video box.** Every stage layer shares one box computed from the video's own width and height, for landscape and portrait alike: video, freeze frame, dimming, masks, cut-outs, trajectory and labels. A hold's zoom transforms that box as a whole. No layer assumes a landscape aspect.
- **The stamp fits.**
  - The main word scales down until it fits inside the stamp: "UNDETERMINED", "IMPOSSIBLE", "MOON ✓".
  - The sub-line is at most two lines; a longer reason ends with an ellipsis and stays whole in the verdict card's sentence.
- **Tests:**
  - A page for a portrait video: the test makes a synthetic 360×640 clip and copies the clip-a result with its frame coordinates scaled to it. At each hold, the freeze-frame layer's box equals the video layer's box within 1 px, and no part of the stage shows the live video beside the freeze frame.
  - An undetermined result with a 150-character reason: the stamp's text lies inside the stamp box (`scrollWidth ≤ clientWidth`, `scrollHeight ≤ clientHeight`), and the sub-line has at most two lines.

## 30. Self-review of v16 on a portrait clip (2026-10-28): the freeze frame fills its canvas

§29's single box holds: video, freeze frame, spotlight and overlay all share one box (on the wall clip at 1440×900: left −129, top −215, 1150×2044). The freeze canvas itself still shows two images, though.
- **Wall clip, Takeoff hold**, with every other layer hidden: the top 70 % of the stage shows frame 60 at the hold's zoom. The bottom 30 % shows the carpet at a larger zoom and darker. These are stale pixels from an earlier draw, or a draw whose destination rectangle is not the whole canvas.
- **Wall clip, Apex hold:** the seam sits at 35 % of the stage.
- **Moon clip (landscape):** a thin strip at the left edge shows the same kind of seam.

- **One draw per freeze.**
  - Each time the freeze frame changes, the canvas is cleared and the whole video frame is drawn once into the whole canvas, as `drawImage(video, 0, 0, canvas.width, canvas.height)`.
  - `canvas.width / canvas.height` equals `videoWidth / videoHeight` within 1 %.
  - Zoom and pan come only from the box's CSS transform, never from the draw's source or destination rectangle.
- **Tests (portrait and landscape):**
  - A synthetic 360×640 clip encodes position in its pixels: red is `255·x/width`, green is `255·y/height`, blue is 128. Make it with ffmpeg `geq`.
  - At each hold, with only the freeze layer visible, screenshot points on a 5×5 grid over the stage. Each point's colour matches, within 12 levels, the source pixel that the box transform maps it to. A second image at another zoom fails this test.
  - The same test runs on a 640×360 landscape clip.

## 31. Owner addendum (2026-10-29): the stamp says realistic or not

Part 02 §8 (2026-10-29) sets the display wording; the verdict card follows it:

- **Stamp text by rule:** world fit → "**REALISTIC ON THE MOON ✓**" (ON EARTH, ON MARS) in the world's colour; retimed → "**NOT REAL SPEED · SLOWED ×1.4**" (or SPED) in red; impossible → "**NOT REALISTIC ON EARTH**" (the candidate world) in red; undetermined → "**UNDETERMINED**" in grey. The gloss under an impossible stamp: "no playback speed makes this motion fit <world>".
- **The headline number stays** ("g = 1.66 ± 0.22 m/s²"; retimed headlines the factor), so the label always comes with its number.
- **One tested world is the normal case:** the g axis marks that world only, one σ chip, and no "why not …" list when `worlds.excluded` is empty.
- The intro headline is `first_look.question` verbatim (§9), so the page opens with the viewer's question and closes with its answer.
- **Tests:** stamps for the four kinds from fixtures; a one-candidate result renders one gauge marker and one chip and no exclusion list.

## 32. Owner addendum (2026-10-29): range checks on the stage and in the rail

Parts 02 §9 and 12 §22 (2026-10-29) add range checks to the result. The player shows them:

- **On the stage:** at each range check's `frame` the video freezes (a hold like the scale hold) and draws its extents as rulers between their endpoints, each labelled with its `name` and length (px, or metres when `uses_scale`), in the result-chip colour.
- **Range bar** under the frozen frame and again in the verdict card: a horizontal bar for the range (`min` … `max`, with `typical` as a tick), the measured value as a marker with its 2σ band; inside → the world's colour, outside → red with the σ distance ("2.5σ below min"); the source's domain under the bar. The bar replaces the g axis when the verdict has no gravity part.
- **Rail:** one step per range check (from `calculation_steps`), with the formula, the range and its quote.
- **Range-only results** (no segments) play the clip once to the first range check's frame and hold there; no trajectory chart, no ghosts, no landing chips; the stage never shows an empty chart.
- **Tests:** the still-range fixture renders two range bars (one inside, one outside, red, with "below min") and the stamp "NOT REALISTIC ON EARTH"; the Moon fixture still renders as before plus its one range bar; no console errors at desktop and phone widths.

- **Contract version:** tests compare a page's `contract_version` with `src.contract.CONTRACT_VERSION`, never with a literal; part 12 raised it for range checks.

## 33. Owner addendum (2026-10-29): the first screen says what we check

- Under the intro headline (`first_look.question`), when `first_look.wonder` is present: one line "Claim: <claim>", then "What we check:" with one short row per check (`what` — compared with `compare_with`). At most three rows; long text wraps, never overflows the card.
- The verdict card's sentence then answers the same question, so the page reads question → plan → measurement → answer.
- **Test:** the clip-A fixture's intro shows its claim and one check row; a result with `wonder` null shows the intro as before.

## 34. Self-review of v17 on a loaded machine (2026-10-30): no hold is skipped, tests wait on the page

Seen: other processes kept the CPU busy (load average 10–14), and each of two full browser runs failed a different player test. `test_chrome_two_segments_timeline_and_ride` got the holds [takeoff, scale, landing, takeoff, apex] instead of all eight, so apex, landing and the verdict were lost. `test_chrome_freeze_frame_fills_canvas` failed its pixel check after a fixed 400 ms wait. The cause in the player is that one animation tick can cross several events. The crossing check enters the first event, then moves `prevFrame` to the current frame, and the other crossed events never fire. A viewer's phone is a slow machine too.

1. **No hold is skipped.**
   - When one tick crosses several events, all of them fire in frame order, one after another.
   - After a hold, the crossing check resumes from the held event's frame, not from the frame the video has reached. The player still never seeks backwards (§26.1).
   - The verdict hold fires when the playhead reaches its frame or when the clip ends, even if the end falls between two ticks.
   - Test: animation frames are throttled to at least 250 ms each, for example by a busy loop in an injected `requestAnimationFrame` callback. Under that throttle the two-segment ride of `test_chrome_two_segments_timeline_and_ride` still yields all eight holds in order.
2. **Tests wait on the page, not on the clock.**
   - A browser test never uses a fixed delay (`wait_for_timeout`) to synchronise. It waits for a state the page exposes through `window.__pp`, such as the freeze canvas drawn for the current frame, a hold entered or a line revealed. The wait has a timeout of at least 30 s.
   - A fixed delay is allowed only to check that something does *not* happen.
   - The whole browser suite passes while another process keeps every CPU core busy.

## 35. Self-review of the Moon page before the demo (2026-10-31): nothing overlaps, the phone shows the verdict

The Moon page (clip-a fixture) was screenshot at 1440 × 900 and 390 × 844 for every event. It has no console errors, and the verdict reads "REALISTIC ON THE MOON ✓". Several viewer-visible defects remain, although §§ 16, 22 and 30 already forbid them. Each one gets a test that measures rectangles in the page, so that it cannot return.

- **Apex:**
  - the two orange height chips ("0.1 m" and "0.170 m") are drawn on top of each other and on the ruler's end tick, so neither is readable;
  - "landed at 0.20 s" is crossed by the ghost's landing circle.
- **Scale:** the ruler label "1 px = 1.31 cm" is crossed by the ruler's end tick, the small chip above the ruler is unreadable, and "takeoff level" loses its first letter behind the mask outline.
- **Takeoff:** the "Earth ghost" label sits half outside the stage.
- **Header:** the question is shown twice, in the top bar and again above the video. It is shown once, above the video.
- **Verdict:** the rail says "Verdict frame 277" while the stage shows frame 376. They show the same frame. The chart's y-axis reads "-0.0", and zero is written "0".
- **Phone (390 × 844):**
  - the title collides with the frame HUD;
  - "What we check" is cut off in the intro card;
  - at the verdict, the card covers the video and the stamp is cut off at the top, so "REALISTIC ON THE MOON" is unreadable;
  - the timeline labels crowd together.

Rules:
1. **Every stage label is laid out with the others.** Height chips, ruler labels, ghost labels, landing labels, "takeoff level" and the HUD are measured with `getBoundingClientRect`. Two labels whose rectangles intersect are moved apart, stacked, or merged into one chip ("0.170 m", not "0.1 m" plus "0.170 m"). Every label lies wholly inside the stage. A line or tick never crosses a label's text: the label gets a solid backing and sits above the line.
2. **On a phone (width ≤ 480 px) the verdict card goes below the video,** not over it. The stamp is wholly inside the viewport, and nothing else covers it. The intro card's text is never cut off: the card grows or scrolls. The title never overlaps the HUD.
3. **Tests (browser):**
   - At 1440 × 900 and 390 × 844, at each of `?event=scale|takeoff|apex|landing|verdict` on the Moon fixture, no two visible stage labels intersect, every label's rectangle lies inside the stage's rectangle, and no line or tick element crosses a label's rectangle.
   - At 390 × 844 with `?event=verdict`, the stamp's rectangle lies inside the viewport, and `elementFromPoint` at its centre is the stamp or a child of it.
   - The question text appears once in the page.
   - The rail's verdict frame equals the stage's frame at the verdict.

## 36. Owner addendum (2026-10-31, from Moon run 22): the chart's end labels tell each curve's own landing time

Seen: on Moon run 22's page, the height-vs-time chart labels the Moon curve "Moon -7.36 s", although the drawn Moon curve lands at about 1.0 s. A landing time is never negative.

- Each end label (`Earth X.XX s`, `Moon X.XX s`, `in the clip X.XX s`) states the time at which that drawn curve returns to the takeoff level. This is the same number the curve is drawn with, computed once from the takeoff speed and that world's g: `t = 2·v₀/g`, with `v₀` the upward takeoff speed in m/s from the fit and the scale. The label sits where the curve crosses zero, or at the chart's edge, with "→" when the crossing is off the chart.
- **Test (unit plus browser):**
  - for clip-a and for a result whose fit has a negative `y0` and a positive `v0` in px/s (Moon run 22's shape: `a_px_s2 = 122.6`, `v0 = 13.5`, `y0 = -57.2`), every end label's number is positive;
  - each label's number equals, within 0.02 s, the time at which that drawn curve's polyline crosses zero.

## 37. Owner addendum (2026-10-31): the chart's curves stay as they were; only the end labels are corrected (replaces § 36)

Seen: the generation for § 36 fixed the label, which on Moon run 22 now reads "Moon 1.02 s", but it broke the chart. It rebuilt every curve from one speed derived from the clip's airtime (`v0 = g·T/2`) and dropped the fit curve. On Moon run 22 the white fit and the Moon curve now peak at 0.20 m, while the measured dots peak at 0.12 m, so the fit no longer passes through the data. That generation was reverted. Section 36 is replaced by this one.

- **Curves are drawn exactly as before § 36:**
  - the measured dots come from the segment's `track`;
  - the white fit curve is the segment's `fit_curve_px`, converted with the scale, and it passes through the measured dots;
  - the world curves are the segment's ghost tracks (`ghosts[].points`) for each world.
  
  No curve is recomputed from a takeoff speed.
- **Only the end labels' numbers change:**
  - each world label reads the time at which that world's drawn curve returns to the takeoff level (height 0) after its peak, measured from the segment's takeoff time. It is found on the drawn polyline by linear interpolation between the two points around the crossing;
  - "in the clip" reads the measured airtime, from the segment's takeoff to its landing frame;
  - a curve that does not return to 0 inside the chart gets its last time and "→";
  - the labels never use `world_outcomes[].landing_time_s` minus a start time, the arithmetic that produced "Moon -7.36 s".
- **Labels stay apart:** "Moon 1.02 s" and "in the clip 1.03 s" are close in time but never overlap (§ 35 rule 1).
- **Tests (browser, Moon run 22's shape and clip-a):**
  - the root-mean-square vertical distance between the fit curve and the measured dots, in chart pixels, is under 4 px for clip-a;
  - every end label's number is positive and equals, within 0.02 s, the drawn polyline's own zero-crossing;
  - no two chart labels intersect.

## 38. Owner addendum (2026-10-31, from Moon run 22): a world's end label is the time its curve lands

Seen: after § 37, Moon run 22's chart reads "Moon 0.75 s · in the clip 1.03 s". The 0.75 s is when the Moon curve returns to takeoff height, but the astronaut lands 0.19 m lower. From part 11 § 31, each world's ghost ends at the clip's landing level, which can be below or above height 0.

- **Each world's end label** reads the time of its drawn curve's last point (its landing), measured from the segment's takeoff time. This replaces § 37's "returns to the takeoff level (height 0)".
- "in the clip" stays the measured airtime.
- The chart's height range covers every drawn point: dots, fit curve and every world curve down to its landing.
- Everything else in § 37 stays as written: curves are drawn as before, nothing is recomputed, the labels stay apart, and the fit RMS test still applies.
- **Tests (browser):**
  - for a result shaped like Moon run 22, where the landing is 0.19 m below takeoff and the Moon ghost ends there: the Moon label is within 0.05 s of "in the clip";
  - each world label equals its polyline's last-point time within 0.02 s;
  - no two chart labels intersect;
  - no drawn point lies outside the chart area.

## 39. Owner addendum (2026-10-31, from wall run 15): a verdict decided by a range check reads like one

Seen on wall run 15's page (verdict "impossible", decided by the range check `wall_height`, with no measured g):
- the stamp's gloss says "no playback speed makes this motion fit earth", although no motion was fitted;
- the verdict card and the summary show a world chip "Earth 0.0σ ✓";
- formulas render words as italic math letters run together ("wallheightfromcarpettotoplip", "lengthpx × mperpx");
- the two first-look motions show as timeline bars that read only "not measured", although the clock was measured on the first;
- on a 390 px phone the verdict card sticks out past the right edge.

Rules:
- **The stamp's gloss and the chips follow `verdict.decided_by`.** A verdict decided by a range check has no playback-speed gloss. Its gloss is the range check's own result, for example "9.6σ above the record range". A world chip with σ appears only when `verdict.g_measured` is not null.
- **Formulas never run words together.** A formula is rendered as math only when it is made of symbols, numbers and units. A formula with a run of three or more letters outside a backslash command (for example `length_px × m_per_px`) is shown as plain monospace text exactly as written.
- **A timeline bar names its motion.** A first-look motion without a segment shows its `description`. When the clock was measured over its frames, the bar also shows the clock's rate, for example "step rate 4.0 Hz". A bar never reads only "not measured".
- **Nothing sticks out on a phone.** At 390 px width the verdict card, the stamp and every overlay card lie inside the viewport.
- **Tests (browser, a result shaped like wall run 15 and clip-a):**
  - the range-decided stamp has no "playback speed" text, and no "0.0σ" chip appears anywhere;
  - no rendered formula contains "lengthpx" or "mperpx";
  - every timeline bar's text is non-empty and is not "not measured";
  - at 390 px, `document.documentElement.scrollWidth ≤ 390` and the verdict card's right edge is ≤ 390.

## 40. Owner addendum (2026-10-31, from the pages of Moon run 22, wall run 15 and hand run 8): labels that read right and never collide

Seen after § 38–39:
- **Moon run 22:** the chart's labels read "Earth 0.27 s · Moon 0.99 s", which is right, but "in the clip 1.03 s" is gone. On the timeline the long motion names now overlap: "Foreground leap" sits over "foreground astronaut standing after landing".
- **Hand run 8** (verdict kind `world`, decided by the range check `hand_length`, no measured g):
  - the verdict card's headline reads "World";
  - the stamp reads "REALISTIC ON THE EARTH ✓ · g within 2σ";
  - the timeline markers "Scale" and "Verdict" overlap.
- **Wall run 15:** the clock's "step rate 4.0 Hz" is added to both motion bars, although it was measured on the approach run only.

Rules:
- **The chart always shows "in the clip X.XX s"**, the measured airtime, next to the world labels. When labels are close in time they go on separate rows (§ 37); a label is never dropped.
- **A verdict decided by a range check reads like its kind:**
  - the headline is the verdict label: "Realistic on Earth", "Not realistic on Earth" or "Undetermined", never the raw kind such as "World";
  - the stamp names the world as § 31 writes it ("ON EARTH", "ON MARS", "ON THE MOON");
  - the gloss is the deciding range check's own result, for example "hand length inside its range" or "9.6σ above max";
  - "g within 2σ" and any g wording appear only when `verdict.g_measured` is not null.
- **Timeline labels never collide:**
  - a motion bar's label fits inside its bar: a longer name is cut with "…", and the full name is the bar's tooltip;
  - event marker labels that would overlap ("Scale", "Verdict") go on separate rows;
  - this holds at 1440 px and at 390 px.
- **The clock's rate goes on one bar only:** the motion bar whose frames overlap the `clock` calculation step's frames. When there is no such step, no bar shows a rate.
- **Tests (browser, results shaped like Moon run 22, wall run 15 and hand run 8, at 1440 px and 390 px):**
  - the Moon chart contains "in the clip 1.03 s";
  - hand run 8's headline is "Realistic on Earth", and its stamp contains neither "g within" nor "THE EARTH";
  - no two timeline labels' boxes intersect;
  - every motion bar label lies inside its bar's horizontal extent;
  - at most one bar shows a step rate.

## 41. Owner addendum (2026-10-31, from the Moon demo review): a world that needs a retime says so

Seen: a sceptic's first answer to the Moon clip is "Earth in slow motion". Part 11 § 41 now always weighs Earth, but a chip like "Earth 33σ ✗" does not say what it would take.

- **A world chip that does not fit at native speed adds the retime it would need,** taken from `retime_factor`:
  - "Earth 33σ ✗ · only if slowed ×2.48" when the factor is above 1;
  - "… · only if sped up ×1.20" when it is below 1;
  - two decimals.
- **A chip that fits stays as before:** "Moon 0.1σ ✓".
- **Chips wrap; they never overflow** the verdict card on a 390 px phone.
- **Test:** Moon run 22's result, with the Earth candidate of part 11 § 41, shows both chips, "Moon 0.1σ ✓" and "Earth 33σ ✗ · only if slowed ×2.48". Its exact σ and factor come from the data.

## 42. Owner review of the Moon page (2026-10-31): the figure, working controls, one screen

The owner watched the page of Moon run 22 from Play, next to the approved prototype (21.10). The prototype draws the whole astronaut: a cyan outline that follows the mask in short steps on every frame, Earth and Moon figures beside him, a chronophotograph of five astronauts along the arc. Run 22's page drew none of this, and its controls did not work. Where this section disagrees with an earlier one, this section holds.

**Fixture.** `fixtures/source/run-22/` is owner input: run 22's directory without logs (`artifacts/`, `input/`, `workspace/`, `result.json`, `summary.json`). The tests below build its page with `build_page`.

### 42.1 The figure is the whole moving body, not the tracked point

- **Definition.** A segment's *figure* is the whole object that moves with the tracked point. The tracked point can be any rigid part of it. On run 22 it is the backpack centre.
- **Selection.** The page build checks every SAM mask artifact of the run (segment masks and reference masks alike), object by object:
  1. on a frame of the segment, the object passes if its mask has a pixel within 3 px of the tracked point;
  2. the object must pass on ≥ 80 % of the segment's frames that have a tracked point;
  3. its mask area must be ≤ 35 % of the frame on each of those frames;
  4. among the objects that pass, the figure is the one with the largest median area;
  5. if none passes, the figure is the segment's own mask object (`segment.mask`).
- **Use.** The figure feeds the outline (§3.2), the spotlight (§18.3), the ghosts (§3.6), the chronophotograph (§3.7, §18.6), the landing ring, the hold camera (§42.7) and the ghost spacing (one figure-bbox width). The tracked point, trail, fit curve, takeoff level, I-beam and every number stay on the tracked point.
- **Missing frames.** A frame with no figure mask has no outline. Do not interpolate across more than 2 frames.
- **Seen.** Run 22 tracked the backpack centre. The page outlined a 30-px backpack as the body. The ghosts were two small rings on the backpack, and the chronophotograph had no figures. The whole astronaut's mask was in the run and unused: `t8_segment_0.npz`, object 0, frames 200–310, the "suited astronaut height" reference.
- **Tests on run 22:**
  - the figure is `t8_segment_0.npz` object 0;
  - at `event=apex` the drawn outline's bbox height is within 10 % of that mask's bbox height at frame 255;
  - each ghost silhouette's bbox height is within 10 % of it too;
  - at `event=landing` the chronophotograph draws ≥ 4 figure cut-outs, each ≥ 90 % of that height.

### 42.2 Outlines come from mask pixels only

- Every outline on the stage is traced from the mask pixels of a run artifact, per §25.1. This covers the figure, the references, the ghost rims and the chronophotograph rims.
- The result's polygons (`overlay[].outline`, `references[].mask.outline`) are never drawn, smoothed or not.
- A reference with no mask frame in the artifacts shows no outline, only its ruler.
- **Seen.** The build smoothed the agent's 12-vertex backpack polygon with Chaikin passes and drew it. The viewer saw a round blob instead of the backpack's edges. The prototype's outline follows the mask in short steps.
- **Tests on run 22:**
  - at `event=scale` the reference outline has ≥ 80 vertices, and its filled area has IoU ≥ 0.9 with the backpack mask at frame 200;
  - at `event=apex` the figure outline has ≥ 150 vertices.

### 42.3 Pause pauses; the timeline seeks

This replaces the hold-skip rule of §4 and §18.1.

- **Play/pause button and space:**
  - while the video plays: pause; the video stops and the overlays stay;
  - during a timed hold: pause the hold; its timer, camera drift, line reveal and animations stop where they are; the next press continues the hold from that point;
  - after the verdict: as before (ground truth on acceptance pages, else restart from 0).
- **Skipping a hold:** only the next-event button and ↓ skip. They end the current hold and go to the next event.
- **The timeline is a seek bar.**
  - Click or drag anywhere on it, touch included, and the video seeks to that frame and pauses.
  - The stage draws that frame's live layers (§18.4). Nothing from the future is drawn.
  - Within 2 frames of an event frame, the stage shows that event's sticky hold.
  - Play continues forward from there. Later events hold as usual; earlier events do not fire again.
  - The timeline's hit area is ≥ 24 px high.
- **The ride only moves forward.**
  - A hold seeks only to its own event frame, the frame the playhead just crossed.
  - The verdict hold starts only when the video reaches its last frame (`ended`, or the last frame), never earlier.
  - The `<video>` has no `loop`. After the verdict the picture stays on the last frame until the viewer acts.
- **Seen:**
  - the play button during a hold skipped the hold, so the viewer could not pause for most of the ride;
  - the timeline had no click handler;
  - on the wall page the ride played to 2.7 s, held, jumped to the clip end at 6.67 s and stopped on the dimmed verdict. The climb was never shown.
- **Tests, real time, in the browser.** Run them on run 22's page and on a synthetic portrait page. The test makes the portrait page itself: ffmpeg `testsrc` 720 × 1280, 30 fps, 6 s, plus a range-check result with one event at 2.0 s.
  1. **Ride.** Press Play. Every 0.25 s until the verdict (or 90 s), sample `video.currentTime`, the state and a hash of the stage pixels.
     - `currentTime` never decreases.
     - Outside holds, two samples never differ by more than 0.6 s of video.
     - The verdict appears only after `currentTime` ≥ duration − 1 frame.
     - Outside holds, the stage hash changes at least once every 1 s.
  2. **Pause while playing.** One second after Play, press pause. For 1.5 s `currentTime` stays within 1 frame and the stage hash does not change. Press play: `currentTime` moves again.
  3. **Pause in a hold.** In the Apex hold, press pause. For 1.5 s the hold bar's width does not change and the event title stays. Press play: the hold finishes its remaining time, then the video moves.
  4. **Seek.** Click the timeline at 25 %, 50 % and 75 % of its width. Each time:
     - `currentTime` is within 1 frame of that fraction × duration;
     - the player is paused;
     - the three stage hashes differ.
  5. **Drag.** Drag from 20 % to 60 %. `currentTime` takes ≥ 3 distinct values during the drag.

### 42.4 One screen, and the video in its own shape

- **No page scroll.** At 1440 × 900, 1280 × 720 and 390 × 844 the ride needs no vertical page scroll. The header, the stage and the control bar stay fully visible.
  - On desktop the side column is as tall as the stage plus the control bar and scrolls inside itself.
  - On phone the column goes below the control bar, and only the column scrolls.
- **The stage keeps the video's display aspect** (coded size × SAR). Its height is `min(free height, free width / aspect)`. A portrait clip gives a tall, narrow stage, centred, with the side column beside it. The picture is never stretched. Nothing is cropped beyond the 3 % camera overscan.
- **The column does not jump.** The chart and the step rows keep their size during the ride. The column scrolls at most once per event, smoothly, to the current step.
- **Seen:**
  - at 1440 × 900 the control bar was cut by the window bottom;
  - during play the wall's 720 × 1280 picture was stretched into a landscape box;
  - the side column jumped on every event.
- **Tests:**
  - at each of the three sizes, after Play and at `event=apex`, `document.scrollingElement.scrollHeight` ≤ the window height, and the play button and the timeline are fully inside the window;
  - on the portrait page the drawn picture's width ÷ height is within 1 % of 720 ÷ 1280.

### 42.5 Nothing on the page that the viewer does not need

This replaces §3.1, the "SAM 3 masks" badge, the hash in the "how this was made" drawer (§2) and the keyboard line (§4).

- **Removed from the visible page:**
  - the HUD line (frame number, `t`, fps) and "Freeze frame";
  - the SAM badge;
  - the template hash, cost, run id and model names;
  - the keyboard help line;
  - the agent's prose: mask descriptions, blind-check descriptions, step notes.
- **Kept, but not visible:** the hash stays as the HTML comment of §2 for the build check. The keys keep working, and the play button's `title` lists them.
- **A step in the side column** shows its title, one line with the formula or the value, and its value chip. Its agent prose appears only with "Full calculation" on.
- **On the video, only these:**
  - the event title and its one line of numbers (§3.4);
  - the outlines;
  - the ghosts, labelled "Earth" / "Moon" (never "Earth ghost");
  - the takeoff level and the I-beam chip;
  - the ruler chip and the reference card at Scale;
  - the chronophotograph heading at Landing.
- **Seen:**
  - the side column was a wall of 12-px monospace agent prose ("The green-tinted region covers the entire upright figure…");
  - the stage showed "frame 255/466 t = 8.51 s 29.97 fps Freeze frame" and "SAM 3 MASKS";
  - the page showed the template hash and the cost.
- **Test.** On run 22's page, in every state, the visible text contains none of these: "frame ", "fps", "Freeze frame", "SAM", "sha", "$", "Muse", "space = ". The visible text also contains no sentence from the result's mask or blind-check descriptions while "Full calculation" is off.

### 42.6 After a jump, its layers leave

- The layers of a jump fade out over 0.5 s. The fade starts 1.0 s after the landing hold ends, or 1.0 s after the landing frame when holds are off.
- These layers are: the ghosts with their labels and trajectories, the "landed at" labels, the takeoff level, the I-beam and its chip.
- The fit curve and the trail stay until the next segment starts.
- **Seen.** On run 22, after the landing hold, "Moon ghost", "Earth ghost", "takeoff level", "0.116 m" and "landed at 0.27 s" hung over the flag for 5 s. The astronaut had already walked out of that place.
- **Test.** On run 22, 2.0 s of video after the landing hold ends, the stage draws no ghost and no apex chip.

### 42.7 The hold camera frames the figure and its ghosts

This replaces the hold target of §18.2 and the zoom column of §18.1 where they differ.

- **Target.** The centre of the union of the figure's bbox and the ghosts' bboxes at the hold frame. At Scale, the union is the figure's bbox and the reference's bbox.
- **Zoom.** `min(the §18.1 table zoom, 0.85 × stage size ÷ union size)`, and never below 1.03.
- **Drift.** The §18.2 drift stays. It is capped so the union stays inside the view.
- **Seen.** Run 22's Apex hold zoomed 1.2× on the backpack. With the drift, the view became a blur of the astronaut's back, and the ghosts sat outside the view.
- **Test.** On run 22, at the end of each timed hold, every ghost's bbox and the figure's bbox lie inside the visible stage.

### 42.8 The chart is on top from the start

- As §8.1 says, the chart sits above the steps, outside the column's scrolling area.
- It shows empty axes on the first screen and grows with playback.
- **Seen.** On run 22 the chart was not visible during the ride. It appeared only at the verdict.
- **Test.** At `event=takeoff` and at `event=apex` the chart's box is fully visible inside the window.

## 43. Self-review of the §42 page (2026-10-31, run 22): silhouettes, not boxes

The §42 page of run 22 now draws the whole astronaut, plays forward to the verdict, pauses, and seeks from the timeline. Its ride, watched every 0.5 s from Play, still differs from the approved prototype in the points below.

### 43.1 A cut-out is a silhouette: the mask lives in the alpha channel

- **Seen.** Every ghost and every chronophotograph figure was a rectangle: the whole bbox of video pixels with its ground and sky, tinted. The build writes each cut-out's mask as `*.a.png`, an 8-bit **greyscale** PNG with no alpha channel. The player composites it with `destination-in`, which reads **alpha**, not grey. A greyscale PNG is opaque everywhere, so nothing was cut.
- **Rule.** The mask image the player composites carries the mask in its **alpha channel** (RGBA or grey + alpha), feathered as §25.2 says. Outside the silhouette the composed cut-out is fully transparent.
- **Test (browser, run 22).** After the cut-outs load, take the composed ghost image of frame 255:
  - a pixel in a bbox corner outside the mask has alpha 0;
  - the pixel at the mask's centroid has alpha > 200;
  - ≥ 25 % of the bbox pixels have alpha 0.

### 43.2 The chronophotograph keeps whole figures at video scale

- Each figure is the silhouette of §43.1 with its own thin outline (§43.4), at the size the astronaut has in the frame. The figures are not magnified.
- Every figure is whole inside the stage: no head or foot is cut by the stage edge.
- **Seen.** The figures were magnified rectangles; the helmets were cut by the stage top.
- **Test.** At `event=landing` on run 22, each figure's drawn bbox lies inside the stage, and its height is within 10 % of the figure mask's height × the stage's video-to-screen scale.

### 43.3 No zoom past the source's resolution

- **Rule.** A hold zoom never makes one source pixel larger than 2.5 screen pixels. The hold zoom is `min(the §42.7 zoom, max(1.03, 2.5 × source display width ÷ stage width))`.
- **Seen.** Run 22's 352 × 240 picture already fills a 960-px stage at 2.7 screen px per source px. The Scale and Apex holds zoomed 1.2–1.3 on top of that, and the picture turned to blur.
- **Test.** On run 22 every hold's camera zoom is 1.03.

### 43.4 Outlines are thin

- **Rule.** The core line of every outline is 1.5–2 CSS px wide at any zoom. Its glow is one wider stroke of ≤ 5 CSS px at ≤ 30 % opacity. This matches the prototype's `rim()`: core 1.5 px, glow 3.2 × core at 28 % opacity.
- **Seen.** The figure's outline was a ≈ 6-px cyan band with a wide halo, heavier than the figure itself.
- **Test.** At `event=apex` on run 22, the figure outline's core stroke width × its screen scale is between 1.4 and 2.2 px.

### 43.5 The side column has no agent prose and no frame numbers

§42.5 still leaked: each step showed the first line of the agent's prose, cut with "…" ("The tinted square covers the light blocky mass carried on the back of …"), and "centre of the backpack, a rigid part of the body".

- **Rule.** With "Full calculation" off, a step shows its title, its formula line and its value chip. It shows no word of the agent's descriptions, notes or point descriptions, cut or whole.
- **Also removed:** the frame numbers beside each step ("#200"), the "How this was made" block with "measurement steps above; build log in the run folder", and the "Summary" block that repeats the verdict card.
- **Test.** With "Full calculation" off, at every event of run 22, the visible text contains no run of 4 consecutive words from any `description`, `note`, `notes` or `point_description` string in the result, and no "#" followed by a digit.

### 43.6 Timeline labels are short and stay in the control bar

- **Rule.**
  - A measured segment is labelled "Jump 1", "Jump 2" (the motion kind and its index, as in the prototype).
  - An unmeasured segment, such as "standing", has no label.
  - Point events keep their one word ("Scale", "Verdict").
  - Every label lies inside the control bar, never over the stage.
- **Seen.** "foreground astronaut standing and crouchi…", "foreground astronaut standing aft…" and "For…" sat over the bottom of the stage and under the event caption.
- **Test.** On run 22 every timeline label's box lies inside the control bar's box, and no label is longer than 12 characters.

### 43.7 The first screen asks one question

- **Rule.** The first screen shows only these:
  - the question, large (as now);
  - one line, "What we check: …";
  - the "By eye, before measuring" card;
  - the "Watch the analysis" button.
- The scene paragraph, the "Claim:" line and the "What we see" card with its chips go to "Full calculation".
- The page header shows "Physics Proof" and the clip's source credit, never the question a second time.
- **Seen.** The question was printed twice (header and first screen), followed by a paragraph, a claim line, a check line, two cards and seven chips. The owner called it a mess of small text.
- **Test.** On run 22's first screen, the visible text has ≤ 60 words, and the question appears once.

## 44. Owner review (2026-10-31, in Firefox): the ride loops; every seek must land on its frame

The owner opened run 22's §43 page in Firefox, the default browser on the demo machine. He pressed play. The video did not play up to Scale, hung, then reached the jump and went round in a circle. The page had passed every test, because every browser test ran in Chrome only.

- **Cause.** `seekFrame()` calls `video.fastSeek(t)` when the browser has it. Firefox and Safari have it; Chrome does not. `fastSeek` lands on the nearest keyframe, not on the asked time. The page video has two keyframes, at 0.00 s and 8.34 s (libx264 default keyframe interval). Every hold before 8.34 s therefore sent the picture back to 0.00 s. The playhead then crossed the event again, and the next hold sent it back again, so the ride looped.

### 44.1 Seeks are exact
- **Never call `fastSeek`.** Every seek sets `currentTime` to the frame's time. The stage draws only after `seeked`, as §16 says.
- **A hold seeks only when it must.** When the playhead crosses an event, the hold seeks to the event frame only if `|currentTime − event time|` > half a frame.
- **The page video has a keyframe at least every 0.5 s.** Use libx264 `-g` = round(fps / 2) and `-keyint_min` = the same value. This keeps exact seeks fast in every browser.

### 44.2 The ride cannot repeat itself
- **An event fires at most once per ride.** The player keeps the set of events that have fired in this ride.
  - An event leaves the set only when the viewer seeks to a frame before it (timeline, step click, previous-event button, arrow keys).
  - Play from the start (first-screen button, the round play button before the first start, restart after the verdict) clears the set.
- **The playhead does not move back by itself.** After a hold resumes, the video may report a time before the hold's frame. The player then seeks to the hold's frame again. It does not re-fire the events in between.
- **The two start buttons behave the same.** The first-screen "Watch the analysis" button and the control bar's round play button both start the same ride from 0.

### 44.3 Tests run in three browser engines
- **Engines.** The real-time ride tests of §42.3 (ride, pause while playing, pause in a hold, seek, drag) run in Chrome (installed, §16.2), in Playwright's Firefox and in Playwright's WebKit. All three are present on the machine.
- **Each ride test runs twice:** once started from "Watch the analysis", once from the round play button.
- **If an engine cannot decode the page video,** the test fails with that message. It does not skip.
- **Extra assertions:**
  - in each engine, every event caption is seen exactly once per ride;
  - `currentTime` never drops by more than one frame during a ride;
  - the verdict appears within (clip length + sum of hold durations + 5 s) of wall time.
- **The keyframe test.** `ffprobe` of the page video shows no gap above 0.5 s between keyframes.

## 45. Self-review (2026-10-31, the sped-up Moon page): the build trims, it does not fail

The page of the sped-up Moon clip did not build: "page build: page without video is 1095275 bytes, limit 1000000". The `smooth_loops` block held 844 KB: the figure's outline for 153 frames, already smoothed by two Chaikin passes, so each loop held 4× the traced points, written as decimal pairs.

**Fixture.** `fixtures/source/fake-1/` is owner input: the run of the Moon clip sped up ×2.46 by the owner, without logs, with its result re-validated by the current part 11.

- **Loops are stored before smoothing.** The build stores each outline loop as its marching-squares points (§25.1). They lie on the half-pixel grid, so it writes them as integers in half-pixel units: the first point absolute, then deltas, in one compact string per loop. The player decodes the loops and runs the two Chaikin passes itself, once per loop, with the same result as now. Every outline drawn on the stage matches the build-side smoothing within 0.05 px.
- **Cut-outs are inlined once.** A cut-out lives in the page as data URLs only (§20.1 needs that on `file://`). The build does not also write it as a file.
- **Over the limit, the build trims; it does not fail.** It trims in the §12 order and logs each trim:
  1. outline loops of frames outside the segment windows ± 1 s;
  2. the chronophotograph interval;
  3. ghost-frame density.
  It raises only if the result and summary data alone exceed the limit.
- **Tests:**
  - the pages of `fixtures/source/run-22/` and `fixtures/source/fake-1/` build, and each is < 1 MB without the video;
  - on run 22's page the figure loops take ≤ 200 KB;
  - a decoded, smoothed loop matches the build-side smoothing of the same mask within 0.05 px at every point;
  - a page forced over the limit (a test that lowers the limit) still builds and logs its trims.

## 46. Owner review (2026-10-31, in Firefox): the picture stands still while the time runs

The owner pressed Play in Firefox. The time readout and the timeline moved; the picture on the stage did not. It showed the frame of the last seek. The cause: the freeze canvas lies over the video in `#vbox` and stays visible all the time. It is redrawn on every `seeked` and every hold, never cleared, so during playback the viewer sees an old still frame over the live video. The tests read `currentTime`, not the pixels the viewer sees, so they passed.

### 46.1 The freeze canvas shows only while the video is paused
- **While the video plays, the freeze canvas is hidden** (`visibility:hidden`); the viewer sees the live video. The player hides it on the video's `playing` event.
- **When the video pauses** (a hold, the pause button, the end), the player draws the current frame into the canvas and shows it. It also redraws it on every `seeked`, as now.
- **Range-only pages** (no video) keep their present behaviour.

### 46.2 Tests check the pixels the viewer sees
- **The stage-moves test.** Start the ride (each start button), then every 0.25 s take a screenshot of `#stage` and read `currentTime`, `paused` and the hold state. For every pair of samples where the video plays (not paused, not in a hold) and `currentTime` advanced by more than 0.05 s, the two screenshots differ. At most 20 % of such pairs may be equal.
- **Where it runs.** Chrome, Playwright's Firefox and Playwright's WebKit (§44.3); the page is opened both from `file://` and from a local HTTP server (`python -m http.server`), because the page is published on GitHub Pages.
- **The paused-frame test.** Pause in the middle of a free run (not in a hold). 0.5 s later the freeze canvas is visible, and the frame it was drawn from (`data-drawn`) is within 1 frame of `floor(currentTime × fps)`, not an earlier frame.

## 47. Owner review (2026-10-31, the §46 page): the calculation column is a log; the video is loaded before the ride

The owner liked the stage. Two things were wrong. The right column did not keep the calculations: lines appeared and vanished, at the verdict every step folded to its heading, and a heading clicked later showed nothing ("Independent clock", "Uncertainty" and "Measured gravity" looked empty). The error-budget bars all read 0.0 %. And the video stuttered for 1–1.5 s at the start in Firefox.

### 47.1 The column is a log that follows the ride
- **A reached step stays open with all its lines.** A step opens when the ride reaches it (its frame or its place in the order) and stays open to the verdict. Its lines appear one after another (0.35 s apart) during its event's hold, and at once otherwise.
- **The column follows the newest line.** Each time a line or a step appears, the column scrolls smoothly so the newest line sits at the bottom of the column (16 px above its lower edge). Older steps move up. The chart above the column does not move. The column does not scroll by itself at any other time, so the viewer can scroll up during the ride.
- **No fold at the verdict.** At the verdict every step is open with all its lines, and the column ends with the Verdict step at the bottom. Scrolling up shows every step, each with its calculation.
- **A backward seek** (timeline, step heading, previous event) closes the steps after the new frame and hides their lines; the steps before it stay open with all lines.
- **A clicked heading** shows that step with all its lines, as well as seeking (§42.3).

### 47.2 Every step in the column says something
- **Each step shows its one-sentence explanation** (the `text` block of `short`), its formula and its value chip. The rest of `short` and `full` and the caveats show only with Full calculation (§42.5 concerned agent prose, not these sentences).
- **No empty step.** A step with no line to show is not listed.
- **A chip carries a number.** A chip without a digit ("measured gravity", "error budget") is not shown, except the verdict step's world. Error-budget values stay on one line.
- **Motions that were not measured** (`first_look.motions` without a `segment_id`) are not steps in the column; they show only with Full calculation.
- **A reference step is titled by its reference,** "Reference: <reference name>", and shows "<size> m over <length> px". Two references never give two steps with the same heading.
- **The error budget** reads each component's `sigma_contribution` (in the unit of the measured value), sorts the components largest first, draws each bar in proportion to the largest, labels it "± <value>", and ends with "σ = √Σσᵢ² = <sigma_total> <unit>". Component names are plain words: reference size, pixel reading, parabola fit, tracked point ≠ centre of mass, reference reading, first vs second half; the component's `basis` is the bar's tooltip.

### 47.3 The video is loaded before the ride starts
- **Over HTTP(S)** (GitHub Pages) the player fetches the whole clip once, as a blob, and plays it from an object URL. On `file://` it uses the file directly.
- **The ride starts only when the video can play through** (`canplaythrough`). A start pressed earlier shows "Loading video…" on the button and starts the ride by itself when the video is ready.
- **No seek at the start when the video already stands at frame 0** (within half a frame): a seek followed at once by `play()` stalls Firefox for about a second.
- **Tests:**
  - the stage-moves test of §46.2 also holds in the first 1.5 s after the click: no more than 2 equal stage screenshots in a row while `currentTime` advances;
  - over HTTP, the page sets the video's `src` to a `blob:` URL;
  - at the verdict every listed step is open, every line is shown, no step has zero lines, and the column's scroll position is at its end (within 20 px);
  - on run 22's page the error budget shows six bars, the largest "± 0.221", and "σ = √Σσᵢ² = 0.246 m/s²".

### 47.4 Self-review of the sped-up Moon page (same day)
- **The retimed stamp reads the direction.** Part 11 §42 stores `verdict.factor` as k > 1 and `verdict.direction` as "sped" or "slowed". The stamp prints "NOT REAL SPEED · SPED UP ×<k>" or "… SLOWED ×<k>" (k to one decimal) from `direction`; only a result without `direction` falls back to the old rule (factor below 1 = sped up, k = 1/factor). Its second line reads "at real speed it fits the <world>". The headline without g reads "sped up ×<k> from <world>" or "slowed ×<k> …". The page of `fixtures/source/fake-1/` must say "SPED UP ×2.1"; the old page said "SLOWED ×2.1".
- **A range event's timeline tick reads "Size check"**, not the reference name cut at 12 characters ("suited figur").

## 48. Owner review (2026-11-01, Moon page against the sped-up page): the same footage draws the same page

The owner compared the two pages frame by frame. The sped-up page stopped for Scale 0.33 s after Play, its outline flickered during 4 s of walking, and the chronophotograph's Moon curve ran off the stage. The run measured a different jump and a reference at frame 10 (parts 07 §21, 08 R-M6/R-M7/R-S11 now make every run see and use both jumps). The player must also not depend on such choices.

### 48.1 Outlines only around a flight, never flickering
- **The figure's outline shows during free playback only inside each measured flight's window:** from 1 s before its takeoff to 1 s after its landing. The Scale hold still draws the reference outlines at its own frame.
- **A frame whose figure mask is an outlier is not drawn:** its area differs by more than 25 % from the median of its ±3 neighbouring frames. The last good outline stays for at most 2 frames; after that nothing is drawn until a good frame comes.
- **Test:** on the page of `fixtures/source/fake-1/`, no outline is drawn at frames 20–90 (the walk before the first window), and none of the frames 32–48 (planted area jumps in that run's masks) draws an outline.

### 48.2 Several jumps
- **Each measured segment plays as "Jump 1", "Jump 2"** with its own Takeoff, Apex and Landing holds, ghosts and chronophotograph (§27, unchanged).
- **The chart shows every jump on one time-since-takeoff axis:** the first-check jump in the present colours; each confirmation jump's measured points and fit in the same colours at 60 % opacity, labelled at its last point ("Jump 2"). The world curves are drawn once, from the first-check jump's takeoff.
- **The verdict card** shows the combined g (part 11 §43) and, under it, one line with each jump's g: "Jump 1: 1.59 ± 0.25 · Jump 2: 1.62 ± 0.30".
- **The calculation column** shows the "Jumps agree" step after the jumps' fit steps.

### 48.3 The chronophotograph stays inside the stage
- **World curves are clipped to the stage.** A world whose landing lies beyond the time axis does not draw its label off the axis; it draws an arrow at the axis end with its landing time ("Moon 2.53 s →").
- **Test:** on the page of `fixtures/source/fake-1/`, every ghost-curve point and every label of the chronophotograph lies inside the stage box.
