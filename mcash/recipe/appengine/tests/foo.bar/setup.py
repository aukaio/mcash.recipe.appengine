"""Package setup."""

from setuptools import setup, find_packages

version = '1.0'

setup(
    name='foo.bar',
    version=version,
    description="Foo bar package",
    long_description="",
    classifiers=[],
    keywords='',
    author='Nobody',
    author_email='nobody@nowhere',
    url='http://nowhere',
    license='',
    packages=find_packages('src'),
    include_package_data=True,
    package_dir={'':'src'},
    namespace_packages=['foo'],
    zip_safe=False,
    install_requires=['setuptools', 'bazpkg', 'tinypkg'],
    entry_points="",
)
