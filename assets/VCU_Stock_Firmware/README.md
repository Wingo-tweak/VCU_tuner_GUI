# Exact stock VCU firmware

This directory contains the unmodified `Compat` VCU images recognized by the tuner. Their names, sizes and SHA-256 values are recorded in `manifest.json`.

Only stock VCU images are included. The 100 km/h mod, runtime readback patch and tuned outputs are intentionally excluded. The stock-based 1.5.13 readback OTA is stored separately in `assets/ota_templates`.

These files are reference/input images. The tuner never overwrites them; export always requires a new destination.
