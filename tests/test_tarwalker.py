#!/usr/bin/env python3
#
# Tests for the module: common.mathstuff
#
import hashlib
import logging
import os
import py
import subprocess
import tempfile
from random import randint
from unittest import TestCase

# Module under test...
from tarwalker import TarWalker
from tarwalker import TarDirWalker

# logging.basicConfig(level=logging.INFO, format='%(message)s', datefmt='%Y-%m-%dT%X')

T = type('T', (), dict([(x, x) for x in ('NONE', 'GZip', 'BZip', 'Tarball', 'Normal')]))


def _md5(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    hasher = hashlib.md5()
    hasher.update(data)
    return hasher.hexdigest()


# This class handles the various on-disk files that will be used.
class ArchiveRepo(object):
    def __init__(self, basedir, fileformat="file{}.info"):
        self.create(basedir, fileformat)
        self.basedir = basedir

    def create(self, basedir, fileformat="file{}.info"):
        if getattr(self, 'basedir', None):
            logging.info('Not re-creating ArchiveRepo')
            assert basedir == self.basedir
        else:
            logging.info('ArchiveRepo.create("{}", "{}")'.format(basedir, fileformat))
            self.basedir = basedir
            self.tarballs = []
            self.fileformat = fileformat
            self.build_data(fileformat)
        return self

    def build_data(self, filename):
        # Doing this without actually arching files from disk is hard, let's go shopping!
        self.sums = {}
        self.build_subdir(filename, self.basedir.mkdir("norm"), "tar-norm.tar", "")
        self.build_subdir(filename, self.basedir.mkdir("gzip"), "tar-gzip.tgz", "-z")
        self.build_subdir(filename, self.basedir.mkdir("bzip"), "tar-bzip.tbz", "-j")

        # Create tarballs, too.
        sums = dict(self.sums)
        for compr, suff in ('-z', '.gz'), ('-j', '.bz'), ('-v', ''):
            tarball = 'tar-redux.tar' + suff
            inner = ['tar-norm.tar', 'tar-gzip.tgz', 'tar-bzip.tbz']
            self.call_proc(['tar', compr, '-cf', tarball] + inner)
            self.tarballs.append(tarball)
            for path, result in sums.items():
                root = path.split(':')[0]
                if root in inner:
                    self.sums[tarball + ":" + path] = result
                    logging.info("Inner: " + tarball + ":" + path)

    def build_subdir(self, filename, subdir, tarball, compress):
        gzips = ["gzip", "-9"]
        bzips = ["bzip2", "-9"]
        sums = {}
        for dname in 'one', 'two', 'three':
            dpath = subdir.mkdir(dname)
            for suff, comp in ('', T.Normal), ('-1', T.Normal), ('-2', T.GZip), ('-3', T.BZip), ('-0', None):
                basename = filename.format(suff)
                filepath = dpath.join(basename)
                relpath = filepath.relto(self.basedir.strpath)

                if comp is None:
                    numlines = 0
                else:
                    numlines = randint(2, 7)
                data = "".join(["{}:{}: Just some text.\n".format(relpath, lnum) for lnum in range(numlines)])
                filepath.write(data)

                # The tarball gets the filename without a suffix.
                result = (_md5(data), numlines)
                if numlines:
                    self.sums[tarball + ":" + relpath] = result
                if comp == T.GZip:
                    gzips.append(relpath)
                    relpath += '.gz'
                elif comp == T.BZip:
                    bzips.append(relpath)
                    relpath += '.bz2'
                sums[relpath] = result

            for other in range(3):
                other = dpath.join("IgnoreMe-%d.txt" % other)
                other.write(other.relto(self.basedir))

        # Add sums for the actual files.
        self.sums.update(sums)

        # Compress the intended files (replacing them on disk).
        self.call_proc(gzips)
        self.call_proc(bzips)

        # Create a tarball with the desired files.
        self.call_proc(['tar', compress, '-cf', tarball, subdir.relto(self.basedir)])
        self.tarballs.append(tarball)
        return sums

    EXPECT_RECURSED = ((True, 'tar-redux.tar', 'tar-norm.tar'),
                       (False, 'tar-redux.tar', 'tar-norm.tar'),
                       (True, 'tar-redux.tar', 'tar-gzip.tgz'),
                       (False, 'tar-redux.tar', 'tar-gzip.tgz'),
                       (True, 'tar-redux.tar', 'tar-bzip.tbz'),
                       (False, 'tar-redux.tar', 'tar-bzip.tbz'),
                       (True, 'tar-redux.tar.bz', 'tar-norm.tar'),
                       (False, 'tar-redux.tar.bz', 'tar-norm.tar'),
                       (True, 'tar-redux.tar.bz', 'tar-gzip.tgz'),
                       (False, 'tar-redux.tar.bz', 'tar-gzip.tgz'),
                       (True, 'tar-redux.tar.bz', 'tar-bzip.tbz'),
                       (False, 'tar-redux.tar.bz', 'tar-bzip.tbz'),
                       (True, 'tar-redux.tar.gz', 'tar-norm.tar'),
                       (False, 'tar-redux.tar.gz', 'tar-norm.tar'),
                       (True, 'tar-redux.tar.gz', 'tar-gzip.tgz'),
                       (False, 'tar-redux.tar.gz', 'tar-gzip.tgz'),
                       (True, 'tar-redux.tar.gz', 'tar-bzip.tbz'),
                       (False, 'tar-redux.tar.gz', 'tar-bzip.tbz'))

    EXPECT_ABORTED = (('tar-redux.tar:tar-norm.tar', 'norm/three/file-3.info'),
                      ('tar-redux.tar:tar-gzip.tgz', 'gzip/three/file-3.info'),
                      ('tar-redux.tar:tar-bzip.tbz', 'bzip/three/file-3.info'))

    def call_proc(self, command, **kwds):
        # Wait for the subprocess to finish, otherwise we might get bad data in the tarballs.
        logging.info("UNDER \"{}\" CALLING: {}".format(self.basedir.strpath, command))
        subprocess.Popen(command, cwd=self.basedir.strpath, **kwds).wait()


class Handler(object):
    def __init__(self, basedir, start_path="file"):
        self.start_path = start_path
        self.basedir = str(basedir)
        self.handled = {}
        self.abort = False
        self.aborted = []
        self.recursed = []

    @staticmethod
    def _md5(data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        hasher = hashlib.md5()
        hasher.update(data)
        return hasher.hexdigest()

    def matcher(self, path):
        base = os.path.basename(path)
        okay = base.startswith(self.start_path)
        return base if okay else None

    def trim(self, path):
        if path and path.startswith(self.basedir):
            return path[len(self.basedir) + 1:]
        return path

    def recurse(self, enter, parent, child, info):
        logging.info("[[Recurse]] %s \"%s\" within \"%s\", info: %s", "Start" if enter else "Finish",
                     parent, child, info)
        self.recursed.append((enter, os.path.basename(parent), child))

    def handler(self, fileobj, filepath, archive, info, match):
        logging.info("[[%s]] File: \"%s\" Info: [sz=%s uid/gid=%s/%s mode=%05o mt=%s Match:[[%s]]",
                     archive, filepath, info.size, info.uid, info.gid, info.mode, info.mtime, match)

        base_arch = archive and os.path.basename(archive)
        if self.abort:
            logging.warning("Aborting on file.: \"%s\":\"%s\"", archive, filepath)
            self.aborted.append((base_arch, filepath))
            raise self.abort("Giving up on %s:%s" % (base_arch, filepath))
        assert not self.aborted

        filepath = self.trim(filepath)
        archive = self.trim(archive)

        hasher = hashlib.md5()
        nlines = 0
        for line in fileobj:
            nlines += 1
            data = line if isinstance(line, bytes) else line.encode('utf-8')
            hasher.update(data)
        md5 = hasher.hexdigest()
        key = "{}{}{}".format(archive or '', archive and ':' or '', filepath)
        self.handled[key] = (md5, nlines, archive, match)

        logging.info("Handled[{}{}]: {}=> {}".format(archive and (archive+":") or "", filepath, nlines, md5))


class TestTarWalker(TestCase):

    def setUp(self):
        tmpdir = tempfile.mkdtemp(prefix='pytest-archscan.')
        self.basedir = py.path.local(tmpdir)
        self.archive_repo = ArchiveRepo(self.basedir)
        self.hook = Handler(self.basedir)

    def tearDown(self):
        logging.info("Removing files: {}".format(self.basedir))
        self.basedir.remove(rec=1)

    def test_dirscanner(self):
        logging.info("test_dirscanner: %s", self.basedir.strpath)
        self.scanner = TarDirWalker(self.hook.handler, name_matcher=self.hook.matcher, recurse=True)
        self.scanner.handle_path(self.basedir.strpath)
        self._validate_results()

    def test_archive_files(self):
        self.scanner = TarWalker(self.hook.handler, name_matcher=self.hook.matcher, recurse=self.hook.recurse)
        logging.info("Files are under: {}".format(self.basedir))

        files = sorted(map(str, self.basedir.visit(fil=lambda p: os.path.isfile(p.strpath))))
        logging.info("test_archive_files: Files: {}".format(files))
        index = len(self.basedir.strpath)+1
        for fpath in files:
            logging.info("Checking: {}".format(fpath))
            fname = fpath[index:]
            if fname.startswith('tar-') or self.scanner.matcher(fpath):
                self.scanner.handle_path(fpath)
            else:
                logging.info("Skipping file: " + str(fname))

        # Bad path gives (1) no exception raised and (2) return of None.
        result = self.scanner.handle_path("/this/path/is/invalid/we/hope")
        assert result is None

        self._validate_results()
        logging.info("RECURSED: " + str(self.hook.recursed))
        assert ArchiveRepo.EXPECT_RECURSED == tuple(self.hook.recursed)

    def test_archive_stop(self):
        self.scanner = TarWalker(self.hook.handler, name_matcher=self.hook.matcher, recurse=self.hook.recurse)

        # Test the StopIteration feature, stopping after recursions:
        self.hook.abort = StopIteration

        files = sorted(map(str, self.basedir.visit(fil=lambda p: os.path.isfile(p.strpath))))
        logging.info("test_archive_files: Files: {}".format(files))
        fpath = os.path.join(self.basedir.strpath, 'tar-redux.tar')
        with open(fpath, 'rb') as fobj:
            self.scanner.handle_path(fobj)
        logging.info("RECURSED: " + str(self.hook.recursed))
        logging.info("ABORTED: " + str(self.hook.aborted))
        assert ArchiveRepo.EXPECT_ABORTED == tuple(self.hook.aborted)

    def test_archive_except(self):
        self.scanner = TarDirWalker(self.hook.handler, name_matcher=self.hook.matcher, recurse=self.hook.recurse)

        # Test the StopIteration feature, stopping after recursions:
        self.hook.abort = IOError

        files = sorted(map(str, self.basedir.visit(fil=lambda p: os.path.isfile(p.strpath))))
        logging.info("test_archive_files: Files: {}".format(files))
        fpath = os.path.join(self.basedir.strpath, 'tar-redux.tar')
        with self.assertRaises(self.hook.abort) as raised:
            self.scanner.handle_path(fpath)
        assert str(raised.exception) == 'Giving up on tar-redux.tar:tar-norm.tar:norm/three/file-3.info'
        assert ArchiveRepo.EXPECT_ABORTED[:1] == tuple(self.hook.aborted)
        assert ArchiveRepo.EXPECT_RECURSED[:1] == tuple(self.hook.recursed)

    def callback(self, *params):
        self.callback_args = params
        return self.callback_return

    def test_init(self):
        logging.info("test_init: %s", self.basedir.strpath)
        with self.assertRaises(RuntimeError) as raised:
            scanner = TarDirWalker(file_handler=self.hook.handler,
                                   name_matcher=self.callback,
                                   file_matcher=self.callback)
        assert str(raised.exception).startswith('Do not provide both')

        # Test with name-only matcher:
        self.callback_return = 12345
        scanner = TarDirWalker(self.hook.handler, name_matcher=self.callback)
        assert 12345 == scanner.matcher('foobar', 'blahblah')
        assert self.callback_args == ('foobar',)

        # Test with name-and-info matcher:
        self.callback_return = 54321
        scanner = TarDirWalker(self.hook.handler, file_matcher=self.callback)
        assert 54321 == scanner.matcher('blahblah', 'foobar')
        assert self.callback_args == ('blahblah', 'foobar')

        # Test with no matcher:
        self.callback_return = 'foobar'
        scanner = TarDirWalker(self.hook.handler)
        assert scanner.matcher('blahblah', 'foobar')

    def _validate_results(self):
        expSums = self.archive_repo.sums
        resSums = self.hook.handled
        print(self.hook.handled)
        errors = []
        for key, expected in expSums.items():
            if key not in resSums:
                errors.append("Did not handle {} exp={}".format(key, expected))
            else:
                result = resSums[key]
                archive = (':'.join(key.split(':')[:-1])) if ':' in key else None
                expected += (archive, os.path.basename(key))
                if expected != result:
                    errors.append("For {} exp={} res={}".format(key, expected, result))
                else:
                    print("OKAY {} res={}".format(key, result))

        for key, result in resSums.items():
            if key not in expSums:
                errors.append("Unexpected handle of {} res={}".format(key, result))

        if errors:
            raise Exception("\n" + "\n".join(errors))
