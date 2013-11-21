#! /usr/bin/env python3
# -*- coding: utf8 -*-

import os
import sys
from setuptools import setup

setup(
    name = "colibrimt",
    version = "0.1",
    author = "Maarten van Gompel",
    author_email = "proycon@anaproy.nl",
    description = ("Colibri MT"),
    license = "GPL",
    keywords = "machine translation moses wrapper colibri",
    url = "https://github.com/proycon/colibri-mt",
    packages=['colibrimt'],
    long_description="Colibri-MT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Text Processing :: Linguistic",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
    entry_points = {
        'console_scripts': [
            'colibri-mosesphrasetable2alignmodel = colibrimt.alignmentmodel:main_mosesphrasetable2alignmodel',
            'colibri-extractskipgrams = colibrimt.extractskipgrams:main',
            'colibri-alignmodel = colibrimt.alignmentmodel:main_alignmodel',
            'colibri-extractfeatures = colibrimt.alignmentmodel:main_extractfeatures',
        ]
    },
    package_data = {},
    install_requires=['colibricore']
)
