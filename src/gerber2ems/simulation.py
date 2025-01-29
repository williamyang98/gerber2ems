"""Module containing Simulation class used for interacting with openEMS."""
import logging
import os
import re
import sys
import math
from typing import Tuple, List, Any

import CSXCAD
import openEMS
import numpy as np

from gerber2ems.config import Config, PortConfig, LayerKind
from gerber2ems.constants import (
    UNIT,
    VIA_POLYGON,
)
import gerber2ems.importer as importer

logger = logging.getLogger(__name__)


class Simulation:
    """Class used for interacting with openEMS."""

    def __init__(self) -> None:
        """Initialize simulation object."""
        self.csx = CSXCAD.ContinuousStructure()
        self.fdtd = openEMS.openEMS(NrTS=Config.get().max_steps)
        self.fdtd.SetCSX(self.csx)
        self.mesh = self.csx.GetGrid()
        self.mesh.SetDeltaUnit(UNIT)

        self.ports: List[openEMS.ports.MSLPort] = []

        # Separate metal materials for easier switching of layers
        self.gerber_materials: List[Any] = []
        self.substrate_materials: List[Any] = []
        self.plane_material = self.csx.AddMetal("Plane")
        self.port_material = self.csx.AddMetal("Port")
        self.via_material = self.csx.AddMetal("Via")
        self.via_filling_material = self.csx.AddMaterial("ViaFilling", epsilon=Config.get().via_filling_epsilon)

    def create_materials(self) -> None:
        """Create materials required for simulation."""
        for i, _ in enumerate(Config.get().get_metals()):
            self.gerber_materials.append(self.csx.AddMetal(f"Gerber_{i}"))
        for i, layer in enumerate(Config.get().get_substrates()):
            self.substrate_materials.append(self.csx.AddMaterial(f"Substrate_{i}", epsilon=layer.epsilon))

    def add_mesh(self) -> None:
        """Add mesh to simulation."""
        config = Config.get()
        pcb_width = config.pcb_width
        pcb_height = config.pcb_height
        if pcb_width is None or pcb_height is None:
            logger.error("PCB dimensions are not set")
            sys.exit(1)
        #### X Mesh
        # Min-Max
        x_lines = np.array(
            (
                -config.margin_xy,
                pcb_width + config.margin_xy,
            )
        )
        # PCB
        mesh = config.pcb_mesh_xy
        x_lines = np.concatenate(
            (
                x_lines,
                np.arange(0 - mesh / 2, pcb_width + mesh / 2, step=mesh),
            )
        )
        self.mesh.AddLine("x", x_lines)
        # Margin
        self.mesh.SmoothMeshLines("x", config.margin_mesh_xy, ratio=config.smoothing_ratio)

        #### Y Mesh
        # Min-Max
        y_lines = np.array(
            (
                -config.margin_xy,
                pcb_height + config.margin_xy,
            )
        )
        # PCB
        mesh = config.pcb_mesh_xy
        y_lines = np.concatenate(
            [
                y_lines,
                np.arange(0 - mesh / 2, pcb_height + mesh / 2, step=mesh),
            ]
        )
        self.mesh.AddLine("y", y_lines)
        # Margin
        self.mesh.SmoothMeshLines("y", config.margin_mesh_xy, ratio=config.smoothing_ratio)

        #### Z Mesh
        # Min-0-Max

        z_lines = np.array([])
        offset = 0
        z_count = int(config.inter_copper_layers)
        make_even = lambda x: x if x % 2 == 0 else x + 1
        make_odd = lambda x: x if x % 2 != 0 else x + 1
        for layer in config.layers:
            if layer.thickness == 0:
                continue
            # Metal layer is embedded in dielectric so z-offset from previous substrate layers will lie halfway inside metal layer
            z_offset = offset if layer.kind == LayerKind.SUBSTRATE else offset + layer.thickness/2
            # Metal layers are usually not adjacent so we linearly spread z-mesh grid from start to end inclusive
            z_line_endpoint = (layer.kind == LayerKind.METAL)
            z_line_count = layer.z_mesh_count or z_count
            # If we are exporting fields make sure there is a field line in the middle of the layer
            if layer.export_field:
                if layer.kind == LayerKind.METAL:
                    z_line_count = make_odd(z_line_count)
                else:
                    z_line_count = make_even(z_line_count)
            z_lines = np.concatenate(
                (
                    z_lines,
                    np.linspace(z_offset - layer.thickness, z_offset, z_line_count, endpoint=z_line_endpoint),
                    # np.linspace(z_offset - layer.thickness, z_offset, z_line_count, endpoint=z_line_endpoint),
                )
            )
            # Metal layers are embedded into the dielectric so we don't consider their z height
            if layer.kind == LayerKind.SUBSTRATE:
                offset -= layer.thickness
        z_lines = np.concatenate([z_lines, [config.margin_z, 0, offset, offset - config.margin_z]])
        # z_lines = np.round(z_lines)

        self.mesh.AddLine("z", z_lines)
        # Margin
        self.mesh.SmoothMeshLines("z", config.margin_mesh_z, ratio=config.smoothing_ratio)

        logger.debug("Mesh x lines: %s", x_lines)
        logger.debug("Mesh y lines: %s", y_lines)
        logger.debug("Mesh z lines: %s", z_lines)

        xyz = [
            self.mesh.GetQtyLines("x"),
            self.mesh.GetQtyLines("y"),
            self.mesh.GetQtyLines("z"),
        ]
        logger.info(
            "Mesh line count, x: %d, y: %d z: %d. Total number of cells: ~%.2fM",
            xyz[0],
            xyz[1],
            xyz[2],
            xyz[0] * xyz[1] * xyz[2] / 1.0e6,
        )

    def add_gerbers(self) -> None:
        """Add metal from all gerber files."""
        logger.info("Adding copper from gerber files")

        offset = 0
        metal_index = 0
        substrate_index = 0
        for layer in Config.get().layers:
            if layer.kind == LayerKind.SUBSTRATE:
                offset -= layer.thickness
                substrate_index += 1
            elif layer.kind == LayerKind.METAL:
                logger.info("Adding contours for %s", layer.file)
                contours = importer.get_triangles(layer.file + ".png")
                material = self.gerber_materials[metal_index]
                self.add_contours(contours, offset, material, layer.thickness)
                metal_index += 1

    def add_contours(self, contours: np.ndarray, z_height: float, material, thickness: float) -> None:
        """Add contours as flat polygons on specified z-height."""
        logger.debug("Adding contours on z=%f, thickness=%f", z_height, thickness)
        for contour in contours:
            points: List[List[float]] = [[], []]
            for point in contour:
                # Half of the border thickness is subtracted as image is shifted by it
                points[0].append((point[1]))
                points[1].append(Config.get().pcb_height - point[0])
            if thickness > 0.0:
                material.AddLinPoly(points, "z", z_height+thickness/2, -thickness, priority=50)
            else:
                material.AddPolygon(points, "z", z_height, priority=50)

    def get_metal_layer_offset(self, index: int) -> float:
        """Get z offset of nth metal layer."""
        current_metal_index = -1
        offset = 0
        for layer in Config.get().layers:
            if layer.kind == LayerKind.METAL:
                current_metal_index += 1
                if current_metal_index == index:
                    return offset
            elif layer.kind == LayerKind.SUBSTRATE:
                offset -= layer.thickness
        logger.error("Hadn't found %dth metal layer", index)
        sys.exit(1)

    def add_msl_port(self, port_config: PortConfig, port_number: int, excite: bool = False):
        """Add microstripline port based on config."""
        logger.debug("Adding port number %d", len(self.ports))

        if port_config.position is None or port_config.direction is None:
            logger.error("Port has no defined position or rotation, skipping")
            return

        while port_config.direction < 0:
            port_config.direction += 360

        dir_map = {0: "y", 90: "x", 180: "y", 270: "x"}
        if int(port_config.direction) not in dir_map:
            logger.error("Ports rotation is not a multiple of 90 degrees which is not supported, skipping")
            return

        start_z = self.get_metal_layer_offset(port_config.layer)
        stop_z = self.get_metal_layer_offset(port_config.plane)

        angle = port_config.direction / 360 * 2 * math.pi

        start = [
            round(port_config.position[0] - (port_config.width / 2) * round(math.cos(angle))),
            round(port_config.position[1] - (port_config.width / 2) * round(math.sin(angle))),
            round(start_z),
        ]
        stop = [
            round(
                port_config.position[0]
                + (port_config.width / 2) * round(math.cos(angle))
                - port_config.length * round(math.sin(angle))
            ),
            round(
                port_config.position[1]
                + (port_config.width / 2) * round(math.sin(angle))
                + port_config.length * round(math.cos(angle))
            ),
            round(stop_z),
        ]
        logger.debug("Adding port at start: %s end: %s", start, stop)

        port = self.fdtd.AddMSLPort(
            port_number,
            self.port_material,
            start,
            stop,
            dir_map[int(port_config.direction)],
            "z",
            Feed_R=port_config.impedance,
            priority=100,
            excite=1 if excite else 0,
        )
        self.ports.append(port)

        self.mesh.AddLine("x", start[0])
        self.mesh.AddLine("x", stop[0])
        self.mesh.AddLine("y", start[1])
        self.mesh.AddLine("y", stop[1])

    def add_resistive_port(self, port_config: PortConfig, excite: bool = False):
        """Add resistive port based on config."""
        logger.debug("Adding port number %d", len(self.ports))

        if port_config.position is None or port_config.direction is None:
            logger.error("Port has no defined position or rotation, skipping")
            return

        dir_map = {0: "y", 90: "x", 180: "y", 270: "x"}
        if int(port_config.direction) not in dir_map:
            logger.error("Ports rotation is not a multiple of 90 degrees which is not supported, skipping")
            return

        start_z = self.get_metal_layer_offset(port_config.layer)
        stop_z = self.get_metal_layer_offset(port_config.plane)

        angle = port_config.direction / 360 * 2 * math.pi

        start = [
            round(port_config.position[0] - (port_config.width / 2) * round(math.cos(angle))),
            round(port_config.position[1] - (port_config.width / 2) * round(math.sin(angle))),
            round(start_z),
        ]
        stop = [
            round(port_config.position[0] + (port_config.width / 2) * round(math.cos(angle))),
            round(port_config.position[1] - (port_config.width / 2) * round(math.sin(angle))),
            round(stop_z),
        ]
        logger.debug("Adding resistive port at start: %s end: %s", start, stop)

        port = self.fdtd.AddLumpedPort(
            len(self.ports),
            port_config.impedance,
            start,
            stop,
            "z",
            excite=1 if excite else 0,
            priority=100,
        )
        self.ports.append(port)

        logger.debug("Port direction: %s", dir_map[int(port_config.direction)])
        if dir_map[int(port_config.direction)] == "y":
            self.mesh.AddLine("x", start[0])
            self.mesh.AddLine("x", stop[0])
            self.mesh.AddLine("y", start[1])
        else:
            self.mesh.AddLine("x", start[0])
            self.mesh.AddLine("y", start[1])
            self.mesh.AddLine("y", stop[1])

    def add_virtual_port(self, port_config: PortConfig) -> None:
        """Add virtual port for extracting sim data from files. Needed due to OpenEMS api desing."""
        logger.debug("Adding virtual port number %d", len(self.ports))
        for i in range(11):
            self.mesh.AddLine("x", i)
            self.mesh.AddLine("y", i)
        self.mesh.AddLine("z", 0)
        self.mesh.AddLine("z", 10)
        port = self.fdtd.AddMSLPort(
            len(self.ports),
            self.port_material,
            [0, 0, 0],
            [10, 10, 10],
            "x",
            "z",
            Feed_R=port_config.impedance,
            priority=100,
            excite=0,
        )
        self.ports.append(port)

    def add_plane(self, z_height):
        """Add metal plane in whole bounding box of the PCB."""
        self.plane_material.AddBox(
            [0, 0, z_height],
            [Config.get().pcb_width, Config.get().pcb_height, z_height],
            priority=1,
        )

    def add_substrates(self):
        """Add substrate in whole bounding box of the PCB."""
        logger.info("Adding substrates")

        offset = 0
        for i, layer in enumerate(Config.get().get_substrates()):
            if not layer.file is None:
                logger.debug("Create layer from gerber file %s", layer.file)
                contours = importer.get_triangles(layer.file + ".png")
                material = self.substrate_materials[i]
                # self.add_contours(contours, offset, material)
                z_start = offset
                z_end = offset - layer.thickness
                priority_offset = 0
                if not layer.priority_offset is None:
                    logger.debug(f"Layer has priority offset {layer.priority_offset}")
                    priority_offset = layer.priority_offset
                for contour in contours:
                    points: List[List[float]] = [[], []]
                    for point in contour:
                        # Half of the border thickness is subtracted as image is shifted by it
                        points[0].append((point[1]))
                        points[1].append(Config.get().pcb_height - point[0])
                    material.AddLinPoly(points, "z", z_start, -layer.thickness, priority=-i + priority_offset)
                    for z_offset in layer.duplicate_z:
                        material.AddLinPoly(points, "z", z_start - z_offset, -layer.thickness, priority=-i + priority_offset)
                logger.debug("Added substrate as linpoly from z=[%f,%f] um, thickness=%f um", z_start, z_end, layer.thickness)
                logger.debug(f"Substrate duplicate z offsets: {layer.duplicate_z} um")
            else:
                self.substrate_materials[i].AddBox(
                    [0, 0, offset],
                    [
                        Config.get().pcb_width,
                        Config.get().pcb_height,
                        offset - layer.thickness,
                    ],
                    priority=-i,
                )
                logger.debug("Added substrate as box from %f to %f", offset, offset - layer.thickness)
            offset -= layer.thickness

    def add_vias(self):
        """Add all vias from excellon file."""
        logger.info("Adding vias from excellon file")
        vias = importer.get_vias()
        for via in vias:
            self.add_via(via[0], via[1], via[2])

    def add_via(self, x_pos, y_pos, diameter):
        """Add via at specified position with specified diameter."""
        config = Config.get()
        thickness = sum(layer.thickness for layer in config.get_substrates())

        x_coords = []
        y_coords = []
        for i in range(VIA_POLYGON):
            x_coords.append(x_pos + np.sin(i / VIA_POLYGON * 2 * np.pi) * diameter / 2)
            y_coords.append(y_pos + np.cos(i / VIA_POLYGON * 2 * np.pi) * diameter / 2)
        self.via_filling_material.AddLinPoly([x_coords, y_coords], "z", -thickness, thickness, priority=101)

        x_coords = []
        y_coords = []
        for i in range(VIA_POLYGON)[::-1]:
            x_coords.append(x_pos + np.sin(i / VIA_POLYGON * 2 * np.pi) * (diameter / 2 + config.via_plating))
            y_coords.append(y_pos + np.cos(i / VIA_POLYGON * 2 * np.pi) * (diameter / 2 + config.via_plating))
        self.via_material.AddLinPoly([x_coords, y_coords], "z", -thickness, thickness, priority=100)

    def add_dump_boxes(self):
        """Add electric field measurement plane in the middle of each metal and substrate layer"""
        offset = 0
        config = Config.get()
        for i, layer in enumerate(config.layers):
            if layer.export_field:
                height = offset - layer.thickness/2
                layer_kind = "metal" if layer.kind == LayerKind.METAL else "substrate"
                logger.info("Adding dump box at i=%d, name=%s, z=%f, thickness=%s, kind=%s", i, layer.name, height, layer.thickness, layer_kind)
                dump = self.csx.AddDump(f"e_field_{i}", sub_sampling=[1, 1, 1])
                start = [
                    -config.margin_xy,
                    -config.margin_xy,
                    height,
                ]
                stop = [
                    config.pcb_width + config.margin_xy,
                    config.pcb_height + config.margin_xy,
                    height,
                ]
                dump.AddBox(start, stop)
            # Metal layers are embedded in dielectric
            if layer.kind == LayerKind.SUBSTRATE:
                offset -= layer.thickness

    def set_boundary_conditions(self, pml=False):
        """Add boundary conditions. MUR for fast simulation, PML for more accurate."""
        if pml:
            logger.info("Adding perfectly matched layer boundary condition")
            self.fdtd.SetBoundaryCond(["PML_8", "PML_8", "PML_8", "PML_8", "PML_8", "PML_8"])
        else:
            logger.info("Adding MUR boundary condition")
            self.fdtd.SetBoundaryCond(["MUR", "MUR", "MUR", "MUR", "MUR", "MUR"])

    def set_excitation(self):
        """Set gauss excitation according to config."""
        logger.debug(
            "Setting excitation to gaussian pulse from %f to %f",
            Config.get().start_frequency,
            Config.get().stop_frequency,
        )
        self.fdtd.SetGaussExcite(
            (Config.get().start_frequency + Config.get().stop_frequency) / 2,
            (Config.get().stop_frequency - Config.get().start_frequency) / 2,
        )

    def set_sinus_excitation(self, freq):
        """Set sinus excitation at specified frequency."""
        logger.debug("Setting excitation to sine at %f", freq)
        self.fdtd.SetSinusExcite(freq)

    def set_step_excitation(self, freq):
        logger.debug("Setting excitation to step at %f", freq)
        self.fdtd.SetStepExcite(freq)

    def run(self, name, threads: None | int = None):
        """Execute simulation."""
        logger.info("Starting simulation")
        cwd = os.getcwd()
        config = Config.get()
        path = os.path.join(config.dirs.simulation_dir, str(name))
        abs_path = os.path.abspath(path)
        logger.info(f"Running FTDT simulation: threads={threads}, path='{abs_path}'")
        if threads is None:
            self.fdtd.Run(abs_path)
        else:
            self.fdtd.Run(abs_path, numThreads=threads)

        os.chdir(cwd)

    def save_geometry(self) -> None:
        """Save geometry to file."""
        config = Config.get()
        filename = os.path.join(config.dirs.geometry_dir, "geometry.xml")
        logger.info("Saving geometry to %s", filename)
        self.csx.Write2XML(filename)

        # Replacing , with . for numerals in the file
        # (openEMS bug mitigation for locale that uses , as decimal separator)
        with open(filename, "r") as f:
            content = f.read()
        new_content = re.sub(r"([0-9]+),([0-9]+e)", r"\g<1>.\g<2>", content)
        with open(filename, "w") as f:
            f.write(new_content)

    def load_geometry(self) -> None:
        """Load geometry from file."""
        config = Config.get()
        filename = os.path.join(config.dirs.geometry_dir, "geometry.xml")
        logger.info("Loading geometry from %s", filename)
        if not os.path.exists(filename):
            logger.error("Geometry file does not exist. Did you run geometry step?")
            sys.exit(1)
        self.csx.ReadFromXML(filename)

    def get_port_parameters(self, index: int, frequencies) -> Tuple[List, List]:
        """Return reflected and incident power vs frequency for each port."""
        config = Config.get()
        result_path = os.path.join(config.dirs.simulation_dir, f"{index}")

        incident: List[np.ndarray] = []
        reflected: List[np.ndarray] = []
        for index, port in enumerate(self.ports):
            try:
                logger.debug("Calculating port parameters %d (%s)", index, result_path)
                port.CalcPort(result_path, frequencies)
                logger.debug("Found data for port %d", index)
            except IOError:
                logger.error("Port data files do not exist. Did you run simulation step?")
                sys.exit(1)
            incident.append(port.uf_inc)
            reflected.append(port.uf_ref)

        return (reflected, incident)
