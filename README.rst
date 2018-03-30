tarwalker
=========

Summary
-------
 
This library provides two (2) classes for scanning directories and tar
archives to easily access matching files within them.

- *TarWalker* handles walking through tar archives, including
  optionally recursively walking through tar archives contained within
  them.

- *TarDirWalker* this expands on *TarWalker* by also scanning directory
  paths, and handling the files and tar archives found within them.

The primary difference is that *TarWalker* will throw an exception if
given a directory.

----------

.. contents:: **Index**
   :depth: 2
   :local:

Installation
------------
Install the package using **pip**, eg:

     sudo pip install tarwalker

Or for a specific version:

     sudo python3 -m pip install tarwalker

Examples
--------

The following is simple tool to look for a given string within files.
Files can be given as arguments or within tarballs, and must end with
either '.log' (w/an optional numeric suffix) or with '.txt':

.. code:: python

    import re
    import sys

    from tarwalker import TarWalker

    PATTERN = re.compile(r'.*\.(txt|log(\.\d+)?)$')


    def handler(fileobj, filename, arch, info, match):
        try:
            for line in fileobj:
                if text in line:
                    path = (arch + ':') if arch else ''
                    print("Found in: " + path + filename)
                    return
        except IOError:
            pass


    text = sys.argv[1]
    walker = TarWalker(file_handler=handler, name_matcher=PATTERN.match, recurse=False)

    for arg in sys.argv[2:]:
        walker.handle_path(arg)
  


Constructors and Callbacks
--------------------------

Constructing an instance of *TarWalker* or *TarDirWalker* take the
same parameters.  Note that at most one of *file_matcher* or
*name_matcher* is allowed.

* *file_handler* (required) a callable taking five (5) positional parameters:

   * FILEOBJ - a readable *file* object for the file contents.
   * FILEPATH - a *str* with the filename, either as one of:

      * the file path given to *handle_path()*, or
      * the path of a file found beneath a directory given to *handle_path()*.
      * the file path of a file within an expanded tar archive.

   * ARCHNAME - a *str* path of the tar archive name, when handling a
     file found within a tar archive.  It will be a colon (':')
     separated list if reading a recursive tar archive.

   * FILEINFO - may be *None* or an object with the following
     attributes.  See "os.stat()" for more details:

      * name - the *str* name of the file,
      * size - the size of the file in bytes,
      * mtime - modification time, in POSIX (epoch) time,
      * mode - the file permission bits,
      * uid - the file owner's User ID, and
      * gid - the file owner's Group ID

   * MATCH - the value returned from the *name_matcher* or *file_matcher* call.

   **NOTE:** files with a compression suffix will have the suffix
   removed, and the file object will return decompressed contents.
   *For example*, for "foo.txt.gz" FILEPATH would be "foo.txt" and FILEOBJ
   would be the equivalent contents of "foo.txt".

* *file_matcher* (optional) a callable that takes two (2) positional
  parameters and returns true if the file should be opened and
  passed to the *file_handler* callback:

   * FILEPATH - See *FILEPATH* above.
   * FILEINFO - See *FILEINFO* above.

* *name_matcher (optional) a callable that takes one (1) positional
  parameter  and returns true if the file be opened and passed to
  *file_handler*:

   * FILEPATH - See *file_handler*, above.

* *recurse* (optional) If true, the algorithm will recurse into
  tarballs found within other tarballs. Furthermore, if *recurse* is a
  callable it will be called before and after opening an interior
  tarball, with four (4) positional parameters:

    * START - a bool that indicates recursion into the given tarball
      is starting; it is False on the second call.
    * TARNAME - name of the contained (interior) tarball, see *FILEPATH* above.
    * ARCHIVE - the name of the containing (exterior) tarball, see *ARCHNAME* above.
    * FILEINFO - See *FILEINFO* above.


Build Status
------------

.. image:: https://travis-ci.org/n2vram/tarwalker.svg?master
    :alt: Build Status
    :target: https://travis-ci.org/n2vram/tarwalker

Known Issues
------------

- The ARCHNAME passed to the *file_handler* callback uses ':' as a
  separator, which is a legal filename component, so does not
  necessarily indicate a nested archive.
