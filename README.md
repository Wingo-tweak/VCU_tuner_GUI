# Ninebot Max G3 VCU Calibration Tuner

**English** · [Русский](README_ru.md)

A set of tools for adjusting throttle response and electric braking on the Ninebot Max G3 without manually searching for addresses in a hex editor.

The project lets you:

- temporarily change A0–A4 on a real scooter and read them back with an Android app;
- test values and find the settings that suit you;
- place those values into the standard VCU tables so they are applied after every power-on;
- export a new raw `.bin` or a ready-to-flash OTA `.zip`, with validation before it is written.

> [!WARNING]
> The tuner currently supports only the **Ninebot Max G3 with model prefix `1CGC`, vehicle variant 0**. A value fitting into a field does not make every possible value safe. A2–A4 affect braking and speed-related paths. Make small changes and test them under controlled conditions.

For the shortest practical route, start [`run_vcu_tuner.cmd`](run_vcu_tuner.cmd). To tune on the scooter first, flash the [VCU 1.5.13 readback OTA](assets/ota_templates/VCU_readback_1.5.13.zip) and install [VCU Runtime Lab](assets/VCU_Runtime_Lab.apk). The full workflow and its limitations are explained below.

![VCU Calibration Tuner main window](assets/screenshots/vcu_tuner_main.png)

*This is the tuner after loading a recognized VCU firmware: mode-specific A0/A1 values are at the top, followed by A2–A4 and two speed fields.*

## Why change the VCU?

The throttle and brake levers do not send a ready-made “power” value straight to the motor. The VCU first processes lever position, the selected riding mode, speed, and other conditions. It then sends commands to the MCU, which controls the motor.

```text
levers and riding modes → VCU → commands over CAN → MCU → motor
```

Some VCU settings are stored in a compressed firmware area. Ninebot moved this area and changed its contents between releases, so copying a raw offset from one version to another is unsafe. The tuner recognizes a supported layout, decompresses the data, changes the selected fields, and packs it back into place.

## What are A0–A4?

| Field | What has been established |
|---|---|
| **A0** | Shapes the rise of the drive request. A larger normal value usually releases the available drive request faster. The scale is nonlinear, and the MCU changes algorithm branch near `13108`. This is neither a power limit nor a maximum-current setting. |
| **A1** | Affects the response rate of one filter in the rising drive-request path. A larger A1 makes the request follow the throttle faster. This is not a “power” setting either. |
| **A2** | Scales one manual electric-braking path. Stock 1.5.6 uses `A2=0`, which removes this component; `A2=20` restores it, as confirmed on a real scooter. A2 is not a global control for all regenerative braking. |
| **A3** | Belongs to a separate braking/regeneration limit path. Its stock values and selection conditions are known, but its exact rider-visible meaning has not been established. |
| **A4** | A signed, speed-related correction. Treat it as an experimental field: values above `127` have a signed meaning and do not simply mean “more.” |

A0/A1 primarily change **response dynamics**. A2 affects one **manual electric-braking** path. A3/A4 should still be treated as advanced or experimental. The same A-values are not guaranteed to produce the same result with a different VCU or MCU version.

### What do the two speed fields mean?

The tuner also shows **Drive speed guard/fallback** and **Sport speed fallback/default**. These are values from the standard VCU tables for `variant 0`. They are used as initial or fallback values only in particular branches of the firmware logic, and they do not necessarily match the speed limit currently saved in the scooter.

The `0…255` range describes only the storage size. Writing `100` is not a “drive at 100 km/h” command and does not remove the other limits. The active speed-limit register may retain an older value, the official app may prevent the rider from selecting anything above its own range, and the firmware still contains separate checks. Going beyond the stock speed requires both a separate update of the active speed limit and VCU firmware whose checks permit that value. The tuner changes only the displayed table defaults/fallbacks and does not claim to perform all those additional steps.

## Two ways to tune

### 1. Temporary runtime override

The VCU contains a standard mechanism that replaces A0–A4 in working RAM. Ninebot likely used it for testing and calibration. A0–A4 overrides disappear when the VCU restarts. The normal Acceleration mode setting (`reg6E`) is stored separately and may persist.

Use [VCU Runtime Lab](assets/VCU_Runtime_Lab.apk) to work with these overrides. The app never writes automatically: it first requires a fresh read, then a separate press of the write button, and finally reads the effective value again after writing.

Each parameter card shows different stages of the same value:

| Label | Meaning |
|---|---|
| **Override / Saved** | The number in the VCU runtime override slot. “Saved” does not mean saved to flash: the value is lost after a restart. |
| **valid** | Whether the runtime slot participates in parameter selection. With `valid=0`, the override is ignored even if a nonzero number remains beside it. With `valid≠0`, the VCU selects the override instead of the normal value for that field. |
| **Effective VCU** | The value currently selected by the VCU: from the standard table/profile when `valid=0`, or from the override when `valid≠0`. Compare this value before and after every write. |

For example, `Override=0, valid=0, Effective VCU=491` means that no override is active and the working value `491` came from the normal calibration. It does not mean that the VCU is using zero. After successfully writing `12644`, the app should show an active `valid` flag and `Effective VCU=12644`, unless additional selection logic or a check applies to that field.

`Effective VCU` confirms the choice made by the VCU. It does not promise a linear physical effect or prove that the MCU applies no further interpretation or limits. To clear temporary overrides, restart the VCU and verify that `valid=0`. Writing the number `0` is not the same as disabling an override: zero can itself be an active value with special behavior.

A stock VCU accepts override commands but does not safely expose these values through the same diagnostic interface. Runtime Lab therefore blocks A0–A4 access unless you explicitly confirm that compatible readback firmware is installed.

### 2. Permanent calibration

The desktop tuner changes the standard initial values inside the firmware. Once flashed, they are applied without Runtime Lab and do not need to be set again after every power-on.

The source file is never overwritten. An audit JSON is created beside the output, recording the source/output hashes and every requested change.

## Recommended workflow

1. Confirm that the scooter is a Max G3 with prefix `1CGC` and variant 0.
2. Flash the [stock-based VCU 1.5.13 readback OTA](assets/ota_templates/VCU_readback_1.5.13.zip). It was built from clean 1.5.13 Compat firmware; its only firmware change relocates the diagnostic readback base.
3. Install the [VCU Runtime Lab APK](assets/VCU_Runtime_Lab.apk), connect to the scooter, and explicitly confirm that readback firmware is installed. The app cannot verify the VCU SHA-256 by itself.
4. Read the current saved/effective values. Change one parameter at a time and record the result. Remember that A2–A4 can affect braking.
5. Restart the VCU to clear runtime overrides. Repeat the experiment to verify that the observed effect was caused by the field you changed.
6. Open the same readback ZIP in the desktop tuner, enter the values you selected into the standard fields, and export a new OTA ZIP.
7. Flash it and read the values through Runtime Lab again. This confirms that the intended numbers reached the table and that the overrides are inactive.

The bundled readback OTA and an OTA rebuilt from it by the tuner have both been flashed and checked on a real scooter; readback returned the expected parameters.

## Running the desktop tuner

Python 3 with Tkinter is required. On Windows, double-click `run_vcu_tuner.cmd` or run:

```powershell
py -3 run_vcu_tuner.py
```

On Linux or macOS:

```bash
python3 run_vcu_tuner.py
```

On first launch, the launcher silently installs `tkinterdnd2` from `requirements.txt` into the user site. Inside a virtual environment, it installs the package into that environment. If pip or the network is unavailable, the tuner still opens, but drag and drop into the window is disabled. Some Linux distributions provide Tkinter in a separate `python3-tk` system package.

You normally do not need to find an OTA template yourself. A raw input uses the bundled readback OTA container; when an OTA ZIP is loaded, that ZIP becomes the default template. You can always choose a different ZIP.

> [!IMPORTANT]
> A template supplies the OTA container. During export, its `FIRM.bin` is completely replaced by the firmware opened in the tuner. If you open stock 1.6.2, the output is 1.6.2 without the readback change. To retain readback in the final 1.5.13 image, open `VCU_readback_1.5.13.zip` itself in the tuner.

## Supported firmware

| VCU | Support level |
|---|---|
| 1.4.8, 1.5.4 | Read-only display for known exact-stock SHA-256 files. These versions keep the parameters in code constants. |
| 1.5.5, 1.5.6 | Editing of table-based A0/A1, A2–A4, and speed fields within a verified layout. |
| 1.5.8, 1.5.13, 1.5.15, 1.6.1, 1.6.2 | The same editing support, plus three Sport/Acceleration presets selected by `reg6E=1/2/3`. |

All nine exact-stock binaries are included in [assets/VCU_Stock_Firmware](assets/VCU_Stock_Firmware/). Their sizes and SHA-256 hashes are listed in the [manifest](assets/VCU_Stock_Firmware/manifest.json). That directory contains no modified, readback, or tuned images.

<details>
<summary><strong>Stock A-values for 1CGC / variant 0</strong></summary>

| VCU | Walk/Eco/Drive A0/A1 | Sport A0/A1 | A2 | A3 selector 0/1/2 | A4 | Drive fallback | Sport fallback |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1.4.8 | 327/20 | 327/20 | 40 | 0/15/18 | 16 | 25 | — |
| 1.5.4 | 491/20 | 491/20 | 0 | 0/10/14 | 16 | 25 | — |
| 1.5.5 | 491/20 | 327/50 | 0 | 0/10/14 | 16 | 25 | 32 |
| 1.5.6 | 491/20 | 327/56 | 0 | 0/10/14 | 16 | 25 | 32 |
| 1.5.8 | 491/20 | 65/38, 327/56, 983/70 | 20 | 0/10/14 | 16 | 25 | 32 |
| 1.5.13 | 491/20 | 65/38, 327/56, 983/70 | 20 | 0/10/14 | 16 | 25 | 32 |
| 1.5.15 | 491/20 | 65/38, 327/56, 983/70 | 30 | 0/10/14 | 16 | 25 | 32 |
| 1.6.1 | 491/20 | 65/38, 327/56, 983/70 | 30 | 0/10/14 | 16 | 25 | 32 |
| 1.6.2 | 491/20 | 65/38, 327/56, 983/70 | 30 | 0/10/14 | 16 | 25 | 32 |

On 1.5.8 and later, the three Sport pairs correspond to the Acceleration modes Energy saving, Standard, and Max. speed. The active Sport pair is copied from the selected preset.

The Drive/Sport fallback is not necessarily the speed currently stored in the scooter. The VCU uses these numbers only under particular conditions.

</details>

## FAQ

<details>
<summary><strong>“I wrote 100 into a speed field, but the speed did not change.”</strong></summary>

The Drive and Sport fields are standard default/fallback values, not a universal speed-unlock switch.

- The VCU may already contain a different runtime value.
- The official app or SHU may limit its own slider.
- A stock VCU still has separate checks in code. For example, changing the Sport fallback alone does not bypass the stock limit of 45.

For Drive, using the new ceiling may require a separate write to the current speed register with a suitable tool. The tuner does not claim to turn every stock firmware into a “100 km/h mod.”

</details>

<details>
<summary><strong>“Should I set A0=65535 for the sharpest throttle response?”</strong></summary>

No. The A0 scale is nonlinear. `0` and values above `32768` trigger MCU fallback behavior, while the algorithm changes branch near `13108`. The number `65535` only describes the largest value that fits in 16 bits. It is neither a recommendation nor the maximum possible physical effect.

Use the same caution with A1–A4: `0…255` describes the storage format, and A4 is interpreted as a signed byte.

</details>

<details>
<summary><strong>“Can I load a dump read from my scooter with a programmer?”</strong></summary>

A full flash dump is usually not the raw `FIRM.bin` expected by the tuner. It may include a different base address, bootloader, size, and unrelated regions. Do not cut it down by guesswork.

If the GUI recognizes the file, verifies its layout, and displays the parameters, you can use it within the stated support limits. If the file is rejected, that is not a check to bypass: first isolate the exact VCU image and establish its structure.

</details>

<details>
<summary><strong>“The tuner says that the IAR block does not fit.”</strong></summary>

A0/A1 values are stored as floating-point data inside the firmware, and different bit patterns compress differently. A new combination can occasionally exceed the available area by a few bytes.

Slightly change one or more A0/A1 values and export again. The tuner shows the same advice and will not create firmware with truncated data or data overlapping the neighboring region.

</details>

<details>
<summary><strong>“Why do equal A0/A1 values not make Eco, Drive, and Sport identical?”</strong></summary>

A0/A1 are only one part of the command chain. The VCU sends other mode, speed, and limit fields, while the MCU contains additional mode profiles and checks. Giving every mode the same A0/A1 pair does not turn every mode into Drive or Sport.

</details>

<details>
<summary><strong>“Will the same values behave identically on 1.5.13 and 1.6.2?”</strong></summary>

Not necessarily. The tuner proves that the numbers reached the intended fields in a particular firmware image. It cannot prove that the surrounding filters, limits, and logic are identical. If you tuned values on 1.5.13, treat a transfer to another version as a new hypothesis rather than a guaranteed equivalent.

</details>

## What the tuner validates

- Known stock, modified, and readback files are recognized by SHA-256.
- For changed derivatives, the tuner additionally checks the descriptor, decoded length, table boundaries, speed-table references, and the form of the relevant Thumb instructions.
- An unknown or ambiguous layout is rejected.
- The source file and an existing output file are never overwritten.
- After packing, the IAR block is decoded again and the requested values are compared with the actual result.
- If new floating-point bit patterns do not compress into the available space, export is rejected without truncating neighboring data.
- For OTA export, `firmware.md5` is updated, the ZIP is read back, and the metadata `displayName` reflects the firmware actually used as input.

<details>
<summary><strong>Dependencies and reproducible bundled assets</strong></summary>

External Python dependencies:

```bash
python -m pip install --user -r requirements.txt
```

The bundled readback OTA and stock assets can be reproduced with scripts in `tools/`. The scripts accept only exact source SHA-256 hashes.

</details>

## Repository layout

- `vcu_tuner/` — the GUI and firmware validation/repacking backend.
- `assets/VCU_Stock_Firmware/` — verified stock VCU images.
- `assets/ota_templates/` — the clean-stock VCU 1.5.13 readback OTA.
- `assets/VCU_Runtime_Lab.apk` — the Android client for runtime tuning.
- `tools/` — reproducible build scripts for bundled assets.

This is a research project. It does not remove the scooter's physical limits, bypass every check in firmware, or guarantee identical behavior on another model or firmware version.
