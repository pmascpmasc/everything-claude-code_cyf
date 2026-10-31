// Streamlined shell styling studies on top of the Carapace structural core.
// Massing only, not printable. x forward, y left, z up, ground z = 0, mm.
//   openscad -D 'view="pod"' -o pod.png body-styling.scad
// Views: pod, manta, raptor, core (structure under every shell).
view = "pod";

$fn = 64;

pivot_z = 95;
tub_z = 70;
tub_top = 115;
wheel_d = 60;
track_y = 105;   // wheel centre line, drivetrain still open

module ellipsoid(c, r) { translate(c) scale(r) sphere(1); }

module ghost_wheels() {
  for (x = [-80, 0, 80], s = [-1, 1])
    %translate([x, s * track_y, wheel_d / 2]) rotate([90, 0, 0]) cylinder(d = wheel_d, h = 26, center = true);
}

// Structural core shared by all styles: tub, battery keel, through pivot.
module core() {
  color("dimgray") hull() for (i = [-1, 1], j = [-1, 1])
    translate([i * 86, j * 46, tub_z]) cylinder(r = 14, h = tub_top - tub_z);
  color("dimgray") hull() for (i = [-1, 1], j = [-1, 1])
    translate([i * 40, j * 19, tub_z - 14]) cylinder(r = 8, h = 16);
  color("silver") translate([0, 0, pivot_z]) rotate([90, 0, 0]) cylinder(d = 8, h = 2 * track_y - 40, center = true);
  color("silver") for (s = [-1, 1]) translate([0, s * 63, pivot_z]) rotate([90, 0, 0]) cylinder(d = 34, h = 6, center = true);
}

// Shells wrap down to the tub floor so the tub is hidden and the body reads as
// one form. Every shell must contain this footprint (tub + 4 mm clearance).
module skirt(dz = 0, inset = 0) {
  hull() for (i = [-1, 1], j = [-1, 1])
    translate([i * (90 - inset), j * (50 - inset), tub_z - 2 + dz]) cylinder(r = 20, h = 8);
}

// Axle port: the pivot shaft exits through a ringed opening in the shell.
module axle_ports() {
  for (s = [-1, 1]) translate([0, s * 70, pivot_z]) rotate([90, 0, 0]) cylinder(d = 38, h = 30, center = true);
}
module port_rings(c) {
  color(c) for (s = [-1, 1]) translate([0, s * 69, pivot_z]) rotate([90, 0, 0])
    difference() { cylinder(d = 42, h = 4, center = true); cylinder(d = 36, h = 6, center = true); }
  color("silver") for (s = [-1, 1]) translate([0, s * 63, pivot_z]) rotate([90, 0, 0]) cylinder(d = 34, h = 6, center = true);
  color("silver") translate([0, 0, pivot_z]) rotate([90, 0, 0]) cylinder(d = 8, h = 2 * track_y - 40, center = true);
}

// ---------------- Pod (水滴艙): one smooth pebble, wraparound visor ----------------
module pod_shell() {
  hull() {
    skirt();
    ellipsoid([50, 0, 108], [62, 64, 38]);
    ellipsoid([-30, 0, 112], [78, 68, 50]);
    ellipsoid([-96, 0, 96], [20, 52, 26]);
  }
}
module pod() {
  color("white") difference() { pod_shell(); axle_ports(); }
  color("red") intersection() {           // wraparound tinted visor across the nose
    scale([1.006, 1.006, 1.006]) pod_shell();
    ellipsoid([92, 0, 122], [52, 90, 15]);
  }
  color("orangered") intersection() {     // spine stripe
    scale([1.006, 1.006, 1.006]) pod_shell();
    translate([-30, 0, 200]) cube([180, 10, 160], center = true);
  }
  color("red") intersection() {           // tail light slit
    scale([1.006, 1.006, 1.006]) pod_shell();
    translate([-115, 0, 104]) cube([20, 60, 5], center = true);
  }
  port_rings("orangered");
  ghost_wheels();
}

// ---------------- Manta (魟魚): wide low wing, side crease, glass canopy ----------------
module manta_shell() {
  hull() {
    skirt();
    ellipsoid([92, 0, 86], [26, 58, 8]);       // low, thin nose
    ellipsoid([-5, 0, 98], [100, 76, 12]);     // wide wing = side crease
    ellipsoid([-20, 0, 112], [70, 50, 26]);    // body hump
    ellipsoid([-104, 0, 96], [12, 56, 16]);    // cut-off tail
  }
}
module manta() {
  color("#2b2f36") difference() { manta_shell(); axle_ports(); }
  color("#0b0d10") intersection() {            // glass canopy over the electronics
    scale([1.01, 1.01, 1.01]) manta_shell();
    ellipsoid([25, 0, 140], [60, 38, 26]);
  }
  color("deepskyblue") intersection() {        // light line tracing the crease
    scale([1.008, 1.008, 1.008]) manta_shell();
    difference() {
      ellipsoid([-5, 0, 98], [104, 80, 2]);
      ellipsoid([-5, 0, 98], [96, 72, 4]);
    }
  }
  port_rings("deepskyblue");
  ghost_wheels();
}

// ---------------- Raptor (掠食者): wedge nose, rising haunches, light bar ----------------
module raptor_shell() {
  r = 8;
  hull() {
    skirt();
    for (s = [-1, 1]) {
      translate([112, s * 42, 82]) sphere(r);           // low wedge nose
      translate([55, s * 64, 102]) sphere(r);
      translate([-70, s * 68, 116]) sphere(r);          // haunches
      translate([-108, s * 54, 110]) sphere(r);
    }
    ellipsoid([-25, 0, 136], [52, 36, 6]);               // roof
  }
}
module raptor() {
  color("gainsboro") difference() {
    raptor_shell();
    axle_ports();
    for (s = [-1, 1]) translate([30, s * 74, 102]) rotate([0, 0, s * -10]) scale([34, 12, 8]) sphere(1);  // side intakes
  }
  color("#111") for (s = [-1, 1]) translate([30, s * 66, 102]) rotate([0, 0, s * -10]) scale([30, 4, 6]) sphere(1);
  color("#111") intersection() {                // windscreen = sensor glass
    scale([1.01, 1.01, 1.01]) raptor_shell();
    translate([45, 0, 128]) rotate([0, -25, 0]) cube([60, 90, 20], center = true);
  }
  color("white") hull() for (s = [-1, 1]) translate([119, s * 40, 82]) rotate([0, 90, 0]) cylinder(d = 5, h = 2);
  color("red") hull() for (s = [-1, 1]) translate([-117, s * 50, 108]) rotate([0, 90, 0]) cylinder(d = 5, h = 2);
  port_rings("orangered");
  ghost_wheels();
}

if (view == "pod") pod();
else if (view == "manta") manta();
else if (view == "raptor") raptor();
else core();
