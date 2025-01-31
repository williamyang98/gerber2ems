---
title: Bugs
prev: /docs/visualise_fields
weight: 8
params:
    icon: exclamation
---

**Bug 1: Metal layers with thickness do not make contact with ports**
- There will be no contact between a micro stripline port with a metal layer that has ```layers.thickness``` set to a non-zero value.
- Only way to guarantee contact is to use a 0 thickness metal layer.
- Symptoms include the S parameters and impedance showing an open circuit at low frequencies (< 1GHz).

**Bug 2: openEMS produces corrupt data if the simulation timestep is too fast**
- Symptoms include postprocessing of data failing due to corrupted port data.
- Can be visually seen by going to ```ems/simulation/{excited_port}/port_it_{port}```.
- Numbers will be mangled and there will be missing rows and columns.

**Bug 3: openEMS will randomly segfault during startup**
- When running simulation through ```gerber2ems -s``` there is a small chance of crashing.
- Running simulation pass again usually fixes this.

**Bug 4: nanomesh will sometimes merge or remove traces**
- When running geometry pass nanomesh has to convert image of layers to mesh data.
- With insufficient settings there will be deletion of traces or merging of traces.
- Modify [nanomesh configuration]({{< abs_url link="/docs/configuration/#configuring-nanomesh" >}}) to fix this
    - Increasing ```nanomesh.quality```.
    - Decreasing ```nanomesh.min_spacing```.
