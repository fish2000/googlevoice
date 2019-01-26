# encoding: utf-8
"""
Simple script to startup a python interpreter after
logging into the voice service.

Local variable `voice` is set as the main Voice instance.

Invoke with python -m googlevoice.interact
"""
from __future__ import print_function

import code
import textwrap

from . import Voice

banner = textwrap.dedent("""
    You are now using Google Voice in the interactive python shell
    Try 'help(voice)' for more info
    """).lstrip()

def main():
    voice = Voice()
    voice.login()
    code.interact(banner=banner, local=locals())


if __name__ == '__main__':
    main()
