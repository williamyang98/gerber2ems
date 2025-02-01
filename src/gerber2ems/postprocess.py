"""Module contains functions usefull for postprocessing data."""
from gerber2ems.config import Config
from collections import OrderedDict
from typing import Union
import os
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class DifferentialParams:
    def __init__(self, s11, s21, Z):
        self.s11 = s11
        self.s21 = s21
        self.Z = Z

class Postprocesor:
    """Class used to postprocess and display simulation data."""

    def __init__(self, frequencies: np.ndarray, port_count: int) -> None:
        """Initialize postprocessor."""
        self.frequencies = frequencies  # Frequency list for whitch parameters are calculated
        self.count = port_count  # Number of ports

        self.incident = np.empty(
            [self.count, self.count, len(self.frequencies)], np.complex128
        )  # Incident wave phasor table ([measured_port][excited_port][frequency])
        self.incident[:] = np.nan
        self.reflected = np.empty(
            [self.count, self.count, len(self.frequencies)], np.complex128
        )  # Reflected wave phasors table ([measured_port][excited_port][frequency])
        self.reflected[:] = np.nan
        self.reference_zs = np.empty([self.count], np.complex128)
        self.reference_zs[:] = np.nan  # Reference impedances of ports

        self.s_params = np.empty(
            [self.count, self.count, len(self.frequencies)], np.complex128
        )  # S-parameter table ([output_port][input_port][frequency])
        self.s_params[:] = np.nan
        self.impedances = np.empty([self.count, len(self.frequencies)], np.complex128)
        self.impedances[:] = np.nan
        self.delays = np.empty(
            [self.count, self.count, len(self.frequencies)], np.float64
        )  # Group delay table ([output_port][input_port][frequency])
        # Table of [{start_p}{stop_p}{start_n}{stop_n}] -> DifferentialParams
        self.differential_params = {}

    def add_port_data(
        self,
        port: int,
        excited_port: int,
        incident: np.ndarray,
        reflected: np.ndarray,
    ):
        """Add port data to postprocessor.

        Data consists of incident and reflected phasor data in relation to frequency
        """
        if self.is_valid(self.incident[port][excited_port]):
            logger.warning("This port data has already been supplied, overwriting")
        self.incident[port][excited_port] = incident
        self.reflected[port][excited_port] = reflected

    def add_impedances(self, impedances: np.ndarray):
        """Add port reference impedances."""
        self.reference_zs = impedances

    def process_data(self):
        """Calculate all needed parameters for further processing. Should be called after all ports are added."""
        logger.info("Processing all data from simulation. Calculating S-parameters and impedance")
        config = Config.get()
        for i, _ in enumerate(self.incident):
            if self.is_valid(self.incident[i][i]):
                for j, _ in enumerate(self.incident):
                    if self.is_valid(self.reflected[j][i]):
                        self.s_params[j][i] = self.reflected[j][i] / self.incident[i][i]

        for i, reference_z in enumerate(self.reference_zs):
            s_param = self.s_params[i][i]
            if self.is_valid(reference_z) and self.is_valid(s_param):
                self.impedances[i] = reference_z * (1 + s_param) / (1 - s_param)

        for i in range(self.count):
            if self.is_valid(self.incident[i][i]):
                for j in range(self.count):
                    if self.is_valid(self.s_params[j][i]):
                        phase = np.unwrap(np.angle(self.s_params[j][i]))
                        group_delay = -(
                            np.convolve(phase, [1, -1], mode="valid")
                            / np.convolve(self.frequencies, [1, -1], mode="valid")
                            / 2
                            / np.pi
                        )
                        group_delay = np.append(group_delay, group_delay[-1])
                        self.delays[j][i] = group_delay

        for index, pair in enumerate(config.diff_pairs):
            if pair.correct:
                self._process_diff_pair(index, pair)

    def _process_diff_pair(self, index: int, pair):
        # differential S parameters
        sdd_11 = 0.5 * (
            self.s_params[pair.start_p][pair.start_p]
            - self.s_params[pair.start_n][pair.start_p]
            - self.s_params[pair.start_p][pair.start_n]
            + self.s_params[pair.start_n][pair.start_n]
        )
        sdd_21 = 0.5 * (
            self.s_params[pair.stop_p][pair.start_p]
            - self.s_params[pair.stop_p][pair.start_n]
            - self.s_params[pair.stop_n][pair.start_p]
            + self.s_params[pair.stop_n][pair.start_n]
        )
        # differential impedance
        s11 = self.s_params[pair.start_p][pair.start_p]
        s21 = self.s_params[pair.start_n][pair.start_p]
        s12 = self.s_params[pair.start_p][pair.start_n]
        s22 = self.s_params[pair.start_n][pair.start_n]
        gamma = ((2 * s11 - s21) * (1 - s22 - s12) + (1 - s11 - s21) * (1 + s22 - 2 * s12)) / (
            (2 - s21) * (1 - s22 - s12) + (1 - s11 - s21) * (1 + s22)
        )
        if not (
            self.reference_zs[pair.start_p]
            == self.reference_zs[pair.start_n]
            == self.reference_zs[pair.stop_p]
            == self.reference_zs[pair.stop_n]
        ):
            logger.warning(f"Differential pair {index} might have incorrect calculated impedance since ports dont have identical impedance")
        z0 = self.reference_zs[pair.start_p]
        impedance = z0 * (1 + gamma) / (1 - gamma)
        params = DifferentialParams(sdd_11, sdd_21, impedance)
        self.differential_params[index] = params

    def get_impedance(self, port: int) -> Union[np.ndarray, None]:
        """Return specified port impedance."""
        if port >= self.count:
            logger.error("Port no. %d doesn't exist", port)
            return None
        if self.is_valid(self.impedances[port]):
            logger.error("Impedance for port %d wasn't calculated", port)
            return None
        return self.impedances[port]

    def get_s_param(self, output_port, input_port):
        """Return specified S parameter."""
        if output_port >= self.count:
            logger.error("Port no. %d doesn't exist", output_port)
            return None
        if input_port >= self.count:
            logger.error("Port no. %d doesn't exist", output_port)
            return None
        s_param = self.s_params[output_port][input_port]
        if self.is_valid(s_param):
            return s_param
        logger.error("S%d%d wasn't calculated", output_port, input_port)
        return None

    def save_to_file(self) -> None:
        """Save all parameters to files."""
        for i, _ in enumerate(self.s_params):
            if self.is_valid(self.s_params[i][i]):
                self._save_port_to_file(i)
        for i in self.differential_params:
            self._save_differential_pair_to_file(i)

    def _save_port_to_file(self, port_number: int) -> None:
        """Save all parameters from single excitation."""
        s_params = self.s_params[:, port_number, :]
        delays = self.delays[:, port_number, :]
        impedances = self.impedances[port_number]

        data = []
        data.append(("Frequency (Hz)", self.frequencies))
        data.extend([(f"S{i}{port_number}", s_params[i]) for i in range(s_params.shape[0])])
        data.extend([(f"D{i}{port_number} (s)", delays[i]) for i in range(delays.shape[0])])
        data.append((f"Z{port_number} (ohms)", impedances))
        data = OrderedDict(data)
        df = pd.DataFrame(data)

        config = Config.get()
        file_name = f"port_{port_number}.csv"
        file_path = os.path.join(config.dirs.results_dir, file_name)
        logger.info("Saving port no. %d parameters to file: %s", port_number, file_path)
        df.to_csv(file_path, index=False)

    def _save_differential_pair_to_file(self, index: int) -> None:
        """Save differential pair data to file"""
        config = Config.get()
        pair = config.diff_pairs[index]
        params = self.differential_params[index]
 
        data = OrderedDict([
            ("Frequency (Hz)", self.frequencies),
            ("S11", params.s11),
            ("S21", params.s21),
            ("Zd (ohms)", params.Z),
        ])
        df = pd.DataFrame(data)
 
        file_name = f"diffpair_{index}_{pair.start_p}{pair.stop_p}{pair.start_n}{pair.stop_n}.csv"
        file_path = os.path.join(config.dirs.results_dir, file_name)
        logger.info("Saving diffpair no. %d parameters to file: %s", index, file_path)
        df.to_csv(file_path, index=False)

    @staticmethod
    def is_valid(array: np.ndarray):
        """Check if array doesn't have any NaN's."""
        return not np.any(np.isnan(array))
