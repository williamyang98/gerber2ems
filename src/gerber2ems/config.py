"""Contains classes that describe the configuration."""
from __future__ import annotations

import sys
import os
import logging
from typing import Any, List, Optional, Union, Tuple, Dict
from enum import Enum

from gerber2ems.constants import CONFIG_FORMAT_VERSION, UNIT

logger = logging.getLogger(__name__)

class MaterialPriorityConfig:
    def __init__(self) -> None:
        self.simulation_port = 200
        self.via_filling = 101
        self.via_metal = 100

class PortConfig:
    """Class representing and parsing port config."""

    def __init__(self, config: Any) -> None:
        """Initialize PortConfig based on passed json object."""
        self.name: str = get(config, ["name"], str, "Unnamed")
        self.position: Union[Tuple[float, float], None] = None
        self.direction: Union[float, None] = None
        self.width = get(config, ["width"], (float, int))
        self.length = get(config, ["length"], (float, int), 1000)
        self.impedance = get(config, ["impedance"], (float, int), 50)
        self.layer = get(config, ["layer"], int)
        self.plane = get(config, ["plane"], int)
        self.dB_margin = get(config, ["dB_margin"], (float, int), -15)
        self.excite = get(config, ["excite"], bool, False)

class DifferentialPairConfig:
    """Class representing and parsing differential pair config."""

    def __init__(self, config: Any, port_count: int) -> None:
        """Initialize DifferentialPairConfig based on passed json object."""
        self.start_p = get(config, ["start_p"], int)
        self.stop_p = get(config, ["stop_p"], int)
        self.start_n = get(config, ["start_n"], int)
        self.stop_n = get(config, ["stop_n"], int)
        self.name = get(config, ["name"], str, f"{self.start_p}{self.stop_p}{self.start_n}{self.stop_n}")
        self.correct = True

        if self.start_p >= port_count:
            logger.warning(
                f"Differential pair {self.name} is defined to use not existing port number {self.start_p} as start_p"
            )
            self.correct = False
        if self.stop_p >= port_count:
            logger.warning(
                f"Differential pair {self.name} is defined to use not existing port number {self.stop_p} as stop_p"
            )
            self.correct = False
        if self.start_n >= port_count:
            logger.warning(
                f"Differential pair {self.name} is defined to use not existing port number {self.start_n} as start_n"
            )
            self.correct = False
        if self.stop_n >= port_count:
            logger.warning(
                f"Differential pair {self.name} is defined to use not existing port number {self.stop_n} as stop_n"
            )
            self.correct = False


class TraceConfig:
    """Class representing and parsing differential pair config."""

    def __init__(self, config: Any, port_count: int) -> None:
        """Initialize DifferentialPairConfig based on passed json object."""
        self.start = get(config, ["start"], int)
        self.stop = get(config, ["stop"], int)
        self.name = get(config, ["name"], str, f"{self.start}{self.stop}")
        self.correct = True

        if self.start >= port_count:
            logger.warning(f"Trace {self.name} is defined to use not existing port number {self.start} as start")
            self.correct = False
        if self.stop >= port_count:
            logger.warning(f"Trace {self.name} is defined to use not existing port number {self.stop} as stop")
            self.correct = False


class LayerConfig:
    """Class representing and parsing layer config."""

    def __init__(self, config: Any) -> None:
        """Initialize LayerConfig based on passed json object."""
        self.name = get(config, ["name"], str, "Unnamed")
        self.kind = self.parse_kind(get(config, ["type"], str))
        self.file = get(config, ["file"], str, "")
        if self.file == "":
            self.file = None
        self.thickness = get(config, ["thickness"], (float, int), 0)
        self.thickness = self.thickness / 1000 / UNIT
        self.thickness = int(self.thickness) # must be unit number of microns
        if self.kind == LayerKind.METAL and self.thickness % 2 != 0:
            # need thickness of metal layers to be even since we need to divide the thickness in 2 when embedding it
            logger.warning(f"Metal layer name={self.name} has thickness in microns that isn't odd, will be changed to even")
            self.thickness += 1
        self.export_field = get(config, ["export_field"], bool, False)
        self.z_mesh_count = get(config, ["z_mesh_count"], int, -1)
        if self.z_mesh_count == -1:
            self.z_mesh_count = None
        if self.kind == LayerKind.SUBSTRATE:
            self.epsilon = get(config, ["epsilon"], (float, int))
            self.priority = get(config, ["priority"], int, 50)
        elif self.kind == LayerKind.METAL:
            self.priority = get(config, ["priority"], int, 51)

        if self.kind == LayerKind.METAL and self.file == None:
            logger.error(f"Metal layer name={self.name} has no Gerber file associated with it")

    def __repr__(self):
        """Get human-readable string describing layer."""
        return f"Layer kind:{self.kind} thickness: {self.thickness}"

    @staticmethod
    def parse_kind(kind: str):
        """Parse type name to enum."""
        if kind in ["core", "prepreg"]:
            return LayerKind.SUBSTRATE
        if kind == "copper":
            return LayerKind.METAL
        raise Exception(f"Unknown layer kind: {kind}")

class LayerKind(Enum):
    """Enum describing layer type."""
    SUBSTRATE = 1
    METAL = 2

def get(
    config: Any,
    path: List[Union[str, int]],
    kind: Union[type, Tuple[type, ...]],
    default=None,
):
    """Gracefully look for value in object."""
    for name in path:
        if isinstance(config, Dict) and name in config:
            config = config[name]
        elif isinstance(name, int) and isinstance(config, List) and name < len(config):
            config = config[name]
        elif default is None:
            logger.error("No field %s found in config", path)
            sys.exit(1)
        else:
            logger.warning("No field %s found in config. Using default: %s", path, str(default))
            return default
    if isinstance(config, kind):
        return config
    if default is None:
        logger.error(
            "Field %s found in config has incorrect type %s (correct is %s)",
            path,
            type(config),
            kind,
        )
        sys.exit(1)
    else:
        logger.warning(
            "Field %s found in config has incorrect type %s (correct is %s). Using default: %s",
            path,
            type(config),
            kind,
            str(default),
        )
        return default

class NanomeshConfig:
    def __init__(self, json: Any):
        self.threshold = int(get(json, ["nanomesh", "threshold"], (int,), 127))
        self.precision = float(get(json, ["nanomesh", "precision"], (int, float), 5))
        self.max_edge_distance = float(get(json, ["nanomesh", "max_edge_distance"], (int, float), 10))
        self.minimum_angle = int(get(json, ["nanomesh", "minimum_angle"], (int,), 20))
        self.max_triangle_area = int(get(json, ["nanomesh", "max_triangle_area"], (int,), 100))

class DirectoryConfig:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.image_dir = os.path.join(output_dir, "images")
        self.geometry_dir = os.path.join(output_dir, "geometry")
        self.simulation_dir = os.path.join(output_dir, "simulation")
        self.results_dir = os.path.join(output_dir, "results")
        self.graphs_dir = os.path.join(output_dir, "graphs")

class Config:
    """Class representing and parsing config."""

    _instance: Optional[Config] = None

    @classmethod
    def get(cls) -> Config:
        """Return already instantiated config."""
        if cls._instance is not None:
            return cls._instance

        logger.error("Config hasn't been instantiated. Exiting")
        sys.exit(1)

    def __init__(self, json: Any, args: Any) -> None:
        """Initialize Config based on passed json object."""
        if self.__class__._instance is not None:
            logger.warning("Config has already beed instatiated. Use Config.get() to get the instance. Skipping")
            return

        logger.info("Parsing config")
        version = get(json, ["format_version"], str)
        if (
            version is None
            or not version.split(".")[0] == CONFIG_FORMAT_VERSION.split(".", maxsplit=1)[0]
            or version.split(".")[1] < CONFIG_FORMAT_VERSION.split(".", maxsplit=1)[1]
        ):
            logger.error(
                "Config format (%s) is not supported (supported: %s)",
                version,
                CONFIG_FORMAT_VERSION,
            )
            sys.exit()

        self.start_frequency = int(get(json, ["frequency", "start"], (float, int), 500e3))
        self.stop_frequency = int(get(json, ["frequency", "stop"], (float, int), 10e6))
        self.max_steps = int(get(json, ["max_steps"], (float, int), None))
        self.pcb_width: Union[int, None] = None
        self.pcb_height: Union[int, None] = None
        self.pcb_mesh_xy = int(get(json, ["mesh", "xy"], (float, int), 50))
        self.inter_copper_layers = int(get(json, ["mesh", "inter_layers"], int, 5))
        self.margin_xy = int(get(json, ["margin", "xy"], (float, int), 3000))
        self.margin_z = int(get(json, ["margin", "z"], (float, int), 3000))
        self.margin_mesh_xy = int(get(json, ["mesh", "margin", "xy"], (float, int), 200))
        self.margin_mesh_z = int(get(json, ["mesh", "margin", "z"], (float, int), 200))
        self.smoothing_ratio = float(get(json, ["mesh", "smoothing_ratio"], (float, int), 2))
        self.via_plating = int(get(json, ["via", "plating_thickness"], (int, float), 50))
        self.via_filling_epsilon = float(get(json, ["via", "filling_epsilon"], (int, float), 1))
        self.x_offset = float(get(json, ["offset", "x"], (int, float), 0))
        self.y_offset = float(get(json, ["offset", "y"], (int, float), 0))
        self.nanomesh = NanomeshConfig(json)

        self.arguments = args

        ports = get(json, ["ports"], list)
        self.ports: List[PortConfig] = []
        for port in ports:
            self.ports.append(PortConfig(port))
        logger.debug("Found %d ports", len(self.ports))

        diff_pairs = get(json, ["differential_pairs"], list, [])
        self.diff_pairs: List[DiffePairConfig] = []
        for diff_pair in diff_pairs:
            self.diff_pairs.append(DifferentialPairConfig(diff_pair, len(self.ports)))
        logger.debug(f"Found {len(self.diff_pairs)} differential pairs")

        traces = get(json, ["traces"], list, [])
        self.traces: List[TraceConfig] = []
        for trace in traces:
            self.traces.append(TraceConfig(trace, len(self.ports)))
        logger.debug(f"Found {len(self.traces)} traces")

        self.load_layers(get(json, ["layers"], list, []))

        self.dirs = DirectoryConfig(args.input, args.output)
        self.material_priorities = MaterialPriorityConfig()

        self.__class__._instance = self

    def load_layers(self, layers) -> None:
        layers = [LayerConfig(layer) for layer in layers]
        is_sim = lambda layer: layer.kind in (LayerKind.METAL, LayerKind.SUBSTRATE)
        layers = [layer for layer in layers if is_sim(layer)]
        # NOTE: If our metal layer has thickness we extend the height of the surrounding dielectric layers so the height of the stackup is correct
        total_layers = len(layers)
        for index in range(total_layers):
            layer = layers[index] 
            prev_layer = layers[index-1] if index > 1 else None
            next_layer = layers[index+1] if index < (total_layers-1) else None
            if layer.thickness > 0 and layer.kind == LayerKind.METAL:
                delta = layer.thickness / 2
                if prev_layer and prev_layer.kind == LayerKind.SUBSTRATE:
                    prev_layer.thickness += delta
                if next_layer and next_layer.kind == LayerKind.SUBSTRATE:
                    next_layer.thickness += delta
        self.layers = layers

    def get_substrates(self) -> List[LayerConfig]:
        """Return substrate layers configs."""
        return list(filter(lambda layer: layer.kind == LayerKind.SUBSTRATE, self.layers))

    def get_metals(self) -> List[LayerConfig]:
        """Return metals layers configs."""
        return list(filter(lambda layer: layer.kind == LayerKind.METAL, self.layers))
