---
title: Bugs
prev: /docs/visualise_fields
next: /docs/tips
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
- To avoid this you have to make each timestep more expensive to run.
- Modify the [PCB mesh properties]({{< abs_url link="/docs/configuration/#pcb-mesh-properties" >}}) to fix this
    - Decrease ```mesh.xy``` to increase the grid resolution along x and y axes.
    - Increase ```mesh.inter_layers``` to increase grid resolution along z axis.
    - Decrease ```mesh.smoothing_ratio``` to increase number of grid lines overall.
- Modify the [simulation settings]({{< abs_url link="/docs/configuration/#simulation-settings" >}}) to fix this
    - Increase ```margin.xy``` and ```margin.z``` to increase size of the air gap to simulate around the PCB.

**Bug 3: openEMS will randomly crash**
- When running openEMS simulation through there is a small chance of crashing with a segmentation error.
- Rerunning until it stops crashing is the only know work around.
- Use the retry script at ```./scripts/retry.sh``` to repeat a command until a successful pass is done.
- Break down simulation into multiple steps along with the retry script to automate around openEMS crashes.

```bash {filename="Simulate differential pair with retry on error"}
# Create convenient alias in bash shell
alias retry=$(realpath ./scripts/retry.sh)

# Go to differential pair example
cd ./examples/differential

# Convert Gerber to image conversion step (does not crash)
gerber2ems --convert

# Create openEMS geometry files (does not crash)
gerber2ems --geometry

# Run openEMS simulation (this can crash)
retry gerber2ems --simulate

# Postprocess data (this can crash since we use openEMS api to parse simulation results)
retry gerber2ems --postprocess

# Render data (this can crash since we use openEMS api to parse simulation results)
retry gerber2ems --render

```
