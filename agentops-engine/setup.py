from setuptools import setup, Extension

setup(
    name="agentops-engine",
    version="0.1.0",
    package_dir={"": "src"},
    packages=["agentops_engine"],
    setup_requires=["cffi>=1.17"],
    install_requires=[],
    cffi_modules=["src/agentops_engine/_build.py:ffibuilder"],
)
