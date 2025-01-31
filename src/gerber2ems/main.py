#!/usr/bin/env python3

"""Main module of EM-Simulator."""
import os
import sys
import json
import argparse
import logging
from typing import Any, Optional
import shutil

import coloredlogs
import numpy as np

from gerber2ems.simulation import Simulation
from gerber2ems.postprocess import Postprocesor
from gerber2ems.config import Config
import gerber2ems.importer as importer

logger = logging.getLogger(__name__)


def main():
    """Run the script."""
    args = parse_arguments()
    setup_logging(args)

    if not any(
        [
            args.geometry,
            args.simulate,
            args.postprocess,
            args.all,
        ]
    ):
        logger.info('No steps selected. Exiting. To select steps use "-g", "-s", "-p", "-a" flags')
        sys.exit(0)

    config_json, config_filepath = open_config(args)
    config = Config(config_json, args)
    create_dir(config.dirs.output_dir)

    if args.geometry or args.all:
        logger.info("Creating geometry")
        create_dir(config.dirs.geometry_dir, cleanup=True)
        importer.process_gbrs_to_pngs()
        geometry()

    if args.simulate or args.all:
        logger.info("Running simulation")
        create_dir(config.dirs.simulation_dir, cleanup=True)
        simulate(threads=args.threads)

    if args.postprocess or args.all:
        logger.info("Postprocessing")
        create_dir(config.dirs.results_dir, cleanup=True)
        postprocess()

def add_ports(sim: Simulation, excited_port_number: Optional[int] = None) -> None:
    """Add ports for simulation."""
    logger.info("Adding ports")

    sim.ports = []
    importer.import_port_positions()

    for index, port_config in enumerate(Config.get().ports):
        sim.add_msl_port(port_config, index, index == excited_port_number)

def add_virtual_ports(sim: Simulation) -> None:
    """Add virtual ports needed for data postprocessing due to openEMS api design."""
    logger.info("Adding virtual ports")
    for port_config in Config.get().ports:
        sim.add_virtual_port(port_config)


def geometry() -> None:
    """Create a geometry for the simulation."""
    config = Config.get()
    top_layer_name = config.get_metals()[0].file
    (width, height) = importer.get_dimensions(top_layer_name + ".png")
    config.pcb_height = height
    config.pcb_width = width

    sim = Simulation()
    sim.create_materials()
    sim.add_layers()
    sim.add_mesh()
    if config.arguments.export_field:
        sim.add_dump_boxes()
    sim.set_boundary_conditions(pml=False)
    sim.add_vias()
    add_ports(sim)
    logger.info("Saving geometry file")
    sim.save_geometry()

def simulate(threads: None | int = None) -> None:
    """Run the simulation."""
    for index, port in enumerate(Config.get().ports):
        if port.excite:
            sim = Simulation()
            sim.create_materials()
            sim.set_excitation()
            logging.info("Simulating with excitation on port #%i", index)
            sim.load_geometry()
            add_ports(sim, index)
            sim.run(f"{index}", threads=threads)

def postprocess() -> None:
    """Postprocess data from the simulation."""
    sim = Simulation()
    sim.load_geometry()
    if len(sim.ports) == 0:
        add_virtual_ports(sim)

    frequencies = np.linspace(Config.get().start_frequency, Config.get().stop_frequency, 1001)
    post = Postprocesor(frequencies, len(Config.get().ports))
    impedances = np.array([p.impedance for p in Config.get().ports])
    post.add_impedances(impedances)

    for index, port in enumerate(Config.get().ports):
        if port.excite:
            reflected, incident = sim.get_port_parameters(index, frequencies)
            for i, _ in enumerate(Config.get().ports):
                post.add_port_data(i, index, incident[i], reflected[i])

    post.process_data()
    post.save_to_file()
    post.render_s_params()
    post.render_impedance()
    post.render_smith()
    post.render_diff_pair_s_params()
    post.render_diff_impedance()
    post.render_trace_delays()


def parse_arguments() -> Any:
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser(
        prog="EM-Simulator",
        description="This application allows to perform EM simulations for PCB's created with KiCAD",
    )
    parser.add_argument("-c", "--config", dest="config", type=str, default="./simulation.json")
    parser.add_argument("-i", "--input", dest="input", type=str, default="./fab")
    parser.add_argument("-o", "--output", dest="output", type=str, default="./ems")
    parser.add_argument(
        "-g",
        "--geometry",
        dest="geometry",
        action="store_true",
        help="Create geometry",
    )
    parser.add_argument(
        "-s",
        "--simulate",
        dest="simulate",
        action="store_true",
        help="Run simulation",
    )
    parser.add_argument(
        "-p",
        "--postprocess",
        dest="postprocess",
        action="store_true",
        help="Postprocess the data",
    )
    parser.add_argument(
        "-a",
        "--all",
        dest="all",
        action="store_true",
        help="Execute all steps (geometry, simulation, postprocessing)",
    )

    parser.add_argument(
        "--export-field",
        "--ef",
        dest="export_field",
        action="store_true",
        help="Export electric field data from the simulation",
    )

    parser.add_argument("-t", "--threads", dest="threads", help="Number of threads to run the simulation on")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-d", "--debug", action="store_true", dest="debug")
    group.add_argument("-l", "--log", choices=["DEBUG", "INFO", "WARNING", "ERROR"], dest="log_level")

    return parser.parse_args()


def setup_logging(args: Any) -> None:
    """Set up logging based on command line arguments."""
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    if args.log_level is not None:
        level = logging.getLevelName(args.log_level)

    if level == logging.DEBUG:
        coloredlogs.install(
            fmt="[%(asctime)s][%(name)s:%(lineno)d][%(levelname).4s] %(message)s",
            datefmt="%H:%M:%S",
            level=level,
            logger=logger,
        )
    else:
        coloredlogs.install(
            fmt="[%(asctime)s][%(levelname).4s] %(message)s",
            datefmt="%H:%M:%S",
            level=level,
            logger=logger,
        )

    # Temporary fix to disable logging from other libraries
    to_disable = ["PIL", "matplotlib"]
    for name in to_disable:
        disabled_logger = logging.getLogger(name)
        disabled_logger.setLevel(logging.ERROR)


def open_config(args: Any) -> None:
    """Try to open and parse config as json."""
    file_name = os.path.abspath(args.config)
    if not os.path.isfile(file_name):
        logger.error("Config file doesn't exist: %s", file_name)
        sys.exit(1)

    with open(file_name, "r", encoding="utf-8") as file:
        try:
            config = json.load(file)
        except json.JSONDecodeError as error:
            logger.error(f"Failed to parse config file: {file_name}")
            logger.error(
                "JSON decoding failed at %d:%d: %s",
                error.lineno,
                error.colno,
                error.msg,
            )
            sys.exit(1)

    return (config, file_name)

def create_dir(path: str, cleanup: bool = False) -> None:
    """Create a directory if doesn't exist."""
    directory_path = path
    if cleanup and os.path.exists(directory_path):
        shutil.rmtree(directory_path)
    if not os.path.exists(directory_path):
        os.mkdir(directory_path)

if __name__ == "__main__":
    main()
