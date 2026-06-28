"""Build script to compile Midgard Studio into a standalone executable using PyInstaller."""

import subprocess
import sys
from pathlib import Path


def build_executable() -> None:
    """Invoke PyInstaller command to compile the desktop studio application."""
    print(">>> Starting Midgard Studio build compilation task...")

    # Determine script entrypoint path
    project_root = Path(__file__).parent.resolve()
    entrypoint = project_root / "src" / "midgard" / "application.py"

    if not entrypoint.exists():
        print(f"Error: Entrypoint script not found at {entrypoint}")
        sys.exit(1)

    # Configure PyInstaller build options
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=MidgardStudio",
        "--onefile",
        "--windowed",
        "--clean",
        # Explicitly specify imports for packages in case they are missing
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PIL.Image",
        "--hidden-import=cv2",
        "--hidden-import=numpy",
        str(entrypoint),
    ]

    print(f">>> Running compilation command: {' '.join(command)}")
    try:
        subprocess.run(command, check=True)
        print(">>> Build compilation completed successfully!")
        print(f"Standalone executable generated in: {project_root / 'dist'}")
    except subprocess.CalledProcessError as e:
        print(f"Error: Build compilation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
