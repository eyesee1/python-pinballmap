from codecs import open
from os import path

# Always prefer setuptools over distutils
from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="pinballmap",
    version="0.4.2",
    description="Python client for the Pinball Map API",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/eyesee1/python-pinballmap",
    author="Duna Csandl",
    author_email="marinas.bobble-05@icloud.com",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="pinball map api",
    packages=find_packages(exclude=["contrib", "docs", "tests"]),
    entry_points={"console_scripts": ["pinballmap=pinballmap.cli:cli"]},
)
