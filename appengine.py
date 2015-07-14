"""Recipe for setting up a Google App Engine development environment."""

import logging
import os
import re
import shutil
import tempfile
import urllib
import zipfile
from zc.buildout.buildout import Options
from zc.recipe.egg import Eggs, Scripts

logger = logging.getLogger(__name__)

rx_setuptools = re.compile(
    '^.*' + re.escape(os.sep) + '(setuptools|distribute)-.*?-py\d.\d.egg$')

dev_appserver_initialization = '''
import os

def mkvar():
  var = %(var)r
  if not os.path.exists(var):
    os.mkdir(var)
  return var
os.environ['TMPDIR'] = mkvar()

from %(script_name)s import *
'''

def copytree(src, dst, symlinks=0, allowed_basenames=None, exclude=[]):
    """Local implementation of shutil's copytree function.

    Checks wheather destination directory exists or not
    before creating it.
    """
    if not os.path.isdir(src):
        # Assume that the egg's content is just one or more modules
        src = os.path.dirname(src)
        dst = os.path.dirname(dst)
    names = os.listdir(src)
    if not os.path.exists(dst):
        os.mkdir(dst)
    for name in names:
        base, ext = os.path.splitext(name)
        if ext == ".egg-info":
            continue
        srcname = os.path.join(src, name)
        srcname = os.path.normpath(srcname)
        dstname = os.path.join(dst, name)
        dstname = os.path.normpath(dstname)
        if allowed_basenames:
            if os.path.isfile(srcname):
                if name not in allowed_basenames:
                    logger.debug("Skipped %s" % srcname)
                    continue
        if os.path.basename(srcname) in exclude:
            continue
        matched = False
        for pattern in exclude:
            if re.match(pattern, srcname):
                matched = True
                break
        if matched:
            continue
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, allowed_basenames, exclude)
            elif not os.path.isfile(dstname) and symlinks:
                os.symlink(srcname, dstname)
            elif not symlinks:
                shutil.copy2(srcname, dstname)
        except (IOError, os.error), why:
            logging.error("Can't copy %s to %s: %s" %
                          (srcname, dstname, str(why)))


class Zipper(object):
    """Provides a zip file creater."""

    def __init__(self, name, topdir, mode = "w"):
        """Initializes zipper."""
        self.name = name
        self.zip = zipfile.ZipFile(name, mode, zipfile.ZIP_DEFLATED)
        os.chdir(os.path.abspath(os.path.normpath(topdir)))
        self.topdir = os.getcwd()

    def close(self):
        self.zip.close()

    def add(self, fname, archname=None, compression_type=zipfile.ZIP_DEFLATED):
        """Adds a file to the zip archive."""
        if archname is None:
            archname = fname

        normfname = os.path.abspath(os.path.normpath(archname))
        if normfname.startswith(self.topdir) and \
           normfname[len(self.topdir)] == os.sep:
            archivename = normfname[len(self.topdir) + 1:]
        else:
            raise RuntimeError, "%s: not found in %s" % (archname, self.topdir)

        self.zip.write(
            os.path.realpath(fname), archivename, compression_type)


class Recipe(Scripts):
    """Buildout recipe for Google App Engine."""

    default_appserver_script_name = 'dev_appserver.py'

    def __init__(self, buildout, name, opts):
        """Standard constructor for zc.buildout recipes."""

        super(Recipe, self).__init__(buildout, name, opts)
        opts['app-directory'] = os.path.join(buildout['buildout']
                                             ['parts-directory'],
                                             self.name)
        # avoid warnings
        opts.get('entry-points')
        opts.get('arguments')


    def _fetch_appengine_lib(self):
        gae = self.options.get('appengine-lib')
        if gae is None:
            gae = os.path.join(self.buildout['buildout']['parts-directory'],
                               'google_appengine')
        return gae


    def write_server_script(self, name, bin):
        """Generates bin script with given name."""

        var = os.path.join(self.buildout['buildout']['parts-directory'], '%s_var' % self.name)
        if not os.path.isdir(var):
            os.makedirs(var)

        script_name = self.get_appserver_script_name().partition('.')[0]

        options = self.options.copy()
        options['eggs'] = ''
        run_file = '_' + self.options['appserver-run-file']
        options['entry-points'] = '%s=%s:%s' % (name, script_name, run_file)
        options['initialization'] = dev_appserver_initialization % dict(var=var, script_name=script_name)
        options['initialization'] += '\n' + self.options.get('initialization', '')
        options['arguments'] = '%r, locals()' % bin
        options = Options(self.buildout, self.name, options)
        scripts = Scripts(self.buildout, self.name, options)
        scripts.install()

    def write_appcfg_script(self, bin):
        """Generates the app configuration script in bin."""
        options = self.options.copy()
        options['eggs'] = ''
        run_file = self.options['appserver-run-file']
        options['entry-points'] = 'appcfg=appcfg:%s' % run_file
        options['arguments'] = '%r, locals()' % bin
        options = Options(self.buildout, self.name, options)
        scripts = Scripts(self.buildout, self.name, options)
        scripts.install()

    def write_extra_scripts(self):
        options = self.options.copy()
        options['eggs'] = ''
        options = Options(self.buildout, self.name, options)
        scripts = Scripts(self.buildout, self.name, options)
        scripts.install()


    def create_gae_runtime_script(self):
        if (self.options.get('symlink-gae-runtime', 'YES').lower()
                in ['yes', 'true']):
            gae = self._fetch_appengine_lib()
            runtime_script_name = "_python_runtime.py"
            srcname = os.path.join(gae, runtime_script_name)
            dstname = os.path.join(self.buildout['buildout']['bin-directory'],
                                        runtime_script_name)
            if not os.path.exists(srcname):
                logger.warn(
                    "Symlink not possible, '%s' is not available" % dstname)
            else:
                try:
                    os.symlink(srcname, dstname)
                except OSError as e:
                    if e.errno != 17:
                        raise


    def install_appengine(self):
        """Downloads and installs Google App Engine."""
        def parse_version(s):
            p, _, ver = s.split('\n')[0].partition(':')
            assert p == 'release', 'Could not parse GAE SDK version'
            return ver.strip(' "')

        arch_filename = self.options['url'].split('/')[-1].split(os.sep)[-1]
        dst = os.path.join(self.buildout['buildout']['parts-directory'])
        downloads_dir = os.path.join(os.getcwd(), 'downloads')
        downloads_dir = self.buildout['buildout'].get('download-cache', downloads_dir)
        tmpdir = None
        if not os.path.isdir(downloads_dir):
            os.mkdir(downloads_dir)
        src = os.path.join(downloads_dir, arch_filename)
        if not os.path.isfile(src):
            if tmpdir is None:
                tmpdir = tempfile.mkdtemp()
            tmpdl = os.path.join(tmpdir, arch_filename)
            logger.info("downloading Google App Engine distribution...")
            urllib.urlretrieve(self.options['url'], tmpdl)
            shutil.move(tmpdl, src)
        else:
            logger.info("Google App Engine distribution already downloaded.")
        unpack = True
        arch = zipfile.ZipFile(open(src, "rb"))
        if os.path.isdir(os.path.join(dst, 'google_appengine')):
            version_in_zip = parse_version(arch.read('google_appengine/VERSION'))
            with open(os.path.join(dst, 'google_appengine', 'VERSION')) as fd:
                version_in_dst = parse_version(fd.read())
            if version_in_zip != version_in_dst:
                shutil.rmtree(os.path.join(dst, 'google_appengine'))
            else:
                logger.info("Google App Engine distribution already installed.")
                unpack = False
        if unpack:
            logger.info("installing Google App Engine distribution...")
            if tmpdir is None:
                tmpdir = tempfile.mkdtemp()
            for name in arch.namelist():
                if name and name[-1] in (os.sep, '/'):
                    os.mkdir(os.path.join(tmpdir, name))
                else:
                    outfile = open(os.path.join(tmpdir, name), 'wb')
                    outfile.write(arch.read(name))
                    outfile.close()
            shutil.move(os.path.join(tmpdir, 'google_appengine'), os.path.join(dst, 'google_appengine'))
        if tmpdir is not None:
            shutil.rmtree(tmpdir)

    def setup_bin(self):
        """Setup bin scripts."""

        gae = self._fetch_appengine_lib()
        extra_paths = self.options.get('extra-paths', '')
        extra_paths += '\n' + gae
        self.options['extra-paths'] = extra_paths
        self.options['appserver-run-file'] = self.options.get(
                                'appserver-run-file', 'run_file')

        # Write server script
        gae_server = os.path.join(gae, self.get_appserver_script_name())
        self.write_server_script(self.options.get('server-script', self.name),
                                 gae_server)

        # Write app configuration script
        gae_config = os.path.join(gae, 'appcfg.py')
        self.write_appcfg_script(gae_config)

        self.write_extra_scripts()
        self.create_gae_runtime_script()

    def get_appserver_script_name(self):
        """Returns the default appserver script name."""
        return self.options.get('appserver-script-name',
            self.default_appserver_script_name )

    def copy_packages(self, ws, lib, entries):
        """Copy egg contents to lib-directory."""
        if not os.path.exists(lib):
            os.mkdir(lib)
        for key in entries.keys():
            top_level = os.path.join(ws.by_key[key]._provider.egg_info,
                                     'top_level.txt')
            top = open(top_level, 'r')
            top_dir = top.read()
            src = os.path.join(entries[key], top_dir.strip())
            top.close()
            dir = os.path.join(lib, os.path.basename(src))
            egg_info_src = os.path.join(ws.by_key[key]._provider.egg_info,
                                        'SOURCES.txt')
            sources = open(egg_info_src, 'r')
            allowed_basenames = [os.path.basename(p.strip())
                                 for p in sources.readlines()]
            sources.close()
            if not os.path.exists(dir) and os.path.exists(src):
                os.mkdir(dir)
            exclude = ['EGG-INFO'] # Exclude this every time
            copytree(src, dir, hasattr(os, 'symlink'),
                     allowed_basenames=allowed_basenames,
                     exclude=exclude+self.options.get('exclude', '').split())

    def zip_packages(self, ws, lib):
        """Creates zip archive of configured packages."""

        zip_name = self.options.get('zip-name', 'packages.zip')
        zipper = Zipper(os.path.join(self.options['app-directory'],
                                     zip_name), lib)
        os.chdir(lib)
        for root, dirs, files in os.walk('.'):
            for f in files:
                zipper.add(os.path.join(root, f))
        zipper.close()

    def copy_sources(self):
        """Copies the application sources."""
        options = self.options
        src = None
        if options.get('src'):
            src = os.path.join(self.buildout['buildout']['directory'],
                               options['src'])
        if src:
            sources = [src]
        else:
            reqs, ws = self.working_set()
            sources = [d.location for d in ws if d.key in reqs]
        for s in sources:
            copytree(s, options['app-directory'], hasattr(os, 'symlink'),
                     exclude=options.get('exclude', '').split())

    def patch_sdk(self, patch_options, patch_file):
        """Patches the SDK's source tree."""
        if patch_options:
            patch_options = patch_options.split(' ')
        else:
            patch_options = ['-p1']
        gae = os.path.join(self.buildout['buildout']['parts-directory'],
                           'google_appengine')
        os.chdir(gae)
        patch_cmd = ['patch'] + patch_options + ['<', patch_file]
        retcode = os.system(' '.join(patch_cmd))
        if retcode != 0:
            raise Exception("patching the SDK failed")
        return 0

    def get_entries(self, ws, packages):
        for p in packages:
            if p not in ws.by_key.keys():
                raise KeyError('{}: package not found.'.format(p))
        entries = {}
        for k in ws.entry_keys:
            key = ws.entry_keys[k][0]
            if key in packages:
                entries[packages[packages.index(key)]] = k
        return entries

    def install(self):
        """Creates the part."""
        options = self.options
        if not self.options.get('appengine-lib', False):
            self.install_appengine()
        self.setup_bin()
        reqs, ws = self.working_set()
        app_dir = options['app-directory']
        if options.get('zip-packages', 'YES').lower() in ['yes', 'true']:
            temp_dir = os.path.join(tempfile.mkdtemp(), self.name)
        else:
            temp_dir = app_dir
        if os.path.isdir(app_dir):
            shutil.rmtree(app_dir, True)
        if not os.path.exists(app_dir):
            os.mkdir(app_dir)
        packages = self.options.get('packages', '').split()
        packages = [p.lower() for p in packages]
        entries = self.get_entries(ws, packages)
        not_zip_safe_packages = dict(filter(
            lambda item: os.path.exists(os.path.join(ws.by_key[item[0]]._provider.egg_info, 'not-zip-safe')),
            entries.iteritems()
        ))
        zip_safe_packages = {key: item for key, item in entries.iteritems() if key not in not_zip_safe_packages}
        self.copy_packages(ws, temp_dir, zip_safe_packages)
        self.copy_packages(ws, app_dir, not_zip_safe_packages)
        if options.get('zip-packages', 'YES').lower() in ['yes', 'true']:
            self.zip_packages(ws, temp_dir)
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, True)
        self.copy_sources()
        patch_file = options.get('patch')
        patch_options = options.get('patch-options')
        if patch_file:
            if options.get('appengine-lib'):
                raise Exception("patching preinstalled SDK not allowed")
            self.patch_sdk(patch_options, patch_file)
        return ()

    def update(self):
        """Updates the part."""
        options = self.options
        self.setup_bin()
        reqs, ws = self.working_set()
        self.copy_sources()
        return ()
