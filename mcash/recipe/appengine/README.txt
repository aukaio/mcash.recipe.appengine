A brief documentation
=====================

This recipe takes a number of options:

appengine-lib
    Path to an already installed appengine library

appserver-script-name
    The name of the script in GAE to run the dev. server.
    The default is 'dev_appserver.py'. Because there have been
    intermediate versions of the GAE SDK using 'dev_appserver2.py',
    this script name is configurable.

appserver-run-file
    The name of the run function in the "appserver-script-name" script.
    This name changed in GAE SDK > 1.7.5. Default is "_run_file".
    In previous GAE versions it was "run_file". This switch enables
    the use of this recipe for older GAE versions.

eggs
    List of required eggs

entry-points
    A list of entry-point identifiers. See zc.recipe.egg for a more detailed
    documentation.

exclude
    A list of basenames and regular expressions to be excluded when setting up
    the application files, e.g. the whole 'tests' directory.

extra-paths
    Extra paths to include in a generated script.

initialization
    Specify some Python initialization code. This is very limited. In
    particular, be aware that leading whitespace is stripped from the code
    given.

packages
    A list of packages to be included into the zip archive, which will be
    uploaded to the appspot.

patch
    Specifies a patch file for patching the SDK source-tree. This option is
    not allowed if appengine-lib is specified.

patch-options
    List of patch options separated by blanks. (Default=-p1)

server-script
    The name of the script to run the development server.

src
    The directory which contains the project source files.

symlink-gae-runtime
    When this flag is True, a symlink to the "_python_runtime.py"
    script is created in the buildout 'bin' directory. 
    This script is needed for newer versions of the GAE SDK.
    You have to manually remove the symlink when you change this 
    flag from True to False.
    
url
    The url for fetching the google appengine distribution

use_setuptools_pkg_resources
    Flag whether the recipe shall copy setuptool's pkg_resources.py into the
    app directory rather than writing a dummy version. (Default=False)

zip-name
    The name of the zip archive containing all external packages ready
    to deploy.

zip-packages
    Flag whether external packages shall be zipped into a single zip file.
    (Default=True)


Tests
=====

We will define a buildout template used by the recipe:

    >>> buildout_template = """
    ... [buildout]
    ... develop = %(dev)s
    ... parts = sample
    ...
    ... [sample]
    ... recipe = rod.recipe.appengine
    ... eggs = foo.bar
    ... packages =
    ...     bazpkg
    ...     tinypkg
    ... server-script = dev_appserver
    ... zip-packages = False
    ... exclude = .*foo/bar/test.*$
    ... url = http://googleappengine.googlecode.com/files/google_appengine_1.5.0.zip
    ... """

We'll start by creating a buildout:

    >>> import os.path
    >>> import rod.recipe.appengine.tests as tests
    >>> egg_src = os.path.join(os.path.split(tests.__file__)[0], 'foo.bar')
    >>> baz_pkg = os.path.join(os.path.split(tests.__file__)[0], 'bazpkg')
    >>> tiny_pkg = os.path.join(os.path.split(tests.__file__)[0], 'tinypkg')
    >>> write('buildout.cfg', buildout_template %
    ...       {'dev': egg_src+' '+baz_pkg+' '+tiny_pkg})

Running the buildout gives us:

    >>> print system(buildout)
    Develop: '.../tests/foo.bar'
    Develop: '.../tests/bazpkg'
    Develop: '.../tests/tinypkg'
    Installing sample.
    rod.recipe.appengine: downloading Google App Engine distribution...
    Generated script '/sample-buildout/bin/dev_appserver'.
    Generated script '/sample-buildout/bin/appcfg'.

This will generate some scripts:

    >>> ls('bin')
    -  appcfg
    -  buildout
    -  dev_appserver

And now we try to run the appserver script:

    >>> print system(os.path.join('bin', 'dev_appserver'), '-h')
    Runs a development application server for an application.
    ...

There should be a configuration script in bin as well:

    >>> print system(os.path.join('bin', 'appcfg'))
    Usage: appcfg [options] <action>
    ...

Let's see if the 'tests' directory has been excluded:

    >>> l = os.listdir(os.sep.join(['parts', 'sample', 'foo', 'bar']))
    >>> assert 'tests' not in l

There should be a baz package within our application directory:

    >>> assert 'baz' in os.listdir(os.sep.join(['parts', 'sample']))

Let's define another buildout template used by the recipe:

    >>> buildout_template = """
    ... [buildout]
    ... develop = %(dev)s
    ... parts = second_sample
    ...
    ... [second_sample]
    ... recipe = rod.recipe.appengine
    ... eggs = foo.bar
    ... use_setuptools_pkg_resources = True
    ... packages =
    ...     bazpkg
    ...     tinypkg
    ... patch = %(patch)s
    ... patch-options = -p1
    ... zip-packages = False
    ... exclude = tests
    ... url = http://googleappengine.googlecode.com/files/google_appengine_1.5.0.zip
    ... """

We'll start by creating a buildout:

    >>> import os.path
    >>> import rod.recipe.appengine.tests as tests
    >>> egg_src = os.path.join(os.path.split(tests.__file__)[0], 'foo.bar')
    >>> baz_pkg = os.path.join(os.path.split(tests.__file__)[0], 'bazpkg')
    >>> tiny_pkg = os.path.join(os.path.split(tests.__file__)[0], 'tinypkg')
    >>> patch = os.path.join(os.path.split(tests.__file__)[0], 'patch.diff')
    >>> write('buildout.cfg', buildout_template %
    ...       {'dev': egg_src+' '+baz_pkg+' '+tiny_pkg, 'patch': patch})

Running the buildout gives us:

    >>> output = system(buildout)
    >>> if output.endswith(
    ...     "patching file lib/patched/patched.txt\n"): True
    ... else: print output
    True

And now we try to run the appserver script:

    >>> print system(os.path.join('bin', 'second_sample'), '-h')
    Runs a development application server for an application.
    ...

Let's have a look if all dependent packages are copied into our application
directory:

    >>> os.path.isfile(os.path.join('parts', 'second_sample', 'tinymodule.py'))
    True
    >>> os.path.isdir(os.path.join('parts', 'second_sample', 'baz'))
    True

Setuptool's original pkg_resources.py file should be copied into our app
directory:

    >>> pkg_resources = os.path.join(
    ...     'parts', 'second_sample', 'pkg_resources.py')
    >>> os.path.isfile(pkg_resources)
    True
    >>> pkg_resources_file = open(pkg_resources, "r")
    >>> pkg_resources_file.read().startswith('def _dummy_func')
    False
    >>> pkg_resources_file.close()

We've configured the recipe to patch the SDK's source tree:

    >>> gae_sdk_root = os.path.join('parts', 'google_appengine')
    >>> patched_dir = os.listdir(os.path.join(gae_sdk_root, 'lib'))
    >>> patched_file = open(
    ...     os.path.join(gae_sdk_root, 'google', 'appengine', 'tools',
    ...                  'dev_appserver.py')).read()[:1300]
    >>> 'patched' in patched_dir
    True
    >>> '# This file is patched by the patch command.' in patched_file
    True

You can also add some extra script:

    >>> buildout_template = """
    ... [buildout]
    ... develop = %(dev)s
    ... parts = script_sample
    ...
    ... [script_sample]
    ... recipe = rod.recipe.appengine
    ... eggs = foo.bar
    ... use_setuptools_pkg_resources = True
    ... packages =
    ...     bazpkg
    ...     tinypkg
    ... zip-packages = False
    ... exclude = tests
    ... url = http://googleappengine.googlecode.com/files/google_appengine_1.5.0.zip
    ... entry-points = manage=django.core:execute_manager
    ... initialization = import settings
    ... arguments = settings
    ... # your script may need some extra-paths
    ... extra-paths =
    ...    /some/extra/path
    ...    ${buildout:parts-directory}/google_appengine/lib/simplejson
    ... """

We'll start by creating a buildout:

    >>> import os.path
    >>> import rod.recipe.appengine.tests as tests
    >>> egg_src = os.path.join(os.path.split(tests.__file__)[0], 'foo.bar')
    >>> baz_pkg = os.path.join(os.path.split(tests.__file__)[0], 'bazpkg')
    >>> tiny_pkg = os.path.join(os.path.split(tests.__file__)[0], 'tinypkg')
    >>> write('buildout.cfg', buildout_template %
    ...       {'dev': egg_src+' '+baz_pkg+' '+tiny_pkg})

    >>> print 'Start...', system(buildout)
    Start...
    Generated script '/sample-buildout/bin/manage'...

Then you get a script:

    >>> cat('bin', 'manage')
    #!...python...
    import sys
    sys.path[0:0] = [
        '/some/extra/path',
        '/sample-buildout/parts/google_appengine/lib/simplejson',
        '/sample-buildout/parts/google_appengine',
        ]
    <BLANKLINE>
    <BLANKLINE>
    import settings
    <BLANKLINE>
    import django.core
    <BLANKLINE>
    if __name__ == '__main__':
        django.core.execute_manager(settings)
