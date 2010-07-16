# The following version determination code is a greatly simplified version
# of the mercurial repo code. The version is stored in nml/__version__.py
# get_numeric_version is used only for the purpose of packet creation,
# in all other cases use get_version()

import subprocess, os, sys

def get_hg_version():
    path = os.path.dirname(os.path.realpath(sys.argv[0]))
    version = ''
    if os.path.isdir(os.path.join(path,'.hg')):
        # we want to return to where we were. So save the old path
        version_list = (subprocess.Popen(['hg', '-R', path, 'id', '-n', '-t', '-i'], stdout=subprocess.PIPE).communicate()[0]).split()
        if version_list[1].endswith('+'):
            modified = 'M'
        else:
            modified = ''
        revision = version_list[1].rstrip('+')
        hash = version_list[0].rstrip('+')
        # Test whether we have a tag (=release version)
        if len(version_list) > 2 and version_list[2] != 'tip':
			version = version_list[2]
        else: # we have a trunk version
            version = 'r'+revision
        # Add modification tag and hash to the stored version info
        version += modified + ' (' + hash + ')'
    return version

def get_version():
    # first try whether we find an nml repository. Use that version, if available
    version = get_hg_version()
    if version:
        return version
    # no repository was found. Return the version which was saved upon built
    try:
        from nml import __version__
        version = __version__.version
    except ImportError:
        version = 'unknown'
    return version

def get_and_write_version():
    version = get_version()
    if version:
        try:
            path = os.path.dirname(os.path.realpath(sys.argv[0]))
            f = open(os.path.join(path,"nml/__version__.py"), "w")
            f.write('# this file is autogenerated by setup.py\n')
            f.write('version = "%s"\n' % version)
            f.close()
            return (get_version().split())[0]
        except IOError:
            print "Version file NOT written"
