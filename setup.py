from setuptools import setup
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    """Force a platform-specific wheel.

    The package bundles a prebuilt native library (copied into ``fon/`` during
    the build), so the wheel is platform-specific even though there is no
    compiled extension module. Without this, setuptools would tag the wheel
    ``py3-none-any`` and cibuildwheel would reject it as a pure-Python build.
    """

    def has_ext_modules(self) -> bool:
        return True


setup(distclass=BinaryDistribution)
