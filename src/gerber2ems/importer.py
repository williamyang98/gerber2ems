"""Module containing functions for importing gerbers."""
import csv
import json
import subprocess
import os
import logging
from typing import List, Tuple
import sys
import re

import PIL.Image
import numpy as np
from nanomesh import Image
from nanomesh import Mesher2D
import matplotlib.pyplot as plt
import multiprocessing

from gerber2ems.config import Config
from gerber2ems.constants import (
    UNIT,
    PIXEL_SIZE_MICRONS,
    BORDER_THICKNESS,
    STACKUP_FORMAT_VERSION,
)

logger = logging.getLogger(__name__)

def process_gbrs_to_pngs():
    """Process all gerber files to PNG's.

    Finds edge cuts gerber as well as copper gerbers in `fab` directory.
    Processes copper gerbers into PNG's using edge_cuts for framing.
    Output is saved to `ems/geometry` folder
    """
    logger.info("Processing gerber files")
    config = Config.get()
    files = os.listdir(config.dirs.input_dir)

    edge = next(filter(lambda name: "Edge_Cuts.gbr" in name, files), None)
    if edge is None:
        logger.error("No edge_cuts gerber found")
        sys.exit(1)

    layers = list(filter(lambda name: "_Cu.gbr" in name, files))
    if len(layers) == 0:
        logger.warning("No copper gerbers found")

    args = []
    for name in layers:
        output = name.split("-")[-1].split(".")[0]
        args.append([
            os.path.join(config.dirs.input_dir, name),
            os.path.join(config.dirs.input_dir, edge),
            os.path.join(config.dirs.image_dir, output),
        ])

    with multiprocessing.Pool() as pool:
        pool.starmap(gbr_to_png, args)

def gbr_to_png(gerber_filename: str, edge_filename: str, output_filename: str) -> None:
    """Generate PNG from gerber file.

    Generates PNG of a gerber using gerbv.
    Edge cuts gerber is used to crop the image correctly.
    Output DPI is based on PIXEL_SIZE_MICRONS constant.
    """
    logger.info("Generating PNG for %s", gerber_filename)
    not_cropped_name = f"{output_filename}_not_cropped.png"

    TOTAL_MILLIMETERS_IN_MIL = 0.0254
    dpi = 1 / (PIXEL_SIZE_MICRONS * UNIT / TOTAL_MILLIMETERS_IN_MIL)
    if not dpi.is_integer():
        logger.warning("DPI is not an integer number: %f", dpi)

    gerbv_command = f"gerbv {gerber_filename} {edge_filename}"
    gerbv_command += " --background=#000000 --foreground=#ffffffff --foreground=#0000ff"
    gerbv_command += f" -o {not_cropped_name}"
    gerbv_command += f" --dpi={dpi} --export=png -a"

    subprocess.call(gerbv_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

    not_cropped_image = PIL.Image.open(not_cropped_name)

    # image_width, image_height = not_cropped_image.size
    bbox = not_cropped_image.getbbox()

    # TODO: Figure out how to calculate cropped offset correctly so that
    #       config.x_offset and config.y_offset don't need to be specified manually
    # logger.warning(f"Gerber cropped: name='{gerber_filename}', specified_offset=({config.x_offset},{config.y_offset}), crop_bbox={bbox}")
    cropped_image = not_cropped_image.crop(bbox)
    cropped_image.save(f"{output_filename}.png")
    # if not Config.get().arguments.debug:
    #     os.remove(not_cropped_name)

def get_dimensions(input_filename: str) -> Tuple[int, int]:
    """Return board dimensions based on png.

    Opens PNG found in `ems/geometry` directory,
    gets it's size and subtracts border thickness to get board dimensions
    """
    config = Config.get()
    path = os.path.join(config.dirs.image_dir, input_filename)
    image = PIL.Image.open(path)
    image_width, image_height = image.size
    height = image_height * PIXEL_SIZE_MICRONS - BORDER_THICKNESS
    width = image_width * PIXEL_SIZE_MICRONS - BORDER_THICKNESS
    logger.debug("Board dimensions read from file are: height:%f width:%f", height, width)
    return (width, height)


def get_triangles(input_filename: str) -> np.ndarray:
    """Triangulate image.

    Processes file from `ems/geometry`.
    Converts to grayscale, thresholds it to remove border
    and then uses Nanomesh to create a triangular mesh of the copper.
    Returns a list of triangles, where each triangle consists of coordinates for each vertex.
    """
    config = Config.get()
    nanomesh_config = config.nanomesh
    path = os.path.join(config.dirs.image_dir, input_filename)
    image = PIL.Image.open(path)
    image_grayscale = image.convert("L")
    image_binarized = image_grayscale.point(lambda p: 255 if p < nanomesh_config.threshold else 0)
    image_data = np.array(image_binarized)
    copper = Image(image_data)

    mesher = Mesher2D(copper)
    # https://nanomesh.readthedocs.io/en/latest/api.meshing.html#nanomesh.Mesher2D.generate_contour
    PIXEL_SIZE_CM = PIXEL_SIZE_MICRONS/1e3
    PIXEL_AREA_CM2 = PIXEL_SIZE_CM**2
    mesher.generate_contour(
        level=nanomesh_config.threshold,
        max_edge_dist=int(nanomesh_config.max_edge_distance/PIXEL_SIZE_CM),
        precision=int(nanomesh_config.precision/PIXEL_SIZE_MICRONS),
        group_regions=False
    )
    mesher.plot_contour()
    # https://rufat.be/triangle/API.html#triangle.triangulate
    triangulation_options = [
        "q", nanomesh_config.minimum_angle,
        "a", (nanomesh_config.max_triangle_area/PIXEL_AREA_CM2),
    ]
    mesh = mesher.triangulate(opts="".join(map(str, triangulation_options)))

    filename = os.path.join(config.dirs.geometry_dir, input_filename.removeprefix(".png") + "_mesh.png")
    logger.debug("Saving mesh to file: %s", filename)
    mesh.plot_mpl(lw=0.1)
    plt.savefig(filename, dpi=600)

    points = mesh.get("triangle").points
    cells = mesh.get("triangle").cells
    kinds = mesh.get("triangle").cell_data["physical"]

    triangles: np.ndarray = np.empty((len(cells), 3, 2))
    for i, cell in enumerate(cells):
        triangles[i] = [
            image_to_board_coordinates(points[cell[0]]),
            image_to_board_coordinates(points[cell[1]]),
            image_to_board_coordinates(points[cell[2]]),
        ]

    # Selecting only triangles that represent copper
    # mask = kinds == 2.0
    is_region_copper = {}
    for region in mesher.contour.region_markers:
        x, y = region.point
        x, y = int(x), int(y)
        is_copper = image_data[x,y] < 127
        is_region_copper[region.label] = is_copper
    # mask = np.array([is_region_copper[x] for x in kinds])
    # NOTE: We need to do this ugly hack because physical cell data is somethings wrong????
    kind_to_region_id = {}
    unique_kinds = np.unique(kinds)
    remaining_kinds = set(kinds)
    remaining_region_ids = set(is_region_copper.keys())
    for kind in unique_kinds:
        kind = int(kind)
        if kind in is_region_copper:
            kind_to_region_id[kind] = kind
            remaining_kinds.remove(kind)
            remaining_region_ids.remove(kind)
    for kind, region_id in zip(remaining_kinds, remaining_region_ids):
        kind = int(kind)
        logger.warning(f"Applying hack to reassign dangling region kind={kind} to region_id={region_id}")
        kind_to_region_id[kind] = region_id
        logger.warning(f"Forcing hacked region to be copper")
        is_region_copper[region_id] = True

    mask = np.array([is_region_copper[kind_to_region_id[int(x)]] for x in kinds])

    logger.debug("Found %d triangles for %s", len(triangles[mask]), input_filename)

    return triangles[mask]


def image_to_board_coordinates(point: np.ndarray) -> np.ndarray:
    """Transform point coordinates from image to board coordinates."""
    return (point * PIXEL_SIZE_MICRONS) - [BORDER_THICKNESS / 2, BORDER_THICKNESS / 2]


def get_vias() -> List[List[float]]:
    """Get via information from excellon file.

    Looks for excellon file in `fab` directory. Its filename should end with `-PTH.drl`
    It then processes it to find all vias.
    """
    config = Config.get()
    files = os.listdir(config.dirs.input_dir)
    drill_filename = next(filter(lambda name: "-PTH.drl" in name, files), None)
    if drill_filename is None:
        logger.error("Couldn't find drill file")
        sys.exit(1)

    drills = {0: 0.0}  # Drills are numbered from 1. 0 is added as a "no drill" option
    current_drill = 0
    vias: List[List[float]] = []
    x_offset, y_offset = Config.get().x_offset, Config.get().y_offset
    with open(os.path.join(config.dirs.input_dir, drill_filename), "r", encoding="utf-8") as drill_file:
        for line in drill_file.readlines():
            # Regex for finding drill sizes (in mm)
            match = re.fullmatch("T([0-9]+)C([0-9]+.[0-9]+)\\n", line)
            if match is not None:
                logger.debug("Got drill size: id={0}, diameter={1} mm".format(match.group(1), match.group(2)))
                drills[int(match.group(1))] = float(match.group(2)) / 1000 / UNIT
                continue

            # Regex for finding drill switches (in mm)
            match = re.fullmatch("T([0-9]+)\\n", line)
            if match is not None:
                logger.debug("Switching to drill bit: new_id={0}, old_id={1}".format(match.group(1), current_drill))
                current_drill = int(match.group(1))
                continue

            # Regex for finding hole positions (in mm)
            match = re.fullmatch("X([\-]?[0-9]+\.[0-9]+)Y([\-]?[0-9]+\.[0-9]+)\\n", line)
            if match is not None:
                if current_drill in drills:
                    logger.debug(
                        f"Adding via at: X{float(match.group(1)) / 1000 / UNIT}Y{float(match.group(2)) / 1000 / UNIT}"
                    )
                    x_pos = float(match.group(1))
                    y_pos = float(match.group(2))
                    x_pos = x_pos - x_offset
                    y_pos = y_pos - y_offset
                    x_pos = x_pos / 1000 / UNIT
                    y_pos = y_pos / 1000 / UNIT
                    if x_pos < 0 or y_pos < 0:
                        logger.warning("Drill position is possibly outside of bounds: x={0}, y={1}".format(x_pos, y_pos))
                    vias.append(
                        [
                            x_pos, y_pos,
                            drills[current_drill],
                        ]
                    )
                else:
                    logger.warning("Drill file parsing failed. Drill with specifed number wasn't found")
                continue
    logger.debug("Found %d vias", len(vias))
    return vias

def import_port_positions() -> None:
    """Import port positions from PnP .csv files.

    Looks for all PnP files in `fab` folder (files ending with `-pos.csv`)
    Parses them to find port footprints and inserts their position information to config object.
    """
    config = Config.get()
    ports: List[Tuple[int, Tuple[float, float], float]] = []
    for filename in os.listdir(config.dirs.input_dir):
        if filename.endswith("-pos.csv"):
            ports += get_ports_from_file(os.path.join(config.dirs.input_dir, filename))

    for number, position, direction in ports:
        if len(Config.get().ports) > number:
            port = Config.get().ports[number]
            if port.position is None:
                Config.get().ports[number].position = position
                Config.get().ports[number].direction = direction
            else:
                logger.warning(
                    "Port #%i is defined twice on the board. Ignoring the second instance",
                    number,
                )
    for index, port in enumerate(Config.get().ports):
        if port.position is None:
            logger.error("Port #%i is not defined on board. It will be skipped", index)


def get_ports_from_file(filename: str) -> List[Tuple[int, Tuple[float, float], float]]:
    """Parse pnp CSV file and return all ports in format (number, (x, y), direction)."""
    ports: List[Tuple[int, Tuple[float, float], float]] = []
    with open(filename, "r", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        next(reader, None)  # skip the headers
        x_offset, y_offset = Config.get().x_offset, Config.get().y_offset
        for row in reader:
            if "Simulation_Port" in row[1]:
                number = int(row[0][2:])
                x = float(row[3])
                y = float(row[4])
                x = x - x_offset
                y = y - y_offset
                ports.append(
                    (
                        number,
                        (float(x) / 1000 / UNIT, float(y) / 1000 / UNIT),
                        float(row[5]),
                    )
                )
                logging.debug("Found port #%i position in pos file", number)

    return ports
