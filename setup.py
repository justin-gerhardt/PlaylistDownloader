import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PlaylistDownloader",
    version="0.1.0",
    author="Justin Gerhardt",
    author_email="justin@gerhardt.link",
    description="Youtube playlist downloader/merger",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/justin-gerhardt/PlaylistDownloader",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "License :: Public Domain",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3"
        "Topic :: Multimedia"
    ],
    python_requires='>=3',
    install_requires=['regex'],
)