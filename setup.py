# -*- coding: utf-8 -
import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name='enoslib',
    version='0.0.1',
    description='',
    url='https://github.com/beyondtheclouds/enoslib',
    author='msimonin',
    author_email='matthieu.simonin@inria.fr',
    license='GPL-3.0',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        ],
    keywords='Evaluation, Reproducible Research, Grid5000',
    long_description=read('README.rst'),
    packages=find_packages(),
    install_requires=[
        'ansible>=2.3.0, <2.4.0'
    ],
    include_package_data=True
)
