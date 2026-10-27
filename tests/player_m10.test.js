/* M10 node probe: pure player.js logic, no DOM. Run with: node tests/player_m10.test.js */
"use strict";

const path = require("path");
const player = require(path.join(__dirname, "..", "player", "player.js"));
const { parseQuery, collectNotices } = player;

let failures = 0;
function check(name, actual, want) {
  const a = JSON.stringify(actual);
  const w = JSON.stringify(want);
  if (a !== w) {
    failures += 1;
    console.log("FAIL " + name + ": got " + a + ", want " + w);
  } else {
    console.log("ok " + name);
  }
}

check("step basic", parseQuery("?step=2", 8), { step: 2, frame: null });
check("step clamp", parseQuery("?step=99", 8), { step: 7, frame: null });
check("step garbage", parseQuery("?step=x", 8), { step: null, frame: null });
check("frame only", parseQuery("?frame=381", 8), { step: null, frame: 381 });
check("frame negative", parseQuery("?frame=-2", 8), { step: null, frame: null });
check("both", parseQuery("?step=1&frame=90", 5), { step: 1, frame: 90 });
check("empty", parseQuery("", 8), { step: null, frame: null });

const page = {
  has_timescale: false,
  flights: [
    { chart: {}, overlay: { notice: "notice.no_px" }, ghost_missing: false },
    { chart: { notice: "notice.no_flight_points" }, overlay: {}, ghost_missing: true },
  ],
};
check("notices", collectNotices(page), {
  clock: "notice.no_timescale",
  "motion-0-overlay": "notice.no_px",
  "motion-1-chart": "notice.no_flight_points",
  "motion-1-ghost": "notice.no_ghost",
});

const clean = { has_timescale: true, flights: [{ chart: {}, overlay: {}, ghost_missing: false }] };
check("no notices", collectNotices(clean), {});

if (failures > 0) {
  console.log(failures + " failures");
  process.exit(1);
}
console.log("player.js logic ok");
