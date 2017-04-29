# -*- mode: python, indent-tabs-mode: nil -*-
#
# This module handles finding/extracting files from directories, paths and
# tarballs.  It can handle:
#
#   1. Uncompressed files,
#   2. Gzip-compressed files,
#   3. BZ2-compressed files,
#   4. Uncompressed tarfiles,
#   5. Gzip-compressed tarfiles,
#   6. BZ2-compressed tarfiles.
#   7. Directory paths; recursively finds files, AND WILL inspect all found
#      tarballs if requested.
#
# For example, to handle all "foobar.log" files, including ones with
# suffixes from rename and compression by logrotate:
#
#   def file_handler(fileobj, filename, archivename, info, match):
#      print("File: \"{}\"{}".format(filename,
#            (" from: " + archivename) if archivename is not None else ""))
#
#   PATTERN = re.compile(r'(.*/)?foobar\.log.*')
#
#   scanner = TarWalker(file_handler, name_matcher=PATTERN.match,
#                       recurse_archives=True)
#   for path in sys.argv[1:]:
#     scanner.handle_path(path)
#
# If `info` is not None, then it will at least have the attributes: size,
# mtime, mode, uid, gid
#
# Note: to abort scanning of an archive, the 'file_handler' should raise a
# StopIteration, but this will only stop the current archive (if scanning a
# recursive archive).
#
import logging
import os
import tarfile

from io import BytesIO
from gzip import GzipFile
from bz2 import BZ2File, decompress as bz2decompress
from collections import namedtuple


__version__ = "1.0"
__credits__ = "NVRAM"
__author__ = "NVRAM (nvram@users.sourceforge.net)"
__date__ = "Sat Apr 29 22:19:38 UTC 2017"
__descr__ = ('A library to walk through tar archives, simplifying use by ' +
             'handling listing and decompression.')

FileInfo = namedtuple('FileInfo', 'size,mtime,mode,uid,gid')


def get_file_info(path):
    # Create an `info` object for a non-archived file.
    stat = os.stat(path)
    info = FileInfo(size=stat.st_size, mtime=stat.st_mtime, mode=stat.st_mode, uid=stat.st_uid, gid=stat.st_gid)
    return info


#
# Use to scan files and contents of tarballs; this class WILL NOT handle
# directories as TarDirWalker would.
#
class TarWalker(object):
    """Provides a simple way to read on-disk files; compressed or uncompressed files directly or streamed from
    within compressed or uncompressed tarballs.

    Construct with:
    @param file_handler a callable that takes three parameters:
            FILEOBJ, FILEPATH (str), ARCHIVENAME (str or None)

    @param file_matcher optional, a callable that takes two parameters and returns true if the file be passed
    to `file_handler`:
               FILEPATH,FILEINFO
    @param name_matcher optional, a callable that takes one parameter and returns true if the file be passed
    to `file_handler`:
               FILEPATH

    1. FILEPATH (str, possibly relative, possibly the name within a tarball)
       - PATH will have any compression suffix removed; "logs/xyz.log.2.gz" will be passed as "logs/xyz.log.2"
       - Empty files (and tarballs if not recursing) within tarballs are
         ignored (default: always true)
    2. FILEINFO is a namedtuple (tarwalker.FileInfo) with members:
         size, mtime, mode, uid, gid

    @param If true, recurse into tarballs found within tarballs. If a callable is given, it will be called
    before and after such a recursion with parameters:
           - START = a bool that indicates recursing is starting, or ended.
           - TARNAME = the name of the contained tarball file to be opened.
           - ARCHIVE = the name of the contaiing tarball files, colon-separated.
           - INFO = a FILEINFO object
    """
    def __init__(self, file_handler, file_matcher=None, name_matcher=None, recurse=False):
        # TODO: allow control in following of links.
        logging.debug("file_handler=%s, file_matcher=%s, name_matcher=%s, recurse=%s",
                     file_handler, file_matcher, name_matcher, recurse)
        if file_matcher and name_matcher:
            raise RuntimeError("Do not provide both a 'file_matcher' and a 'name_matcher'.")
        self.handler = file_handler
        self.recurse = recurse
        self.files = []
        if file_matcher:
            self.matcher = file_matcher
        elif name_matcher:
            self.matcher = lambda name, *info: name_matcher(name)
        else:
            self.matcher = lambda *args: True

    def handle_path(self, param):
        """Handle the given file (str or fileobj), calling back into the `name_matcher` or
        `file_handler` as appropriate"""
        if isinstance(param, str):
            name = param
            param = None
        else:
            name = getattr(param, 'name', None)
            assert isinstance(name, str)

        # Determine type and compression scheme by suffix.
        _path, ctype, ftype = self._file_type(name)

        # Always scan top-level tarballs.
        if ftype == self.Types.TARBALL:
            return self._tarball(tarname=name, tarobj=param)

        # For other files, we do the same as file within a tarball.
        try:
            info = get_file_info(name)
        except Exception as exc:
            message = getattr(exc, 'message', str(exc))
            message = getattr(exc, 'strerror', message)
            logging.error("Failure [%s] with: %s", message, name)
            return
        match = self.matcher(name, info)
        if match:
            return self._file(name, param, ctype, ftype, None, info, match)

    def _handle(self, fpath, fobj, ctype, ftype, archive, info, match):
        logging.debug("_HANDLE(\"%s\", %s, %s, %s, \"%s\", %s)...", fpath, type(fobj), ctype, ftype, archive, info)
        assert fpath and fobj
        self.handler(fobj, fpath, archive or None, info, match)
        self.files.append((fpath, archive and (archive + ":") or "", ftype, ctype, info, match))

    def _file(self, fpath, fobj, ctype, ftype, archive, info, match):
        # We don't consult the matcher since it's either done or was a
        # top-level filename.
        assert ftype == self.Types.NORMAL
        if ctype == self.Types.GZIP:
            logging.debug("GZ._FILE(\"%s\", %s, %s, %s, \"%s\")...", fpath, type(fobj), ctype, ftype, archive)
            with GzipFile(filename=fpath, fileobj=fobj, mode="r") as gzfile:
                return self._handle(fpath, gzfile, ctype, ftype, archive, info, match)

        elif ctype == self.Types.BZIP:
            # BZ2File can't wrap a "file" until v3.4
            if isinstance(fobj, tarfile.ExFileObject):
                fobj = BytesIO(bz2decompress(fobj.read()))
                return self._handle(fpath, fobj, ctype, ftype, archive, info, match)
            logging.debug("BZ._FILE(\"%s\", %s, %s, %s, \"%s\") ==> [%s]...", fpath, type(fobj), ctype, ftype,
                          archive, type(fobj))
            with BZ2File(fobj or fpath, mode="rb") as bzfile:
                return self._handle(fpath, bzfile, ctype, ftype, archive, info, match)

        elif fobj:
            logging.debug("FO._FILE(\"%s\", %s, %s, %s, \"%s\")...", fpath, type(fobj), ctype, ftype, archive)
            return self._handle(fpath, fobj, ctype, ftype, archive, info, match)

        else:
            logging.debug("FP._FILE(\"%s\", %s, %s, %s, \"%s\")...", fpath, type(fobj), ctype, ftype, archive)
            with open(fpath, 'r') as fobj:
                return self._handle(fpath, fobj, ctype, ftype, archive, info, match)

    def _tarball(self, tarname, tarobj):
        # If we were called with just path rather than a file object, open it and recurse once.
        if not tarobj or isinstance(tarobj, str):
            assert tarname
            logging.debug(" OPENED File: %s", tarname)
            with open(tarname, "rb") as tarobj:
                return self._tarball(tarname, tarobj)

        # Loop through each entry in the tarball
        logging.debug("TARFILE.OPEN(name=\"%s\", fileobj[%s], mode='r')...",
                      tarname, type(tarobj))
        with tarfile.open(name=tarname, fileobj=tarobj, mode="r") as bundle:
            logging.debug("Scanning Tarball: %s", tarname)
            while True:
                info = bundle.next()
                if not info:
                    break
                if not info.isfile() or info.size == 0:
                    continue
                path, ctype, ftype = self._file_type(info.name)
                if ftype == self.Types.TARBALL:
                    if self.recurse:
                        if callable(self.recurse):
                            logging.warning("Recursing into: %s (%s)", tarname, info)
                            self.recurse(True, tarname, info.name, info)
                        self._tarball(tarname + ":" + info.name, bundle.extractfile(info))
                        if callable(self.recurse):
                            logging.warning("Recursion done: %s (%s)", tarname, info)
                            self.recurse(False, tarname, info.name, info)

                    # Without 'recurse' never even ask about embedded tarballs.
                    continue
                match = self.matcher(path, info)
                if not match:
                    logging.debug(" Skipping tarball file: %s", path)
                    continue
                try:
                    self._file(path, bundle.extractfile(info), ctype, ftype, tarname, info, match)
                except StopIteration:
                    logging.warning("NOTICE: aborting tarball: %s", tarname)
                    break
                except Exception as exc:
                    logging.exception("With %s:%s DETAIL: %s", tarname, info.name, exc)
                    raise

    # An enum of file types we handle here.
    Types = type('Types', (), dict([(x, x) for x in ('NONE', 'GZIP', 'BZIP', 'TARBALL', 'NORMAL')]))

    # Not a dictionary since order matters (test ".tar.gz" before ".gz")
    SUFFIXES = (
        (Types.NONE, Types.TARBALL, '.tar'),
        (Types.GZIP, Types.TARBALL, '.tar.gz'),
        (Types.GZIP, Types.TARBALL, '.tgz'),
        (Types.BZIP, Types.TARBALL, '.tar.bz'),
        (Types.BZIP, Types.TARBALL, '.tar.bz2'),
        (Types.BZIP, Types.TARBALL, '.tbz'),
        (Types.BZIP, Types.TARBALL, '.tbz2'),
        (Types.GZIP, Types.NORMAL, '.gz'),
        (Types.BZIP, Types.NORMAL, '.bz'),
        (Types.BZIP, Types.NORMAL, '.bz2'),
        (Types.GZIP, Types.NORMAL, '.z'),
    )

    @classmethod
    def _file_type(cls, path):
        """Returns the FileType enum value based only on the file suffix."""
        for ctype, ftype, suff in cls.SUFFIXES:
            if path.lower().endswith(suff):
                base = path[:-len(suff)]
                return base, ctype, ftype
        return path, cls.Types.NONE, cls.Types.NORMAL


#
# A simple way to recursively scan directories, too.  Note that
# TarDirWalker.handle_path() will look into any tarballs that are found within
# a given directory -- in addition to any files that match the name_matcher
# filter.
#
class TarDirWalker(TarWalker):
    """This class wraps an TarWalker and handles directories recursively."""
    def __init__(self, file_handler, **kwds):
        super(TarDirWalker, self).__init__(file_handler, **kwds)

    def handle_path(self, param):
        # Handle directories here.
        if isinstance(param, str) and os.path.isdir(param):
            logging.debug("Scanning Directory: %s", param)
            for dname, _subdirs, files in os.walk(param):
                for fname in files:
                    fname = os.path.join(dname, fname)
                    logging.debug('TarDirWalker.handle_path("%s")', fname)
                    ftype = self._file_type(fname)
                    if ftype[1] != self.Types.NONE:
                        logging.debug('TarWalker.handle_path("%s")', fname)
                        super(TarDirWalker, self).handle_path(fname)
                    elif (self.matcher and
                          self.matcher(fname, get_file_info(fname))):
                        logging.debug('TarWalker.handle_path("%s")', fname)
                        super(TarDirWalker, self).handle_path(fname)
                    elif ftype[2] == self.Types.TARBALL and self.recurse:
                        logging.debug('Scanning TARBALL: %s', fname)
                        super(TarDirWalker, self).handle_path(fname)
                    else:
                        logging.debug('TarWalker.ignored_path("%s")', fname)
        else:
            super(TarDirWalker, self).handle_path(param)
