// Body (chassis) concept massing models — design phase only, not printable parts.
// Coordinates: x forward, y left, z up, ground at z = 0. Units: mm.
//   openscad -D 'view="A"' -o a.png body-concepts.scad
// Views: A, B, C (concept overviews), A_exploded, A_layout (top view of internals).
view = "A";

$fn = 48;

// Shared envelope / hardpoint assumptions (drivetrain still open).
pivot = [0, 0, 95];   // transverse suspension pivot axis (along y)
body_l = 200;
body_w = 120;
wheel_d = 60;

// Ghost wheels: placeholders for proportion only.
module ghost_wheels() {
  for (x = [-80, 0, 80], s = [-1, 1])
    %translate([x, s * (body_w / 2 + 45), wheel_d / 2]) rotate([90, 0, 0]) cylinder(d = wheel_d, h = 25, center = true);
}

module pivot_rod(len = body_w + 50) {
  color("dimgray") translate(pivot) rotate([90, 0, 0]) cylinder(d = 8, h = len, center = true);
}

module rbox(size, r = 8) {
  // Box with rounded vertical edges, origin at bottom centre.
  hull() for (i = [-1, 1], j = [-1, 1])
    translate([i * (size[0] / 2 - r), j * (size[1] / 2 - r), 0]) cylinder(r = r, h = size[2]);
}

// ---------------- Concept A: Carapace (甲殼) ----------------
tub_z = 70;
tub_h = 45;
module a_tub(hollow = false) {
  color("slategray") difference() {
    union() {
      translate([0, 0, tub_z]) rbox([body_l, body_w, tub_h], 14);
      // battery keel below the pivot keeps the centre of mass under the axis
      translate([0, 0, tub_z - 14]) rbox([96, 54, 16], 8);
      // bearing bosses for 608 bearings, coaxial on both side walls
      for (s = [-1, 1]) translate([pivot[0], s * (body_w / 2 + 3), pivot[2]]) rotate([90, 0, 0]) cylinder(d = 34, h = 6, center = true);
    }
    if (hollow) {
      translate([0, 0, tub_z + 3]) rbox([body_l - 6, body_w - 6, tub_h], 11);
      translate([0, 0, tub_z - 11]) rbox([90, 48, 20], 5);
    }
    for (s = [-1, 1]) translate([pivot[0], s * (body_w / 2), pivot[2]]) rotate([90, 0, 0]) cylinder(d = 22, h = 20, center = true);
  }
}

module a_shell() {
  // Faceted lid: frustum from tub outline to a narrower roof, plus a "head".
  color("darkorange") difference() {
    hull() {
      translate([0, 0, tub_z + tub_h]) rbox([body_l, body_w, 1], 14);
      translate([-10, 0, tub_z + tub_h + 32]) rbox([140, 80, 1], 10);
    }
    // slot for the differential pivot post
    translate([0, 0, tub_z + tub_h + 20]) cube([14, 30, 40], center = true);
  }
}

module a_head() {
  // Sensor head: HC-SR04 "eyes" tilted 5 degrees up, sits on the front facet.
  translate([body_l / 2 - 18, 0, tub_z + tub_h + 6]) rotate([0, -5, 0]) {
    color("whitesmoke") translate([-12, -30, 0]) cube([24, 60, 30]);
    color("black") for (s = [-1, 1]) translate([12, s * 13, 15]) rotate([0, 90, 0]) cylinder(d = 16, h = 6);
  }
}

module a_tray() {
  color("seagreen") translate([0, 0, pivot[2] + 6]) rbox([body_l - 14, body_w - 14, 3], 9);
}

module a_diff_post() {
  color("gold") translate([0, 0, tub_z + tub_h - 2]) cylinder(d = 12, h = 46);
}

module concept_a() {
  a_tub();
  a_shell();
  a_head();
  a_diff_post();
  pivot_rod();
  ghost_wheels();
}

module concept_a_exploded() {
  a_tub(true);
  translate([0, 0, 40]) a_tray();
  translate([0, 0, 110]) { a_shell(); a_head(); }
  a_diff_post();
  pivot_rod();
  // battery sled sliding out of the rear of the keel
  color("royalblue") translate([-150, 0, tub_z - 10]) rbox([80, 42, 22], 4);
}

// Top view of the internal layout (tub floor and tray), labelled.
module label(t, p, sz = 6) {
  color("black") translate([p[0], p[1], 200]) text(t, size = sz, halign = "center", valign = "center");
}
module concept_a_layout() {
  color("slategray") difference() {
    rbox([body_l, body_w, 2], 14);
    translate([0, 0, -1]) rbox([body_l - 6, body_w - 6, 4], 11);
  }
  color("royalblue", 0.8) translate([0, 0, 5]) rbox([78, 41, 2], 2);
  label("2x18650 keel (below)", [0, 0]);
  color("dimgray") translate([0, 0, 10]) cube([8, body_w + 20, 2], center = true);
  label("pivot axis", [0, body_w / 2 + 16], 5);
  color("teal") translate([-58, -2, 20]) cube([69, 53, 2], center = true);
  label("Arduino Uno", [-58, -2]);
  color("firebrick") translate([42, -30, 20]) cube([43, 43, 2], center = true);
  label("motor driver", [42, -30], 5);
  color("mediumpurple") translate([42, 28, 20]) cube([37, 15, 2], center = true);
  label("HM-10", [42, 28], 5);
  color("whitesmoke") translate([body_l / 2 - 12, 0, 20]) cube([20, 46, 2], center = true);
  label("sonar", [body_l / 2 - 30, 0], 5);
  color("orange") for (s = [-1, 1]) translate([14, s * (body_w / 2 - 12), 20]) cylinder(d = 10, h = 2);
  label("wire exits at axis", [14, -body_w / 2 - 10], 5);
  color("gold") translate([0, 0, 20]) cylinder(d = 12, h = 2);
}

// ---------------- Concept B: Spine (脊椎) ----------------
module concept_b() {
  color("slategray") translate([0, 0, pivot[2] - 20]) rbox([body_l + 20, 40, 40], 6);    // box beam
  color("dimgray") for (z = [pivot[2] + 30, pivot[2] + 60]) for (i = [-1, 1], j = [-1, 1])
    translate([i * 60, j * 38, pivot[2] + 20]) cylinder(d = 5, h = z - pivot[2] - 20);
  color("seagreen") translate([0, 0, pivot[2] + 30]) rbox([150, 96, 3], 6);
  color("seagreen") translate([0, 0, pivot[2] + 60]) rbox([150, 96, 3], 6);
  color("royalblue") translate([0, 0, pivot[2] - 44]) rbox([80, 42, 22], 4);          // slung battery
  color("whitesmoke") translate([body_l / 2 + 10, 0, pivot[2] - 10]) cube([10, 50, 22], center = true);
  pivot_rod();
  ghost_wheels();
}

// ---------------- Concept C: Cassette (卡匣) ----------------
module frame_bar(a, b, d = 10) {
  hull() { translate(a) sphere(d = d); translate(b) sphere(d = d); }
}
module concept_c() {
  z0 = 72;
  z1 = 130;
  hx = body_l / 2;
  hy = body_w / 2;
  color("slategray") {
    for (z = [z0, z1]) for (p = [[[-hx, -hy], [hx, -hy]], [[-hx, hy], [hx, hy]], [[hx, -hy], [hx, hy]]])
      frame_bar([p[0][0], p[0][1], z], [p[1][0], p[1][1], z]);
    for (x = [-hx, 0, hx], y = [-hy, hy]) frame_bar([x, y, z0], [x, y, z1]);
  }
  // electronics cassette sliding out of the open rear
  color("darkorange") translate([-60, 0, z0 + 8]) rbox([170, body_w - 24, 44], 6);
  color("royalblue") translate([0, 0, z0 - 26]) rbox([80, 42, 22], 4);
  pivot_rod();
  ghost_wheels();
}

if (view == "A") concept_a();
else if (view == "A_exploded") concept_a_exploded();
else if (view == "A_layout") concept_a_layout();
else if (view == "B") concept_b();
else if (view == "C") concept_c();
