---
title: Installation
prev: /docs/
next: /docs/export_pcb
weight: 1
params:
    icon: terminal
---

## Download and installation

Following steps assume a bash shell (including git-bash).

{{% steps %}}

### Clone repository
```bash {filename="1. Clone repository"}
git clone --recursive https://github.com/williamyang98/gerber2ems.git
```
```bash {filename="2. Change directory to repository location"}
cd gerber2ems
```

### Install openEMS and gerberv
#### Windows
```bash {filename="Download binaries"}
./vendor/download.sh
```

#### Linux
1. Install [openEMS for linux](https://docs.openems.de/install.html#linux).
2. Install [gerbv for linux](https://gerbv.github.io/#download).

### Setup Python virtual environment
Only python 3.10 and 3.11 are supported by openEMS.

```bash {filename="1. Create virtual environment"}
python -m venv venv
```
```bash {filename="2. Activate virtual environment"}
source ./venv/Scripts/activate
```
```bash {filename="3. Add openEMS and gerbv binaries to path (windows only)"}
source ./vendor/update_path.sh
```

### Install gerber2ems inside environment
```bash {filename="1. Install gerber2ems"}
pip install -e .
```
```bash {filename="2. Check if gerber2ems is installed"}
gerber2ems -h
```

#### Windows
> [!WARNING]
> To fix missing DLL errors make sure to add openEMS binaries to the path.
```bash
source ./vendor/update_path.sh
```

#### Linux
Follow the openEMS installation instructions for the python interface [here](https://docs.openems.de/python/install.html#linux).


### After use shut down Python environment
```bash
deactivate
```

{{% /steps %}}

## Use after setup
{{% steps %}}

### Activating environment
```bash {filename="Change directory to repository"}
cd gerber2ems
```
```bash {filename="Activate virtual environment"}
source ./venv/Scripts/activate
```
```bash {filename="Add openEMS and gerberv binaries to path (Windows only)"}
source ./vendor/update_path.sh
```

### Running gerber2ems
```bash
gerber2ems [options]
```

### Deactivating environment
```bash
deactivate
```

{{% /steps %}}
