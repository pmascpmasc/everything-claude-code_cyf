// Competition-scale concept massing (NIAR outdoor obstacle course). Units: mm.
// x forward, y left, z up, ground z = 0. Massing only, not a build drawing.
//   openscad -D 'view="tracked"' -o t.png competition-concepts.scad
// Views: tracked, whegs, axle, tracked_stairs, tracked_hurdle
view = "tracked";
$fn = 64;

// ---- Concept 1: tracked body + front flippers ----
trk_r = 100;          // sprocket / idler radius incl. track
trk_c = 700;          // sprocket centre distance -> ~800 mm ground contact
trk_w = 130;          // track width
body_w = 380;         // hull between the tracks
flip_l = 360;         // flipper length (pivot to tip)
flip_r_tip = 55;

module track_loop(c = trk_c, r = trk_r, w = trk_w) {
  color("#1a1a1a") rotate([90, 0, 0]) linear_extrude(w, center = true)
    hull() { circle(r); translate([c, 0]) circle(r); }
  color("dimgray") for (x = [0, c]) rotate([90, 0, 0]) cylinder(r = r * 0.55, h = w + 4, center = true);
}

module flipper(angle) {
  // pivots on the front sprocket axis; angle 0 = pointing forward, + = tip up
  rotate([0, -angle, 0]) color("#222") rotate([90, 0, 0]) linear_extrude(70, center = true)
    hull() { circle(trk_r * 0.9); translate([flip_l, 0]) circle(flip_r_tip); }
}

module manta_hull() {
  // low wedge shell between the tracks, Manta styling language
  color("#2b2f36") hull() {
    translate([trk_c + 60, 0, 30]) scale([40, body_w / 2 - 20, 25]) sphere(1);
    translate([trk_c / 2, 0, 60]) scale([trk_c / 2 + 40, body_w / 2, 70]) sphere(1);
    translate([-90, 0, 40]) scale([30, body_w / 2 - 10, 50]) sphere(1);
  }
  color("deepskyblue") for (s = [-1, 1]) hull() {
    translate([trk_c + 70, s * 120, 35]) sphere(6);
    translate([trk_c - 120, s * (body_w / 2 + 2), 70]) sphere(6);
  }
  color("#0b0d10") translate([trk_c - 150, 0, 120]) scale([120, 110, 30]) sphere(1);   // camera / sensor glass
  color("red") translate([200, 0, 135]) cylinder(d = 60, h = 30);                       // E-stop
  color("gold") translate([trk_c - 120, 0, 140]) cylinder(d = 8, h = 220);              // FPV / GNSS mast
}

module tracked(flip = 15) {
  // origin = rear sprocket axis
  for (s = [-1, 1]) translate([0, s * (body_w / 2 + trk_w / 2), 0]) track_loop();
  for (s = [-1, 1]) translate([trk_c, s * (body_w / 2 + trk_w + 40), 0]) flipper(flip);
  manta_hull();
}

// ---- Concept 2: six tri-spoke wheel-legs (whegs) ----
wheg_r = 260;
module wheg(phase) {
  color("#222") rotate([90, 0, 0]) for (a = [0, 120, 240]) rotate([0, 0, a + phase]) {
    hull() { cylinder(r = 30, h = 50, center = true); translate([wheg_r - 30, 0, 0]) cylinder(r = 30, h = 50, center = true); }
    translate([wheg_r - 30, 0, 0]) rotate([0, 0, 90]) scale([1, 0.5, 1]) cylinder(r = 45, h = 50, center = true);  // rubber foot
  }
}
module whegs() {
  for (i = [0, 1, 2], s = [-1, 1])
    translate([i * 420 - 420, s * 300, wheg_r]) wheg(i % 2 * 60 + (s > 0 ? 0 : 60));
  color("#c8c8c8") hull() {
    translate([520, 0, wheg_r]) scale([80, 200, 60]) sphere(1);
    translate([0, 0, wheg_r + 20]) scale([500, 230, 100]) sphere(1);
    translate([-520, 0, wheg_r]) scale([60, 210, 70]) sphere(1);
  }
  color("orangered") for (s = [-1, 1]) translate([0, s * 232, wheg_r + 20]) cube([700, 4, 12], center = true);
  color("red") translate([-200, 0, wheg_r + 110]) cylinder(d = 60, h = 30);
}

// ---- Concept 3: two-axle 4WD, oscillating front axle, big tyres ----
tyre_d = 480;
module axle4wd() {
  for (x = [0, 650], s = [-1, 1])
    color("#1a1a1a") translate([x, s * 330, tyre_d / 2]) rotate([90, 0, 0]) cylinder(d = tyre_d, h = 160, center = true);
  color("silver") translate([650, 0, tyre_d / 2]) rotate([90, 0, 0]) cylinder(d = 40, h = 520, center = true);
  color("orange") hull() {
    translate([820, 0, tyre_d / 2 + 30]) scale([60, 160, 50]) sphere(1);
    translate([325, 0, tyre_d / 2 + 60]) scale([420, 230, 100]) sphere(1);
    translate([-140, 0, tyre_d / 2 + 40]) scale([50, 200, 80]) sphere(1);
  }
  color("red") translate([200, 0, tyre_d / 2 + 160]) cylinder(d = 60, h = 30);
}

// ---- Obstacles ----
rise = 200; run = 286;   // 5 steps, 35 degrees
module stairs() {
  color("#9aa") for (i = [0 : 4]) translate([i * run, -650, 0]) cube([run * (5 - i) + 600, 1300, rise * (i + 1)]);
}
module hurdle(h = 200) { color("gold") translate([0, -1200, 0]) cube([100, 2400, h]); }

stair_angle = atan(rise / run);
if (view == "tracked") tracked();
else if (view == "whegs") whegs();
else if (view == "axle") axle4wd();
else if (view == "tracked_stairs") {
  stairs();
  // Track bottom rests on the line through the step noses (z = x * tan + rise),
  // shifted so the rear idler sits on the second nose.
  translate([run * 1.2, 0, rise + run * 1.2 * tan(stair_angle)])
    rotate([0, -stair_angle, 0]) translate([0, 0, trk_r]) tracked(-10);
} else if (view == "tracked_hurdle") {
  translate([trk_c + 200, 0, 0]) hurdle();
  translate([0, 0, trk_r]) tracked(35);
}
