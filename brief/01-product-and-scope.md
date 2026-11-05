# 01 — Product and Scope

**Owns:** the product definition. No runtime code; every other part is checked against this file, and part 15's demo plan is built from it.

## 1. What this is

A system that takes **one video** and answers a physics question about the motion in it: **in which world is this motion true?** Not "real or fake", not an authenticity score. The possible shapes of the answer (specified in part 02):

- the motion fits a world's gravity at normal speed ("g = 1.73 ± 0.23 m/s², fits Moon — Earth ruled out");
- it fits a world only if the clip was retimed ("slowed down ×1.5");
- it fits no world at any playback speed ("physically impossible");
- or the system cannot tell ("undetermined", with the reason).

## 2. Who it's for and how it's judged

The audience is the **Meta hackathon judges** (deadline Nov 4). They receive:

1. **A demo video** — a recording of the system analysing and presenting clips. This is the primary artefact if nothing can be run live.
2. **The public repo** — this spec (`brief/`), the full source, the clip-preparation script and both Apollo test clips (part 03). The wall-run clip is *not* in the repo (third-party); it is passed to the system by path.
3. **Live pages on GitHub Pages** — one precomputed player page per analysed clip, plus a gallery page linking them. Pages are static and precomputed; no analysis runs on Pages.

Anyone with the repo can run a **fresh analysis with one command** on a Mac. A fresh analysis typically takes **7–11 minutes** (hard acceptance limits: 30 min and $2 per run, part 03). Judging must never depend on a live run succeeding on stage.

## 3. The user experience, end to end

1. The user supplies one video file (path on their machine). That is the *only* input: no title, no description, no hints (part 05 enforces this).
2. They run one command. Spark, as orchestrator in the agent loop (parts 06–07), measures the clip and submits a result data file (part 12).
3. They open the result in the **player** (part 13): a static web page, no framework, no build step, works from a local file and on GitHub Pages, on desktop and phone, in English.
4. In the player, **the same video plays and everything is drawn on top of it**: the outline of the body, the tracked point and its trail, the fitted curve, and a "ghost" showing where the relevant gravity would actually have put the body.
5. The video **pauses by itself at the key moments** (e.g. takeoff, apex, landing) with a short caption. The **calculation appears step by step** beside the video. At the end there is a **big verdict** — label plus the measured number (part 02).
6. **No voice.** Text and graphics only.

One player template, frozen. For each video, only the video file and its result data file change.

## 4. In scope

- **Motion types** (Spark decides per clip what is measurable, parts 06/08):
  - a body moving **unsupported**: jumps, throws, falls — any ballistic/free-flight segment;
  - a body **sliding along a vertical surface**: a vertical wall's normal force is horizontal, so (under this product's physics assumption) friction cannot hold the body up and its **vertical motion must still follow g**. This is what makes the wall run testable.
- Any clip where Spark can find such a segment, a scale, and — where the verdict needs one — an independent clock (part 02). Any clip where it cannot is a legitimate *undetermined*, not a failure of the product concept.
- Precomputed publication (GitHub Pages gallery + per-clip pages) and one-command re-analysis.

## 5. Explicitly out of scope

- Generic deepfake/authenticity detection, editing or splice detection, audio forensics, and any "real vs. fake" score.
- Identifying who made a clip, where it came from, or anything requiring knowledge beyond the video itself. The system must work — and in the tests, must be *seen* to work — from the video alone.
- Motion with no unsupported or vertical-surface phase (e.g. a car driving, a person walking the whole time) as a *measurable* target: the correct output there is undetermined/not measurable, not a forced verdict.
- Real-time or live-stream analysis; batch queues; multi-video comparison inside one analysis (the test harness compares separate runs, the product never does).
- A backend service, accounts, uploads. Analysis runs locally on the owner's Mac (M3 Max, 36 GB, macOS 26); presentation is static files.
- Voiceover, narration, or any audio output.

## 6. Non-negotiable product properties

These are stated here and specified where they are enforced:

| Property | Enforced in |
|---|---|
| Video-only, anonymised input; no clip identity or expected answer reaches the agent | 05, 03 (prompt-leak test), 07 (search blindness filter) |
| Every model call is a Meta model (Spark / SAM 3.1 via the Meta Model API) | 04, 14 |
| Every number in the result is produced by executed code, with provenance | 07 (sandbox), 09, 10, 11 |
| "Undetermined, with reason" is a first-class, respectable outcome | 02, 11 |
| Verdict shows the number *and* the world | 02, 12, 13 |
| One frozen player template; per-clip variation is data only | 12, 13 |

## 7. Success, in one paragraph

The three blind test clips of part 03 are told apart to the tolerances of part 03, repeatably (2 of 3 runs each), within budget, with at least one blind mask check per run — and a judge watching the player can *see* why: the track, the fit, the ghost, the steps, and the verdict all agree with each other.

## Owner decision (2026-10-28): identify what is in the frame, research it, never look up the answer

The owner: "When we analyse, we must think about what is in the video and look it up: who this person is, their height, their boot size. The original version did all of this." The approved prototype read the scene as "NASA Apollo 16 footage of John Young's jump salute filmed by Charles Duke, April 21, 1972", took the backpack size from Apollo documents and the jump from the boot soles. The ninth run, blocked from searching "Apollo …", took "the global average adult male, 171 cm" for a suited astronaut.

- **Identification from the pixels is in scope.** The agent works out, from the frames alone, what and who is in the clip, as specifically as the footage allows: the place, the era, the event, the specific person, the model of a vehicle or device. It then searches for the facts that give sizes: that person's height, that suit's and those boots' dimensions, that model's length.
- **Still out of scope:** the input's identity reaching the agent from outside the frames (filename, metadata, title, the operator's words), and any lookup of the clip's answer. That means searching for the clip itself, for an analysis of it, for "real or fake", or for the gravity or jump height someone measured in it. The verdict is still computed by code from the measurements (part 06 §2), and the scale is still cross-checked by two or three references (part 08 R-S6), so knowing the scene does not let the agent pick the answer.
- This amends §5's "anything requiring knowledge beyond the video itself": knowledge about what the video shows is allowed, knowledge about the video is not.

## Owner addendum (2026-10-29, from wall run 5 and a third test clip): the clip's own question, answered in the scene's world

Seen: wall run 5 measured g = 8.92 ± 1.06 m/s² on a city street, then listed the Moon and Mars only to rule them out, and asked "Does the wall ascent match Earth gravity?". A viewer of that clip asks something else: can a person really run up a wall this tall? The owner's direction: the system works out for itself what the clip asks it to prove, and proves it with measurements. What we check is physical truthfulness: is what the clip shows realistic?

- **The question comes from the clip.** Spark first works out, from the frames alone, what happens and what a viewer would doubt about it: what the clip shows or claims that might not be real. It writes that as one plain question a measurement can settle ("Can a person run up a wall this tall?", "Is this hop realistic on the Moon?", "Can a human hand have these proportions?"). The question names no physics term the viewer did not bring.
- **The world is the scene's.** Ordinary footage is on Earth; the Moon only when the scene itself shows the Moon. That one world is the only one tested. Other worlds are not tested, listed or mentioned, unless the question itself names one. On the Apollo clip the astronaut rises high because the clip is on the Moon; on the wall clip the Moon and Mars have nothing to do with the question.
- **The answer is realistic, not realistic, or undetermined, in that world**, always with the measured number and what it was compared with (part 02 §8). It replaces §1's "in which world is this motion true?": the measurement (g from a free-flight or wall segment, clock, error budget) stays as it is; the question and the wording change.

## Owner addendum (2026-10-29): a measured size, ratio or duration against a sourced real range

The clip's question is not always about gravity. "Can a person run up a wall this tall?" asks about a height; "Can a human hand have these proportions?" asks about a ratio in a still image. The owner's reference is a human analysis of the second question (TikTok @learnwithsherlock, "iPhone Duo Math", 2026-09-29, link only): the phone's published width (164.6 mm = 566 px) gives the hand's length (659 px ≈ 19 cm); a public body-measurement survey (ANSUR II, 2012) gives the human range of palm length / hand length (53–68 %, mean 60 %); a hand at 48 % is outside it, so that hand is not realistic.

- **Range checks are part of the product.** Besides g, the system measures any quantity the question needs — a length, height, ratio, duration or speed — and compares it with a **real range from a source** (min, typical, max, for the same kind of thing). Inside the range within uncertainty: realistic; outside it by more than 2σ: not realistic; otherwise undetermined.
- **A clip may answer with range checks only** (a still image, a pose, a size), with g only (a jump on the Moon), or with both (a wall run: the height reached against records, and the airborne part against g).
- **The answer combines the parts:** any part not realistic → not realistic; at least one part realistic and none not realistic → realistic; otherwise undetermined (part 02 §9).
