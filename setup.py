#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os

# Leggi il contenuto del file README.md
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Leggi le dipendenze dal file requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="repolizer",
    version="0.1.0",
    author="Fabrizio Salmi",
    author_email="fabrizio.salmi@gmail.com",
    description="Analizzatore di Repository GitHub",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fabriziosalmi/repolizer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "repolizer=repolizer:main",
        ],
    },
    include_package_data=True,
)