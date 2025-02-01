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

class PortBoundingBox:
    def __init__(self, start, stop, dir) -> None:
        self.start = start # (x,y,z)
        self.stop = stop # (x,y,z)
        self.dir = dir # "x" or "y" direction

    def __repr__(self):
        return f"PortBBox(start={self.start}, end={self.stop}, dir={self.dir})"

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
        self.metal_materials: List[Any] = []
        self.dielectric_materials: List[Any] = []
        self.plane_material = self.csx.AddMetal("Plane")
        self.port_material = self.csx.AddMetal("Port")
        self.via_material = self.csx.AddMetal("Via")
        self.via_filling_material = self.csx.AddMaterial("ViaFilling", epsilon=Config.get().via_filling_epsilon)

    def create_materials(self) -> None:
        """Create materials required for simulation."""
        for i, _ in enumerate(Config.get().get_metals()):
            self.metal_materials.append(self.csx.AddMetal(f"Metal_{i}"))
        for i, layer in enumerate(Config.get().get_substrates()):
            self.dielectric_materials.append(self.csx.AddMaterial(f"Substrate_{i}", epsilon=layer.epsilon))

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
        x_lines = np.round(x_lines)
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
        y_lines = np.round(y_lines)
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
        z_lines = np.round(z_lines)
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

    def add_layers(self) -> None:
        """Add layers from config"""
        logger.info("Adding layers")
        config = Config.get()

        z_offset = 0
        metal_index = 0
        substrate_index = 0
        for index, layer in enumerate(config.layers):
            z_start = z_offset
            z_end = z_offset - layer.thickness

            if layer.kind == LayerKind.METAL:
                material = self.metal_materials[metal_index]
            else:
                material = self.dielectric_materials[substrate_index]

            layer_kind = "metal" if layer.kind == LayerKind.METAL else "dielectric"
            logger.info(
                "Added layer %d: name=%s, file=%s, kind=%s, z=%f, thickness=%f",
                index, layer.name, layer.file, layer_kind, z_start, layer.thickness
            )

            if layer.file is None:
                self._add_plane(z_start, material, layer.thickness, layer.priority)
            else:
                contours = importer.get_triangles(layer.file + ".png")
                self._add_contours(contours, z_start, material, layer.thickness, layer.priority)

            if layer.kind == LayerKind.SUBSTRATE:
                z_offset -= layer.thickness
                substrate_index += 1
            elif layer.kind == LayerKind.METAL:
                # Metal layers are embedded into dielectric so they don't affect z-height
                metal_index += 1


    def _add_plane(self, z_height: float, material, thickness: float, priority: int) -> None:
        config = Config.get()
        material.AddBox(
            [0, 0, round(z_height)],
            [
                round(config.pcb_width),
                round(config.pcb_height),
                round(z_height - thickness),
            ],
            priority=priority,
        )

    def _add_contours(self, contours: np.ndarray, z_height: float, material, thickness: float, priority: int) -> None:
        """Add contours as flat polygons on specified z-height."""
        config = Config.get()
        for contour in contours:
            points: List[List[float]] = [[], []]
            for point in contour:
                # Half of the border thickness is subtracted as image is shifted by it
                points[0].append(round(point[1]))
                points[1].append(round(config.pcb_height - point[0]))
            if thickness > 0.0:
                material.AddLinPoly(points, "z", round(z_height+thickness/2), -round(thickness), priority=priority)
            else:
                material.AddPolygon(points, "z", round(z_height), priority=priority)

    def get_metal_layer_offset(self, index: int) -> float:
        """Get z offset of nth metal layer."""
        current_metal_index = -1
        offset = 0
        config = Config.get()
        for layer in config.layers:
            if layer.kind == LayerKind.METAL:
                current_metal_index += 1
                if current_metal_index == index:
                    return offset
            elif layer.kind == LayerKind.SUBSTRATE:
                offset -= layer.thickness
        logger.error("Hadn't found %dth metal layer", index)
        sys.exit(1)

    def _get_port_bbox(self, port_config: PortConfig) -> PortBoundingBox:
        if port_config.position is None or port_config.direction is None:
            raise Exception("Port has no defined position or rotation, skipping")

        while port_config.direction < 0:
            port_config.direction += 360

        dir_map = {0: "y", 90: "x", 180: "y", 270: "x"}
        if int(port_config.direction) not in dir_map:
            raise Exception(f"Ports rotation ({port_config.direction}) is not a multiple of 90 degrees which is not supported")

        config = Config.get()
        metal_layers = config.get_metals()
        signal_layer = metal_layers[port_config.layer]
        reference_layer = metal_layers[port_config.plane]

        signal_layer_z = self.get_metal_layer_offset(port_config.layer)
        reference_layer_z = self.get_metal_layer_offset(port_config.plane)
        # FIXME: We still can't get the port to contact the metal layer if it is 3D (has thickness)
        #       This was an attempt to see if setting the port on the surface of the layer would fix this.
        #       However we still end up with open contacts which ruins low frequency data.
        # signal trace is above reference plane
        # if port_config.layer < port_config.plane:
        #     start_z = signal_layer_z - signal_layer.thickness/2
        #     stop_z = reference_layer_z + reference_layer.thickness/2
        # else:
        #     start_z = signal_layer_z + signal_layer.thickness/2
        #     stop_z = reference_layer_z - reference_layer.thickness/2
        start_z = signal_layer_z
        stop_z = reference_layer_z

        pos_x = port_config.position[0]
        pos_y = port_config.position[1]
        size_x = port_config.width
        size_y = port_config.length

        # rotate bounding box around port position
        angle = port_config.direction*math.pi/180
        rot_x = 0.5*(size_x*math.cos(angle) - size_y*math.sin(angle))
        rot_y = 0.5*(size_x*math.sin(angle) + size_y*math.cos(angle))

        bbox_start = [
            round(pos_x - rot_x),
            round(pos_y - rot_y),
            round(start_z),
        ]
        bbox_stop = [
            round(pos_x + rot_x),
            round(pos_y + rot_y),
            round(stop_z),
        ]
        bbox_dir = dir_map[int(port_config.direction)]
        return PortBoundingBox(bbox_start, bbox_stop, bbox_dir)

    def add_msl_port(self, port_config: PortConfig, port_number: int, excite: bool = False):
        """Add microstripline port based on config."""
        config = Config.get()
        port_bbox = self._get_port_bbox(port_config)
        logger.debug(f"Adding micro stripline port {port_number} at: {port_bbox}")

        port = self.fdtd.AddMSLPort(
            port_number,
            self.port_material,
            port_bbox.start,
            port_bbox.stop,
            port_bbox.dir,
            "z",
            Feed_R=port_config.impedance,
            priority=config.material_priorities.simulation_port,
            excite=1 if excite else 0,
        )
        self.ports.append(port)
        self.mesh.AddLine("x", port_bbox.start[0])
        self.mesh.AddLine("x", port_bbox.stop[0])
        self.mesh.AddLine("y", port_bbox.start[1])
        self.mesh.AddLine("y", port_bbox.stop[1])

    def add_resistive_port(self, port_config: PortConfig, excite: bool = False):
        """Add resistive port based on config."""
        config = Config.get()
        port_bbox = self._get_port_bbox(port_config)
        logger.debug(f"Adding resistive port {port_number} at: {port_bbox}")

        port = self.fdtd.AddLumpedPort(
            len(self.ports),
            port_config.impedance,
            port_bbox.start,
            port_bbox.stop,
            "z",
            excite=1 if excite else 0,
            priority=config.material_priorities.simulation_port,
        )
        self.ports.append(port)

        if port_bbox.dir == "y":
            self.mesh.AddLine("x", port_bbox.start[0])
            self.mesh.AddLine("x", port_bbox.stop[0])
            self.mesh.AddLine("y", port_bbox.start[1])
        else:
            self.mesh.AddLine("x", port_bbox.start[0])
            self.mesh.AddLine("y", port_bbox.start[1])
            self.mesh.AddLine("y", port_bbox.stop[1])

    def add_virtual_port(self, port_config: PortConfig, port_number: int) -> None:
        """Add virtual port for extracting sim data from files. Needed due to OpenEMS api desing."""
        config = Config.get()
        port_bbox = self._get_port_bbox(port_config)
        logger.debug(f"Adding virtual port {port_number} at: {port_bbox}")
        port = self.fdtd.AddMSLPort(
            port_number,
            self.port_material,
            port_bbox.start,
            port_bbox.stop,
            port_bbox.dir,
            "z",
            Feed_R=port_config.impedance,
            priority=config.material_priorities.simulation_port,
            excite=0,
        )
        self.ports.append(port)
        self.mesh.AddLine("x", port_bbox.start[0])
        self.mesh.AddLine("x", port_bbox.stop[0])
        self.mesh.AddLine("y", port_bbox.start[1])
        self.mesh.AddLine("y", port_bbox.stop[1])
        self.mesh.AddLine("z", port_bbox.start[2])
        self.mesh.AddLine("z", port_bbox.stop[2])

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
        self.via_filling_material.AddLinPoly([x_coords, y_coords], "z", -thickness, thickness, priority=config.material_priorities.via_filling)

        x_coords = []
        y_coords = []
        for i in range(VIA_POLYGON)[::-1]:
            x_coords.append(round(x_pos + np.sin(i / VIA_POLYGON * 2 * np.pi) * (diameter / 2 + config.via_plating)))
            y_coords.append(round(y_pos + np.cos(i / VIA_POLYGON * 2 * np.pi) * (diameter / 2 + config.via_plating)))
        self.via_material.AddLinPoly([x_coords, y_coords], "z", round(-thickness), round(thickness), priority=config.material_priorities.via_metal)

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
                    round(-config.margin_xy),
                    round(-config.margin_xy),
                    round(height),
                ]
                stop = [
                    round(config.pcb_width + config.margin_xy),
                    round(config.pcb_height + config.margin_xy),
                    round(height),
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
        config = Config.get()
        logger.debug(
            "Setting excitation to gaussian pulse from %f to %f",
            config.start_frequency,
            config.stop_frequency,
        )
        self.fdtd.SetGaussExcite(
            (config.start_frequency + config.stop_frequency) / 2,
            (config.stop_frequency - config.start_frequency) / 2,
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
