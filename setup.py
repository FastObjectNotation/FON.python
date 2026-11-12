import glob
import os

from setuptools import setup
from setuptools.dist import Distribution

try:
    from setuptools.command.bdist_wheel import bdist_wheel
except ImportError:
    from wheel.bdist_wheel import bdist_wheel


PACKAGE_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fon")
LIBRARY_PATTERNS: tuple = ("fon_native.dll", "libfon_native.so", "libfon_native.dylib")


class BinaryDistribution(Distribution):
    """Force a platform-specific wheel.

    The package bundles a prebuilt native library (copied into ``fon/`` during
    the build), so the wheel is platform-specific even though there is no
    compiled extension module. Without this, setuptools would tag the wheel
    ``py3-none-any`` and cibuildwheel would reject it as a pure-Python build.
    """

    def has_ext_modules(self) -> bool:
        return True


class WheelWithNativeLibrary(bdist_wheel):
    """Refuse to build a wheel that would install without its native library."""

    def run(self) -> None:
        present: list = [name for name in LIBRARY_PATTERNS if glob.glob(os.path.join(PACKAGE_DIR, name))]
        if not present:
            raise SystemExit(
                "fon: no native library in fon/. Build it and copy it there before building a wheel:\n"
                "  cargo build --release --manifest-path native/Cargo.toml\n"
                "  copy native/target/release/fon_native.dll (or libfon_native.so, libfon_native.dylib) into fon/"
            )
        super().run()


setup(distclass=BinaryDistribution, cmdclass={"bdist_wheel": WheelWithNativeLibrary})
