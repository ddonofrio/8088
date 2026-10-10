"""Remove generated output only, after checking the resolved project boundary."""

from pathlib import Path
import shutil

project = Path(__file__).resolve().parent.parent
build = project / "build"
if build.exists():
    if build.is_symlink() or build.resolve().parent != project.resolve():
        raise ValueError("Refusing to remove a build directory outside the project")
    shutil.rmtree(build)
    print("Removed generated build output.")
