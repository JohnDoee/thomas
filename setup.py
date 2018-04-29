#!/usr/bin/env python

from setuptools import setup, find_packages

def read_description():
    import os
    path = os.path.join(os.path.dirname(__file__), 'README.rst')
    try:
        with open(path) as f:
            return f.read()
    except:
        return 'No description found'

setup(
    name='thomas',
    version='2.1.0',
    description='Thomas allows segmented downloads and is an alternative to Axel',
    long_description=read_description(),
    author='Anders Jensen',
    author_email='johndoee+thomas@tidalstream.org',
    maintainer='Anders Jensen',
    url='https://github.com/JohnDoee/thomas',
    packages=find_packages(),
    install_requires=[
        'six',
        'twisted',
        'progressbar2',
        'rfc6266',
        'requests',
        'rarfile',
    ],
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: BSD',
        'Operating System :: POSIX :: Linux',
        'Operating System :: POSIX :: Other',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
    ],
    entry_points={ 'console_scripts': [
        'thomas = thomas.__main__:main',
    ]},
)
