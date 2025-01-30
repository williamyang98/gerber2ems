---
title: Visualise geometry
prev: /docs/visualise_results
next: /docs/visualise_fields
weight: 6
params:
    icon: cube
---

- Geometry data can be visualised with ```AppCSXCad``` which should come pre-installed with ```openEMS```.
- This is especially useful for confirming whether or not simulation ports are placed correctly.
    - To correct for undesired offsets in the simulation port location adjust the ```offset.x``` and ```offset.y``` values in the configuration file as [explained here]({{< abs_url link="/docs/configuration/#simulation-settings" >}}).

> [!IMPORTANT]
> Make sure that you have initialised the virtual environment following [these instructions]({{< abs_url link="/docs/installation/#use-after-setup" >}}).


{{% steps %}}

### Generate your geometry file with gerber2ems.

```bash
gerber2ems --geometry
```

### Start AppCSXCad as a bash job.
```bash
AppCSXCad.exe &
```

### Open generated geometry file
Click ```File > Load``` and select ```./ems/geometry/geometry.xml``` in the dialog box.

### View geometry file
- Enable/disable visiblity on specific layers.
- Change to 2D or 3D views.
- Snap to different planes: ```[xy, xz, yz]```.
- Use ```MIDDLE_MOUSE``` to pan.
- Use ```LEFT_MOUSE``` to orbit.
- Use ```RIGHT_MOUSE``` to zoom.

{{< responsive_image key="appcxcad_usage" >}}

{{% /steps %}}
