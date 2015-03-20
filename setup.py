from setuptools import setup

setup(
    name='mcash.recipe.appengine',
    version='0.1',
    author="mCASH Team",
    author_email="support@mca.sh",
    description="Buildout recipe for google appengine",
    entry_points={'zc.buildout': ['default = appengine:Recipe']},
    packages=['appengine']
)
