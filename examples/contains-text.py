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
