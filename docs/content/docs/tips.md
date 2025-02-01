---
title: Tips
prev: /docs/bugs
weight: 9
params:
    icon: light-bulb
---

**Tip 1: Check copper traces are imported correctly**
- ```nanomesh``` and ```gerbv``` may delete or merge traces in the final mesh.
- Follow [visualising geometry]({{< abs_url link="/docs/visualising_geometry" >}}) to confirm all traces are intact.
- Symptoms include high impedance values in results and a high S11 parameter meaning high input reflections.
- When running geometry pass nanomesh has to convert image of layers to mesh data.
- With insufficient settings there will be deletion of traces or merging of traces.
- Modify [nanomesh configuration]({{< abs_url link="/docs/configuration/#configuring-nanomesh" >}}) to fix this.
    - Decrease ```nanomesh.precision``` to reduce mesh vertex position error.
    - Decrease ```nanomesh.minimum_angle``` to permit more aggressive triangulation.

**Tip 2: Fix simulation port and drill offsets**
- Currently there isn't automatic alignment of drill and component positions to the Gerber files.
- Symptoms include high impedance values in results and a high S11 parameter meaning high input reflections.
- Follow [visualising geometry]({{< abs_url link="/docs/visualising_geometry" >}}) to see if vias and simulation ports are placed correctly.
- To correct for undesired offsets in the simulation port location adjust the ```offset.x``` and ```offset.y``` values in the configuration file as [explained here]({{< abs_url link="/docs/configuration/#simulation-settings" >}}).

**Tip 3: Double check port assignment**
- Follow [visualising fields]({{< abs_url link="/docs/visualising_fields" >}}) to see if excited ports have been assigned correctly.
- Paraview visualisation will show if you have any ports swapped based on the excitation signal travel direction and location.
- Additionally it will also indicate any bad connections if the excitation signal does not propagation according to expectations.
- Revisit the following configuration file settings to fix this.
    - [Simulation ports]({{< abs_url link="/docs/configuration/#simulation-ports" >}})
    - [Differential pairs]({{< abs_url link="/docs/configuration/#differential-pairs" >}})
    - [Signal traces]({{< abs_url link="/docs/configuration/#signal-traces" >}})
- Make sure you are exporting simulation ports correctly.
    - [Format of port position file]({{< abs_url link="/docs/export_pcb/#ports-file--poscsv" >}})
    - [Creating simulation ports in KiCAD 8.0]({{< abs_url link="/docs/export_pcb/#creating-simulation-ports" >}})
    - [Exporting port positions in KiCAD 8.0]({{< abs_url link="/docs/export_pcb/#export-ports-file" >}})
