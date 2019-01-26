""" Google Voice interactive CLI app. Invoke with `python -m googlevoice`. """

from __future__ import print_function

import atexit, sys
from optparse import OptionParser
from pprint import pprint
from six.moves import input

from googlevoice.voice import Voice
from googlevoice.util import LoginError

parser = OptionParser(usage='''gvoice [options] commands
    Where commands are

    login (li) - log into the voice service
    logout (lo) - log out of the service and make sure session is deleted
    help

    Voice Commands
        call (c) - call an outgoing number from a forwarding number
        cancel (cc) - cancel a particular call
        download (d) - download mp3 message given id hash
        send_sms (s) - send sms messages

    Folder Views
        search (se)
        inbox (i)
        voicemail (v)
        starred (st)
        all (a)
        spam (sp)
        trash (t)
        voicemail (v)
        sms (sm)
        recorded (r)
        placed (p)
        received (re)
        missed (m)''')
parser.add_option("-e", "--email", dest="email", default=None,
                  help="Google Voice Account Email")
parser.add_option("-p", "--password", dest='passwd', default=None,
                  help='Your account password (prompted if blank)')
parser.add_option(
    "-b", "--batch", dest='batch', default=False, action="store_true",
    help='Batch operations, asking for no interactive input')


YES   = ('', 'y')
TRUTH = (True, 'true')

def login(voice, **kwargs):
    """ Login to a Voice instance, based on options, environment variable
        values, and interactivity
    """
    import os
    
    def environ_override(name, viro=None, fallback=None):
        """ Get a keyword argument, falling back to an environment
            variable value, falling back finally to a provided
            default value.
        """
        if viro is None:
            viro = name
        return kwargs.get(name, None) or \
           os.environ.get(viro, None) or fallback
    
    # Use the local “environ_override(…)” call to get keyword args:
    email  = environ_override('email',  'GOOGLE_VOICE_USER')
    passwd = environ_override('passwd', 'GOOGLE_VOICE_PASS')
    batch  = environ_override('batch',  'GOOGLE_VOICE_BATCH') in TRUTH
    
    print('Logging into voice…')
    if email:
        print('» EMAIL: %s' % email)
    if passwd:
        print('» PASSWD: *********')
    if batch:
        print('» BATCH: %s' % batch)
    
    try:
        voice.login(email=email, passwd=passwd)
    except LoginError:
        if batch:
            # Batch mode exits immediately on failure:
            print('Login failed.')
            return False
        if input('Login failed. Retry? [Y/n] ').lower() in YES:
            # Retrying forces an attempt with environment values:
            return login(voice, email=None,
                                passwd=None,
                                batch=True)
        else:
            return False
    return True


def logout(voice):
    """ Callback delegate function to call `voice.logout()` at the
        program’s end, using `atexit.register`.
    """
    print('Logging out of voice…')
    voice.logout()


def pprint_folder(voice, name):
    """ Use `pprint.pprint` to print out the contents of a folder. """
    folder = getattr(voice, name)()
    print(folder)
    pprint(folder.messages, indent=4)


def main():
    """ The main entry point for the “googlevoice” package CLI app. """
    loggedin = False
    options, args = parser.parse_args()

    try:
        action, args = args[0], args[1:]
    except IndexError:
        action = 'interactive'

    if action == 'help':
        print(parser.usage)
        sys.exit(0)

    # Initialize the application invocations’ Voice instance:
    voice = Voice()
    loggedin = login(voice)
    
    if loggedin:
        atexit.register(logout, voice)
    else:
        print("» Couldn’t get login credentials, exiting…")
        sys.exit(0)

    # The interactive main loop:
    if action == 'interactive':
        while 1:
            try:
                action = input('gvoice> ').lower().strip()
            except (EOFError, KeyboardInterrupt):
                sys.exit(1)
            if not action:
                continue
            elif action in ('q', 'quit', 'exit'):
                break
            elif action in ('login', 'li'):
                loggedin = login(voice)
            elif action in ('logout', 'lo'):
                voice.logout()
            elif action in ('call', 'c'):
                voice.call(
                    input('Outgoing number: '),
                    input('Forwarding number [optional]: ') or None,
                    int(
                        input(
                            'Phone type [1-Home, 2-Mobile, 3-Work, 7-Gizmo]:'
                        ) or 2)
                )
                print('Calling...')
            elif action in ('cancelcall', 'cc'):
                voice.cancel()
            elif action in ('sendsms', 's'):
                voice.send_sms(input('Phone number: '), input('Message: '))
                print('Message Sent')
            elif action in ('search', 'se'):
                se = voice.search(input('Search query: '))
                print(se)
                pprint(se.messages)
            elif action in ('download', 'd'):
                print(
                    'MP3 downloaded to %s'
                    % voice.download(input('Message sha1: ')))
            elif action in ('help', 'h', '?'):
                print(parser.usage)
            elif action in ('trash', 't'):
                pprint_folder(voice, 'trash')
            elif action in ('spam', 'sp'):
                pprint_folder(voice, 'spam')
            elif action in ('inbox', 'i'):
                pprint_folder(voice, 'inbox')
            elif action in ('voicemail', 'v'):
                pprint_folder(voice, 'voicemail')
            elif action in ('all', 'a'):
                pprint_folder(voice, 'all')
            elif action in ('starred', 'st'):
                pprint_folder(voice, 'starred')
            elif action in ('missed', 'm'):
                pprint_folder(voice, 'missed')
            elif action in ('received', 're'):
                pprint_folder(voice, 'received')
            elif action in ('recorded', 'r'):
                pprint_folder(voice, 'recorded')
            elif action in ('sms', 'sm'):
                pprint_folder(voice, 'sms')
    
    # The “send_sms” action logic:
    else:
        if action == 'send_sms':
            try:
                num, args = args[0], args[1:]
            except Exception:
                print('Please provide a message')
                sys.exit(4)
            args = (num, ' '.join(args))
        getattr(voice, action)(*args)

# Call the “main(…)” function:
if __name__ == '__main__':
    main()
