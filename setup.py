from setuptools import setup, find_packages

setup(
    name='mcash.recipe.appengine',
    version='0.2',
    author="mCASH Team",
    author_email="support@mca.sh",
    description="Buildout recipe for google appengine",
    entry_points={'zc.buildout': ['default = appengine:Recipe']}
)

