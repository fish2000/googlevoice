# encoding: utf-8
from __future__ import print_function

import json
from datetime import datetime
from time import gmtime
from xml.parsers.expat import ParserCreate


def validate_response(response):
    """ Validates that a given JSON response is A-OK. """
    try:
        assert 'ok' in response and response['ok']
    except AssertionError as exc:
        raise ValidationError('There was a problem with GV: %s (%s)' % (response,
                                                                        str(exc)))


def load_and_validate(response):
    """ Loads JSON data from an HTTP response, then validates it. """
    validate_response(response.json())


class ValidationError(Exception):
    """ Bombs when response code coming back from Voice is in the 500s. """
    pass


class LoginError(Exception):
    """ Occurs when login credentials are incorrect. """
    pass


class ParsingError(Exception):
    """ Happens when XML feed parsing fails. """
    pass


class JSONError(Exception):
    """ The product of a failed JSON deserialization. """
    pass


class DownloadError(Exception):
    """ The result of a message that could not be downloaded – probably not
        in either “voicemail” or “recorded”.
    """
    pass


class ForwardingError(Exception):
    """ The forwarding number provided was incorrect. """
    pass


class AttrDict(dict):
    """ A dict whose values can be conveninently accessed through dot.notation """
    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        return None


class Phone(AttrDict):
    
    """ Wrapper for phone objects, used to furnish phone-specific API-backed
        endpoint method calls.
        
        Attributes are:
        
        * id: `int`
        * phoneNumber: `i18n` phone number
        * formattedNumber: humanized phone number `str`
        * we: data `dict`
        * wd: data `dict`
        * verified: `bool`
        * name: `str` label
        * smsEnabled: `bool`
        * scheduleSet: `bool`
        * policyBitmask: `int`
        * weekdayTimes: `list`
        * dEPRECATEDDisabled: `bool`
        * weekdayAllDay: `bool`
        * telephonyVerified
        * weekendTimes: `list`
        * active: `bool`
        * weekendAllDay: `bool`
        * enabledForOthers: `bool`
        * type: enumeration `int`:
          » 1 - Home,
            2 - Mobile,
            3 - Work,
            4 - Gizmo
    """
    
    def __init__(self, voice, data):
        self.voice = voice
        super(Phone, self).__init__(data)

    def enable(self):
        """ Enables this Phone instance for usage. """
        return self.__call_forwarding()

    def disable(self):
        """ Disables this Phone instance. """
        return self.__call_forwarding('0')

    def __call_forwarding(self, enabled='1'):
        """ Enables or disables this Phone instance. """
        self.voice.__validate_special_page('default_forward', {
            'enabled': enabled,
            'phoneId': self.id
        })

    def __str__(self):
        return self.phoneNumber

    def __repr__(self):
        return '<Phone %s>' % self.phoneNumber


class Message(AttrDict):
    
    """ Wrapper for all call and SMS message data stored in Google Voice.
        
        Attributes are:
        
        * id: SHA1 identifier
        * isTrash: `bool`
        * displayStartDateTime: `datetime`
        * star: `bool`
        * isSpam: `bool`
        * startTime: `gmtime`
        * labels: `list`
        * displayStartTime: `time`
        * children: `str`
        * note: `str`
        * isRead: `bool`
        * displayNumber: `str`
        * relativeStartTime: `str`
        * phoneNumber: `str`
        * type: `int`
    """
    
    def __init__(self, folder, id, data):
        self.folder = folder
        self.id = id
        super(AttrDict, self).__init__(data)
        self['startTime'] = gmtime(int(self['startTime']) / 1000)
        self['displayStartDateTime'] = datetime.strptime(self['displayStartDateTime'],
                                                              '%m/%d/%y %I:%M %p')
        self['displayStartTime'] = self['displayStartDateTime'].time()

    def delete(self, trash=1):
        """ Moves this message to the Trash. Use ``message.delete(0)``
            to move it back out of the Trash.
        """
        self.folder.voice.__messages_post('delete', self.id, trash=trash)

    def star(self, star=1):
        """ Star this message. Use ``message.star(0)`` to unstar it. """
        self.folder.voice.__messages_post('star', self.id, star=star)

    def mark(self, read=1):
        """ Mark this message as read. Use ``message.mark(0)`` to
            subsequently mark it as unread.
        """
        self.folder.voice.__messages_post('mark', self.id, read=read)

    def download(self, adir=None):
        """ Download the message as an MP3 file, if such data exists.
            
            Saves downloaded files to ``adir``, which defaults to the
            current directory.
            Message hashes can then be found in and accessed through
            e.g. ``self.voicemail().messages``.
            
            Returns the location of the saved file.
        """
        return self.folder.voice.download(self, adir)

    def __str__(self):
        return self.id

    def __repr__(self):
        return '<Message #%s (%s)>' % (self.id, self.phoneNumber)


class Folder(AttrDict):
    
    """ Folder wrapper for “feeds” of object data from Google Voice.
        
        Attributes are:
        
        * totalSize: `int` (aka ``__len__``)
        * unreadCounts: `dict`
        * resultsPerPage: `int`
        * messages: `list` of `Message` instances
    """
    
    def __init__(self, voice, name, data):
        self.voice = voice
        self.name = name
        super(AttrDict, self).__init__(data)

    @property
    def messages(self):
        """ Returns a list of all messages contained in this folder. """
        return [Message(self, *i) for i in self['messages'].items()]

    def __len__(self):
        return self['totalSize']

    def __repr__(self):
        return '<Folder %s (%s)>' % (self.name, len(self))


class XMLParser(object):
    """ `XMLParser` is a helper class that can dig both json and html
        out of Google feed responses.
        
        The parser takes a ``Voice`` instance, a page name, and a
        callback function from which to grab its data. All `XMLParser`
        instances are callable – calling the parser instance calls its
        data function callback once, sets up the ``json`` and ``html``
        attributes, and returns a ``Folder`` instance for the given page:
        
            >>> o = XMLParser(voice, 'voicemail', lambda: 'some html payload')
            >>> f = o()
            >>> f
            <Folder ...>
            >>> o.json
            'some json payload'
            >>> o.data
            'loaded json payload'
            >>> o.html
            'some html payload'
    """
    # attr = None

    def __init__(self, voice, name, datafunc):
        self.attr = None
        self.json = ''
        self.html = ''
        self.datafunc = datafunc
        self.voice = voice
        self.name = name

    def start_element(self, name, attrs):
        if name in ('json', 'html'):
            self.attr = name

    def end_element(self, name):
        self.attr = None

    def char_data(self, data):
        if self.attr and data:
            setattr(self, self.attr,
            getattr(self, self.attr) + data)

    def __call__(self):
        self.json = ''
        self.html = ''
        datafunc = self.datafunc
        parser = ParserCreate()
        parser.StartElementHandler = self.start_element
        parser.EndElementHandler = self.end_element
        parser.CharacterDataHandler = self.char_data
        
        try:
            data = datafunc()
            parser.Parse(data, 1)
        except Exception as exc:
            raise ParsingError(str(exc))
        
        return self.folder

    @property
    def folder(self):
        """ Returns the associated ``Folder`` instance for the given page
            e.g. (``self.name``).
        """
        return Folder(self.voice,
                      self.name,
                      self.data)

    @property
    def data(self):
        """ Returns the parsed JSON after the XMLParser has been called. """
        try:
            return json.loads(self.json)
        except Exception as exc:
            raise JSONError(str(exc))
