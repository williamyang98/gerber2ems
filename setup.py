from setuptools import setup, find_packages
import os
import pathlib

requirements = [
    "numpy",
    "matplotlib",
    "coloredlogs",
    "nanomesh",
    "Pillow",
    "scikit-rf",
    "h5py",
]

PYTHON_VERSION = sys.version_info[:2]

if os.name == 'nt':
    ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
    OPENEMS_ROOT = os.path.join(ROOT_DIR, "vendor/openems/openEMS/")
    OPENEMS_ROOT = os.path.abspath(OPENEMS_ROOT)
    OPENEMS_WHEEL_FILEPATHS = {
        (3, 10): os.path.join(OPENEMS_ROOT, "python", "openEMS-0.0.36-cp310-cp310-win_amd64.whl"),
        (3, 11): os.path.join(OPENEMS_ROOT, "python", "openEMS-0.0.36-cp311-cp311-win_amd64.whl"),
    }
    CSXCAD_WHEEL_FILEPATHS = {
        (3, 10): os.path.join(OPENEMS_ROOT, "python", "CSXCAD-0.6.3-cp310-cp310-win_amd64.whl"),
        (3, 11): os.path.join(OPENEMS_ROOT, "python", "CSXCAD-0.6.3-cp311-cp311-win_amd64.whl"),
    }

    def get_wheel(name, filepaths, version):
        filepath = filepaths.get(version, None)
        if filepath is None:
            format_version = lambda v: '.'.join(map(str, v))
            current_version = format_version(PYTHON_VERSION)
            supported_versions = [format_version(v) for v in filepaths.keys()]
            raise RuntimeError(
                f"Unsupported Python version {current_version} for wheel {name}. "
                f"Supported versions are: [{','.join(supported_versions)}]."
            )
        return filepath

    OPENEMS_WHEEL_FILEPATH = get_wheel("openEMS", OPENEMS_WHEEL_FILEPATHS, PYTHON_VERSION)
    CSXCAD_WHEEL_FILEPATH = get_wheel("CSXCAD", CSXCAD_WHEEL_FILEPATHS, PYTHON_VERSION)
    OPENEMS_WHEEL_URI = pathlib.Path(OPENEMS_WHEEL_FILEPATH).as_uri()
    CSXCAD_WHEEL_URI = pathlib.Path(CSXCAD_WHEEL_FILEPATH).as_uri()

    windows_requirements = [
        f"openEMS @ {OPENEMS_WHEEL_URI}",
        f"CSXCAD @ {CSXCAD_WHEEL_URI}",
    ]
    requirements.extend(windows_requirements)

setup(
    name="gerber2ems",
    version="0.99.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "gerber2ems": ["*.mplstyle"]
    },
    python_requires=">=3.10, <=3.11",
    entry_points={
        "console_scripts": [
            "gerber2ems = gerber2ems.main:main"
        ]
    },
    install_requires=requirements,
)
