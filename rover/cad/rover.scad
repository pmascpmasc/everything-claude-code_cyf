// 6WD rocker-bogie rover — printable parts (units: mm).
// Export one part at a time, e.g.:
//   openscad -D 'part="rocker"' -o rocker.stl rover.scad
// Parts: rocker (x2, mirror one in slicer), bogie (x2), body, diff_bar,
//        diff_bracket, sonar_bracket, assembly (preview only).
part = "assembly";

$fn = 48;

// ---- Purchased hardware ----
n20_w = 12;            // N20 gearmotor cross-section
n20_h = 10;
wheel_d = 60;          // any 3 mm D-shaft wheel, 43–65 mm
m3 = 3.4;              // M3 clearance
m4 = 4.3;              // M4 clearance (pivot bolts)

// ---- Geometry (side view, rocker body pivot at origin) ----
plate_t = 6;           // arm plate thickness
arm_w = 14;
hub_r = 9;
front_axle = [75, -55];
bogie_pivot = [-47.5, -30];
bogie_half = 37.5;     // bogie axle offset from its pivot (x)
bogie_drop = 25;       // bogie pivot height above axles
link_lug = [25, 12];   // differential link attachment on rocker

block_h = 16;          // motor clamp height
block_wall = 4;

// ---- Body ----
body_l = 180;
body_w = 110;
body_h = 60;
wall = 4;
pivot_from_edge = 15;  // rocker pivot hole above the side-wall bottom edge

module bar(a, b, w = arm_w, t = plate_t) {
  hull() {
    translate(a) cylinder(d = w, h = t);
    translate(b) cylinder(d = w, h = t);
  }
}

// N20 clamp: rectangular pocket through, motor slides in, M3 set screw.
module motor_block(h) {
  ow = n20_w + 2 * block_wall;
  oh = n20_h + 2 * block_wall;
  difference() {
    translate([-ow / 2, -oh / 2, 0]) cube([ow, oh, h]);
    translate([-(n20_w + 0.3) / 2, -(n20_h + 0.3) / 2, -1]) cube([n20_w + 0.3, n20_h + 0.3, h + 2]);
    translate([0, 0, h / 2]) rotate([90, 0, 0]) cylinder(d = 2.8, h = oh);  // tap M3
  }
}

module pivot_hole(p, d = m4) {
  translate([p[0], p[1], -1]) cylinder(d = d, h = 100);
}

module rocker() {
  // Front clamp is taller so the front wheel lines up with the outboard bogie wheels.
  front_h = block_h + plate_t + 1;
  difference() {
    union() {
      bar([0, 0], front_axle);
      bar([0, 0], bogie_pivot);
      bar([0, 0], link_lug, 12);
      cylinder(r = hub_r, h = plate_t);
      translate(bogie_pivot) cylinder(r = hub_r, h = plate_t);
      translate(front_axle) motor_block(front_h);
    }
    pivot_hole([0, 0]);
    pivot_hole(bogie_pivot);
    pivot_hole(link_lug, m3);
    translate([front_axle[0], front_axle[1], -1])
      cube([n20_w + 0.3, n20_h + 0.3, 2 * front_h], center = true);
  }
}

module bogie() {
  l = [-bogie_half, -bogie_drop];
  r = [bogie_half, -bogie_drop];
  difference() {
    union() {
      bar([0, 0], l);
      bar([0, 0], r);
      cylinder(r = hub_r, h = plate_t);
      translate(l) motor_block(block_h);
      translate(r) motor_block(block_h);
    }
    pivot_hole([0, 0]);
    for (p = [l, r]) translate([p[0], p[1], -1])
      cube([n20_w + 0.3, n20_h + 0.3, 2 * block_h], center = true);
  }
}

// Arduino Uno mounting holes (official drawing), origin = board corner.
uno_holes = [[13.97, 2.54], [15.24, 50.8], [66.04, 7.62], [66.04, 35.56]];
uno_origin = [8, 8];
// L298N red module: ~43 mm board, holes on a 37 mm square — measure yours.
l298_origin = [96, 12];
l298_pitch = 37;
// 2x18650 holder, two M3 holes on its centre line — measure yours.
batt_holes = [[110, 78], [160, 78]];
diff_x = body_l / 2 + link_lug[0];

// Printed upside down: deck on the bed, side walls up. No supports needed.
module body() {
  difference() {
    union() {
      cube([body_l, body_w, wall]);
      cube([body_l, wall, body_h]);
      translate([0, body_w - wall, 0]) cube([body_l, wall, body_h]);
    }
    // rocker pivots
    translate([body_l / 2, -1, body_h - pivot_from_edge]) rotate([-90, 0, 0]) cylinder(d = m4, h = body_w + 2);
    // electronics
    for (h = uno_holes) translate([uno_origin[0] + h[0], uno_origin[1] + h[1], -1]) cylinder(d = m3, h = wall + 2);
    for (i = [0, 1], j = [0, 1])
      translate([l298_origin[0] + i * l298_pitch, l298_origin[1] + j * l298_pitch, -1]) cylinder(d = m3, h = wall + 2);
    for (h = batt_holes) translate([h[0], h[1], -1]) cylinder(d = m3, h = wall + 2);
    // differential bracket (2x M3) and sonar bracket (2x M3)
    for (dy = [-9, 9]) translate([diff_x, body_w / 2 + dy, -1]) cylinder(d = m3, h = wall + 2);
    for (dy = [-18, 18]) translate([body_l - 7, body_w / 2 + dy, -1]) cylinder(d = m3, h = wall + 2);
    // motor wire pass-throughs
    for (y = [14, body_w - 14]) translate([body_l / 2 - 20, y, -1]) cylinder(d = 10, h = wall + 2);
  }
}

// Seesaw bar across the top; its ends link down to both rockers so the body
// pitch stays at the average of the two rockers.
diff_half = body_w / 2 + 4;
module diff_bar() {
  difference() {
    union() {
      bar([-diff_half, 0], [diff_half, 0], 12);
      cylinder(r = hub_r, h = plate_t);
    }
    pivot_hole([0, 0]);
    pivot_hole([-diff_half, 0], m3);
    pivot_hole([diff_half, 0], m3);
  }
}

diff_axis_h = 20;  // pivot height above deck
module diff_bracket() {
  gap = plate_t + 1;
  cheek = 5;
  difference() {
    union() {
      translate([-(gap / 2 + cheek), -12, 0]) cube([gap + 2 * cheek, 24, 4]);
      for (s = [-1, 1]) translate([s > 0 ? gap / 2 : -gap / 2 - cheek, -8, 0]) cube([cheek, 16, diff_axis_h + 8]);
    }
    translate([-20, 0, diff_axis_h]) rotate([0, 90, 0]) cylinder(d = m4, h = 40);
    for (dy = [-9, 9]) translate([0, dy, -1]) cylinder(d = m3, h = 6);
    translate([-gap / 2, -9, 4]) cube([gap, 18, diff_axis_h + 10]);
  }
}

// HC-SR04: transducers 16 mm, ~26 mm apart.
module sonar_bracket() {
  difference() {
    union() {
      translate([-25, 0, 0]) cube([50, 14, 3]);
      translate([-25, 0, 0]) cube([50, 3, 26]);
    }
    for (dy = [-18, 18]) translate([dy, 8, -1]) cylinder(d = m3, h = 5);
    for (dx = [-13, 13]) translate([dx, -1, 15]) rotate([-90, 0, 0]) cylinder(d = 16.5, h = 5);
  }
}

// Rough side-by-side preview for checking proportions, not an exact assembly.
module assembly() {
  color("silver") translate([-body_l / 2, -body_w / 2, body_h - pivot_from_edge]) mirror([0, 0, 1]) body();
  for (s = [-1, 1]) {
    y = s * (body_w / 2 + 1);
    // rotate([90,0,0]) stands a flat part up: its +Y becomes +Z, thickness goes to -Y.
    color("orange") translate([0, y + (s > 0 ? plate_t : 0), 0]) rotate([90, 0, 0]) rocker();
    color("gold") translate([bogie_pivot[0], y + s * (plate_t + 1) + (s > 0 ? plate_t : 0), bogie_pivot[1]]) rotate([90, 0, 0]) bogie();
  }
  color("black") for (x = [front_axle[0], bogie_pivot[0] - bogie_half, bogie_pivot[0] + bogie_half], s = [-1, 1])
    translate([x, s * (body_w / 2 + 40), front_axle[1]]) rotate([90, 0, 0]) cylinder(d = wheel_d, h = 26, center = true);
}

if (part == "rocker") rocker();
else if (part == "bogie") bogie();
else if (part == "body") body();
else if (part == "diff_bar") diff_bar();
else if (part == "diff_bracket") diff_bracket();
else if (part == "sonar_bracket") sonar_bracket();
else assembly();
