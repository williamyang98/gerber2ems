---
title: Exporting PCB
prev: /docs/installation
next: /docs/configuration
weight: 2
params:
    icon: save-as
---

## Required files
These following files should be exported from your PCB design. This should be achievable from any PCB design software.

### Gerber files (*.gbr)
- Specified geometry for copper layers is added to simulation (*_Cu.gbr).
- Edge cuts must be supplied (Edge_Cuts.gbr).
- Must be referenced to drill/place file origin.
- Uses the ```4.6, unit mm``` coordinate format.

### Drill files (*.drl)
- Only plated through holes such as vias are added to simulation (PTH.drl).
- Must be referenced to dill/place file origin.
- Uses decimal format in millimeters.
- Excellon file format in alternate drill mode.

### Ports file (*-pos.csv)
- Only specially marked simulation ports are imported into simulation.
- Reference must be "SP{number}".
- Value must be "Simulation_Port".
- xy position:
    - Must be in millimeters.
    - Referenced to drill/place file origin.
- Only rotations of ```[0, 90, 180, 270]``` are allowed.
- File must be in ```csv``` format where first row is the header.
- Order of values is given in the following table.

| Ref | Val | Package | PosX | PosY | Rot | Side |
| --- | --- | --- | --- | --- | --- | --- |
| SP0 | Simulation_Port | * | 0.4 | 2.5 | * |
| SP1 | Simulation_Port | * | 0.6 | 2.5 | * |

## Exporting from KiCAD 8.0
{{% steps %}}

### Creating simulation ports
{{< responsive_image key="kicad_simulation_port" >}}

Check to see if a component on the board is setup correctly to be imported as a simulation port into openEMS.

1. Select a footprint.
2. Select properties.
3. Check to see if the ```Reference``` and ```Value``` are set to ```SP{number}``` and ```Simulation_Port``` respectively.
    - This should be done in the KiCAD schematic file by editing the properties on the component.
    - You can create a library of simulation port cusotm footprints in KiCAD or reuse an inbuilt footprint.
4. Change orientation if port is the orientation after being imported.
5. Make sure that it is not excluded from the exported position files.

### Begin exporting files
Use the following menu to export each of the required file types.

{{< responsive_image key="kicad_file_menu" style="width: 50%" >}}

### Export Gerber files
{{< responsive_image key="kicad_export_gerber" >}}

0. Select ```File > Fabrication Outputs > Gerbers (.gbr)...```.
1. Choose output folder.
2. Include layers that you want to export.
3. Setup options.
4. Press ```Plot``` to export gerber files to output folder.

### Export drill files

{{< responsive_image key="kicad_export_drill" >}}

0. Select ```Generate Drill Files...``` from previous ```Gerber files``` dialog box.
1. Choose output folder.
2. Setup options.
3. Press ```Generate Drill File``` to export drill files to output folder.

### Export ports file
{{< responsive_image key="kicad_export_ports" >}}

0. Select ```File > Fabrication Outputs > Component Placement (.pos, .gbr)...```.
1. Choose output folder.
2. Setup options.
3. Press ```Generate Position File``` to export ports to output folder.

{{% /steps %}}
