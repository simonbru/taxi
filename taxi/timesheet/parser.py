from __future__ import unicode_literals

import copy
import datetime
import re

import six

from .flags import FlaggableMixin
from ..exceptions import TaxiException
from ..utils import date as date_utils


@six.python_2_unicode_compatible
class TextLine(object):
    """
    The TextLine is either a blank line or a comment line.
    """
    def __init__(self, text):
        self._text = text
        super(TextLine, self).__init__()

    def __str__(self):
        return self.text

    def __repr__(self):
        return '"%s"' % str(self.text)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value


class EntryLine(TextLine, FlaggableMixin):
    """
    The EntryLine is a line representing a timesheet entry, with an alias, a
    duration and a description.
    """
    FLAGS_REPR = {
        FlaggableMixin.FLAG_IGNORED: '?',
        FlaggableMixin.FLAG_PUSHED: '=',
    }

    ATTRS_POSITION = {
        0: 'flags',
        2: 'alias',
        4: 'duration',
        6: 'description',
    }

    ATTRS_TRANSFORMERS = {
        'flags': 'flags_as_text',
        'duration': 'duration_as_text',
    }

    DURATION_FORMAT = '%H:%M'

    def __init__(self, alias, duration, description, flags=None, text=None):
        super(EntryLine, self).__init__(text=text)

        self.alias = alias
        self.duration = duration
        self.description = description
        if flags is not None:
            self._flags = copy.copy(flags)
        self._changed_attrs = set()

        if text:
            self._text = text
        else:
            self._text = (
                self.flags_as_text, ' ' if self.flags_as_text else '',
                self.alias, ' ', self.duration_as_text, ' ', self.description
            )

    def __setattr__(self, attr, value):
        if hasattr(self, '_changed_attrs'):
            if attr in self.ATTRS_POSITION.values():
                self._changed_attrs.add(attr)

        super(EntryLine, self).__setattr__(attr, value)

    def add_flag(self, flag):
        super(EntryLine, self).add_flag(flag)
        self._changed_attrs.add('flags')

    def remove_flag(self, flag):
        super(EntryLine, self).remove_flag(flag)
        self._changed_attrs.add('flags')

    @property
    def text(self):
        line = []

        for i, text in enumerate(self._text):
            if i in self.ATTRS_POSITION:
                if self.ATTRS_POSITION[i] in self._changed_attrs:
                    attr_name = self.ATTRS_POSITION[i]

                    if attr_name in self.ATTRS_TRANSFORMERS:
                        attr_value = getattr(self, self.ATTRS_TRANSFORMERS[attr_name])
                    else:
                        attr_value = getattr(self, self.ATTRS_POSITION[i])
                else:
                    attr_value = text

                line.append(attr_value)
            else:
                if i == 1:
                    text = '' if not self._flags else ' '
                elif i > 0:
                    if len(line[i-1]) != len(self._text[i-1]):
                        text = ' ' * max(1, (len(text) - (len(line[i-1]) - len(self._text[i-1]))))

                line.append(text)

        return ''.join(line)

    @property
    def flags_as_text(self):
        if self._flags:
            text = ''.join([self.FLAGS_REPR[flag] for flag in self._flags])
        else:
            text = ''

        return text

    @property
    def duration_as_text(self):
        if isinstance(self.duration, tuple):
            start = (self.duration[0].strftime(self.DURATION_FORMAT)
                     if self.duration[0] is not None
                     else '')

            end = (self.duration[1].strftime(self.DURATION_FORMAT)
                   if self.duration[1] is not None
                   else '?')

            duration = '%s-%s' % (start, end)
        else:
            duration = six.text_type(self.duration)

        return duration


class DateLine(TextLine):
    def __init__(self, date, text=None, date_format='%d.%m.%Y'):
        self.date = date

        if text is not None:
            self.text = text
        else:
            self.text = date_utils.unicode_strftime(self.date, date_format)


class TimesheetParser(object):
    """
    Parse a string and transform it into a list of parsed lines (date line,
    entry line, text line). The basic structure is as follows:

    Date line: <date>, where `date` is formatted as dd.mm.yyyy (the `.`
    separator can be replaced by any non-word character)
    Entry line: <alias> <duration> <description>, where `duration` can either
    be expressed as a float/int to mean hours or as a time range (eg.
    `09:00-09:30`, the `:` separator being optional)
    Comment line: any line starting with `#` will be ignored

    For the parsed string to be a valid timesheet, any entry line needs to
    be preceded by at least a date line.
    """
    entry_match_re = re.compile(
        r"^(?:(?P<flags>.+?)(?P<spacing1>\s+))?"
        r"(?P<alias>[?\w_-]+)(?P<spacing2>\s+)"
        r"(?P<time>(?:(?P<start_time>(?:\d{1,2}):?(?:\d{1,2}))?-(?P<end_time>(?:(?:\d{1,2}):?(?:\d{1,2}))|\?))|(?P<duration>\d+(?:\.\d+)?))(?P<spacing3>\s+)"
        r"(?P<description>.+)$"
    )
    date_match_re = re.compile(r'(\d{1,2})\D(\d{1,2})\D(\d{4}|\d{2})')
    us_date_match_re = re.compile(r'(\d{4})\D(\d{1,2})\D(\d{1,2})')

    @classmethod
    def parse(cls, text):
        text = text.strip()
        lines_parser = cls.parser(text.splitlines())

        return [line for line in lines_parser]

    @classmethod
    def parser(cls, lines):
        current_date = None

        for (lineno, line) in enumerate(lines, 1):
            line = line.strip()
            line = line.replace('\t', ' ' * 4)

            try:
                if len(line) == 0 or line.startswith('#'):
                    yield TextLine(line)
                else:
                    try:
                        date = cls.extract_date(line)
                    except ValueError:
                        if current_date is None:
                            raise ParseError("Entries must be defined inside a"
                                             " date section")

                        yield cls.parse_entry_line(line)
                    else:
                        current_date = date
                        yield DateLine(date, line)
            except ParseError as e:
                e.line_number = lineno
                e.line = line
                raise

    @classmethod
    def parse_entry_line(cls, line):
        """
        Try to parse the given text line and extract and entry. Return an
        :class:`EntryLine` object if parsing is successful, otherwise raise
        :class:`ParseError`.
        """
        split_line = re.match(cls.entry_match_re, line)

        if not split_line:
            raise ParseError(
                "Line must have an alias, a duration and a description"
            )

        alias = split_line.group('alias').replace('?', '')
        start_time = end_time = None

        if split_line.group('start_time') is not None:
            if split_line.group('start_time'):
                try:
                    start_time = cls.parse_time(split_line.group('start_time'))
                except ValueError:
                    raise ParseError(
                        "Duration must be in format hh:mm or hhmm"
                    )
            else:
                start_time = None

        if split_line.group('end_time') is not None:
            if split_line.group('end_time') == '?':
                end_time = None
            else:
                end_time = cls.parse_time(split_line.group('end_time'))

        if start_time or end_time:
            duration = (start_time, end_time)

        if split_line.group('duration') is not None:
            duration = float(split_line.group('duration'))

        description = split_line.group('description')

        # TODO
        flags = set()
        if split_line.group('flags') and '?' in split_line.group('flags'):
            flags.add(EntryLine.FLAG_IGNORED)
        if split_line.group('flags') and '=' in split_line.group('flags'):
            flags.add(EntryLine.FLAG_PUSHED)

        line = (
            split_line.group('flags') or '',
            split_line.group('spacing1') or '',
            split_line.group('alias'),
            split_line.group('spacing2'),
            split_line.group('time'),
            split_line.group('spacing3'),
            split_line.group('description'),
        )

        entry_line = EntryLine(alias, duration, description, flags=flags,
                               text=line)

        return entry_line

    @classmethod
    def parse_duration(cls, str_duration):
        return float(str_duration)

    @classmethod
    def parse_time(cls, str_time):
        """
        Parse a time in the form hh:mm or hhmm (or even hmm) and return a
        datetime.time object.
        """
        str_time = str_time.replace(':', '')

        if not re.match('^\d{3,}$', str_time):
            raise ValueError("Time must be numeric")

        minutes = int(str_time[-2:])
        hours = int(str_time[0:2] if len(str_time) > 3 else str_time[0])

        return datetime.time(hours, minutes)

    @classmethod
    def extract_date(cls, line):
        # Try to match dd/mm/yyyy format
        date_matches = re.match(cls.date_match_re, line)

        # If no match, try with yyyy/mm/dd format
        if date_matches is None:
            date_matches = re.match(cls.us_date_match_re, line)

        if date_matches is None:
            raise ValueError("No date could be extracted from the given value")

        # yyyy/mm/dd
        if len(date_matches.group(1)) == 4:
            return datetime.date(int(date_matches.group(1)),
                                 int(date_matches.group(2)),
                                 int(date_matches.group(3)))

        # dd/mm/yy
        if len(date_matches.group(3)) == 2:
            current_year = datetime.date.today().year
            current_millennium = current_year - (current_year % 1000)
            year = current_millennium + int(date_matches.group(3))
        # dd/mm/yyyy
        else:
            year = int(date_matches.group(3))

        return datetime.date(year, int(date_matches.group(2)),
                             int(date_matches.group(1)))


@six.python_2_unicode_compatible
class ParseError(TaxiException):
    def __init__(self, message, line=None, line_number=None):
        self.line = line
        self.message = message
        self.line_number = line_number
        self.file = None

    def __str__(self):
        if self.line_number is not None and self.file:
            msg = "Parse error in {file} at line {line}: {msg}.".format(
                file=self.file,
                line=self.line_number,
                msg=self.message
            )
        elif self.line_number is not None:
            msg = "Parse error at line {line}: {msg}.".format(
                line=self.line_number,
                msg=self.message
            )
        else:
            msg = self.message

        if self.line:
            msg += " The line causing the error was:\n\n%s" % self.line

        return msg
