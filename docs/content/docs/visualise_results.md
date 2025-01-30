---
title: Visualise results
prev: /docs/running
next: /docs/visualise_geometry
weight: 5
params:
    icon: chart-pie
---

## Instructions

Run the simulation with post processing as shown [here]({{< abs_url link="/docs/running" >}}).

```bash {filename="Run simulation and output to default location"}
gerber2ems -a
```

- Results of post processing should be stored in ```ems/results/*.png```.
- The ```ems``` folder is controlled by the ```--output``` argument to ```gerbv``` which is [explained here]({{< abs_url link="/docs/running/#options" >}})

## Post processed results
- S parameters are calculated for all excited ports.
- Impedance of signal trace or differential pair is calculated.

### Propagation delay
{{< responsive_image key="results_A_delay" >}}

### S-parameters
{{< responsive_image key="results_S_x1" >}}
{{< responsive_image key="results_S_x3" >}}
{{< responsive_image key="results_S_11_smith" >}}
{{< responsive_image key="results_S_33_smith" >}}
{{< responsive_image key="results_SDD" >}}

### Characteristic impedance
{{< responsive_image key="results_Z_1" >}}
{{< responsive_image key="results_Z_3" >}}
{{< responsive_image key="results_Z_diff_A" >}}
