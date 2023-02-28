from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="kwhmeter",
    version_config=True,
    setup_requires=['setuptools-git-versioning'],
    author="nachomas",
    author_email="mas.ignacio@gmail.com",
    description="Clientes para lectura de contadores electricos de distribuidoras españolas",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nachoplus/kwhmeter.git",
    packages=find_packages(),
    install_requires=[
        'click==7.1.2',
        'pyyaml',
        'requests',
        'workalendar',
        'pandas'
    ],
    extras_require={

    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
