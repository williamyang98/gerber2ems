from gerber2ems.config import Config
from gerber2ems.constants import PLOT_STYLE
import logging
import os
import matplotlib.pyplot as plt
import numpy as np
import skrf

logger = logging.getLogger(__name__)

def is_valid(array: np.ndarray):
    """Check if array doesn't have any NaN's."""
    return not np.any(np.isnan(array))

def calculate_min_max_impedance(s11_margin, z0):
    """Calculate aproximated min-max values for impedance (it assumes phase is 0)."""
    angles = [0, np.pi]
    reflection_coeffs = 10 ** (-s11_margin / 20) * (np.cos(angles) + 1j * np.sin(angles))
    impedances = z0 * (1 + reflection_coeffs) / (1 - reflection_coeffs)
    return (abs(impedances[0]), abs(impedances[1]))

def render_impedance(data, include_margins=False):
    """Render all ports impedance plots to files."""
    logger.info("Rendering impedance plots")
    plt.style.use(PLOT_STYLE)
    config = Config.get()
    for port, impedance in enumerate(data.impedances):
        if is_valid(impedance):
            fig, axs = plt.subplots(2)
            axs[0].plot(data.frequencies / 1e9, np.abs(impedance))
            axs[1].plot(
                data.frequencies / 1e9,
                np.angle(impedance, deg=True),
                linestyle="dashed",
                color="orange",
            )

            axs[0].set_ylabel("Magnitude, $|Z_{" + str(port) + r"}| [\Omega]$")
            axs[1].set_ylabel("Angle, $arg(Z_{" + str(port) + r"}) [^\circ]$")
            axs[1].set_xlabel("Frequency, f [GHz]")
            axs[0].grid(True)
            axs[1].grid(True)

            if include_margins:
                s11_margin = config.ports[port].dB_margin
                z0 = config.ports[port].impedance
                min_z, max_z = data.calculate_min_max_impedance(s11_margin, z0)

                axs[0].axhline(np.real(min_z), color="red")
                axs[0].axhline(np.real(max_z), color="red")

            fig.savefig(
                os.path.join(config.dirs.graphs_dir, f"Z_{port+1}.png"),
                bbox_inches="tight",
            )

def render_smith(data):
    """Render port reflection smithcharts to files."""
    logger.info("Rendering smith charts")
    plt.style.use(PLOT_STYLE)
    net = skrf.Network(frequency=data.frequencies / 1e9, s=data.s_params.transpose(2, 0, 1))
    config = Config.get()
    for port in range(data.count):
        if is_valid(data.s_params[port][port]):
            fig, axes = plt.subplots()
            s11_margin = config.ports[port].dB_margin
            vswr_margin = (10 ** (s11_margin / 20) + 1) / (10 ** (s11_margin / 20) - 1)
            net.plot_s_smith(
                m=port,
                n=port,
                ax=axes,
                draw_labels=False,
                show_legend=True,
                draw_vswr=[vswr_margin],
            )
            fig.savefig(
                os.path.join(config.dirs.graphs_dir, f"S_{port+1}{port+1}_smith.png"),
                bbox_inches="tight",
            )

def render_trace_delays(data):
    """Render all trace delay plots to files."""
    logger.info("Rendering trace delay plots")
    plt.style.use(PLOT_STYLE)
    config = Config.get()
    for trace in config.traces:
        if trace.correct and is_valid(data.delays[trace.stop][trace.start]):
            fig, axes = plt.subplots()
            axes.plot(
                data.frequencies / 1e9,
                data.delays[trace.stop][trace.start] * 1e9,
                label=f"{trace.name} delay",
            )
            axes.legend()
            axes.set_xlabel("Frequency, f [GHz]")
            axes.set_ylabel("Trace delay, [ns]")
            axes.grid(True)
            fig.savefig(os.path.join(config.dirs.graphs_dir, f"{trace.name}_delay.png"))

    for pair in config.diff_pairs:
        if (
            pair.correct
            and is_valid(data.delays[pair.stop_p][pair.start_n])
            and is_valid(data.delays[pair.stop_n][pair.start_p])
        ):
            fig, axes = plt.subplots()
            axes.plot(
                data.frequencies / 1e9,
                data.delays[pair.stop_p][pair.start_n] * 1e9,
                label=f"{pair.name} n delay",
            )
            axes.plot(
                data.frequencies / 1e9,
                data.delays[pair.stop_n][pair.start_p] * 1e9,
                label=f"{pair.name} p delay",
            )
            axes.legend()
            axes.set_xlabel("Frequency, f [GHz]")
            axes.set_ylabel("Trace delay, [ns]")
            axes.grid(True)
            fig.savefig(os.path.join(config.dirs.graphs_dir, f"{pair.name}_delay.png"))

def render_s_params(data):
    """Render all S parameter plots to files."""
    config = Config.get()
    logger.info("Rendering S-parameter plots")
    plt.style.use(PLOT_STYLE)
    for i in range(data.count):
        if is_valid(data.s_params[i][i]):
            fig, axes = plt.subplots()
            for j in range(data.count):
                s_param = data.s_params[j][i]
                if is_valid(s_param):
                    axes.plot(
                        data.frequencies / 1e9,
                        20 * np.log10(np.abs(s_param)),
                        label="$S_{" + f"{j+1}{i+1}" + "}$",
                    )
            axes.legend()
            axes.set_xlabel("Frequency, f [GHz]")
            axes.set_ylabel("Magnitude, [dB]")
            axes.grid(True)
            fig.savefig(os.path.join(config.dirs.graphs_dir, f"S_x{i+1}.png"))

def render_diff_pair_s_params(data):
    """Render differential pair S parameter plots to files."""
    logger.info("Rendering differential pair S-parameter plots")
    plt.style.use(PLOT_STYLE)
    config = Config.get()
    for index, pair in enumerate(config.diff_pairs):
        if (
            pair.correct
            and is_valid(data.s_params[pair.start_p][pair.start_p])
            and is_valid(data.s_params[pair.start_n][pair.start_n])
        ):
            fig, axes = plt.subplots()
            diff_params = data.differential_params[index]
            s11 = diff_params.s11
            s21 = diff_params.s21
            axes.plot(
                data.frequencies / 1e9,
                20 * np.log10(np.abs(s11)),
                label=pair.name + " $SDD_{11}$",
            )
            axes.plot(
                data.frequencies / 1e9,
                20 * np.log10(np.abs(s21)),
                label=pair.name + " $SDD_{21}$",
            )
            axes.legend()
            axes.set_xlabel("Frequency, f [GHz]")
            axes.set_ylabel("Magnitude, [dB]")
            axes.grid(True)
            fig.savefig(os.path.join(config.dirs.graphs_dir, f"SDD_{pair.name}"))

def render_diff_impedance(data):
    """Render differential pair impedance plots to files."""
    logger.info("Rendering differential pair impedance plots")
    plt.style.use(PLOT_STYLE)
    config = Config.get()
    for index, params in data.differential_params.items():
        pair = config.diff_pairs[index]
        diff_params = data.differential_params[index]
        impedance = diff_params.Z

        fig, axs = plt.subplots(2)
        axs[0].plot(data.frequencies / 1e9, np.abs(impedance))
        axs[1].plot(
            data.frequencies / 1e9,
            np.angle(impedance, deg=True),
            linestyle="dashed",
            color="orange",
        )

        axs[0].set_ylabel(f"Magnitude, {pair.name} |Z| [\Omega]$")
        axs[1].set_ylabel(f"Angle, {pair.name} arg(Z) [^\circ]$")
        axs[1].set_xlabel("Frequency, f [GHz]")
        axs[0].grid(True)
        axs[1].grid(True)

        fig.savefig(
            os.path.join(config.dirs.graphs_dir, f"Z_diff_{pair.name}.png"),
            bbox_inches="tight",
        )
