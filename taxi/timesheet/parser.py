from __future__ import unicode_literals

import datetime
import re

import six

from ..exceptions import TaxiException
from ..utils import date as date_utils


@six.python_2_unicode_compatible
class TextLine(object):
    """
    The TextLine is either a blank line or a comment line.
    """
    def __init__(self, text):
        self._text = text

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


class EntryLine(TextLine):
    """
    The EntryLine is a line representing a timesheet entry, with an alias, a
    duration and a description.
    """
    def __init__(self, alias, duration, description, flags=None):
        self._alias = alias
        self.duration = duration
        self.description = description

    # TODO
    def generate_text(self):
        """
        Return a textual representation of the line.

        An effort is made to preserve the original formatting of the line since
        some OCD people like to have perfectly aligned timesheets.
        """
        formatting = self.formatting

        if not formatting:
            formatting = {
                'width': (None, None),
                'time_format': '%H:%M',
                'spacer': (' ', ' ')
            }

        if isinstance(self.duration, tuple):
            start = (self.duration[0].strftime(formatting['time_format'])
                     if self.duration[0] is not None
                     else '')

            end = (self.duration[1].strftime(formatting['time_format'])
                   if self.duration[1] is not None
                   else '?')

            duration = '%s-%s' % (start, end)
        else:
            # Remove '.0' if the number doesn't have a decimal part
            duration = str(self.duration).rstrip('0').rstrip('.')

        commented_prefix = '# ' if self.commented else ''
        alias = '%s?' % self.alias if self.ignored else self.alias

        padding1 = (1 if formatting['width'][0] is None
                    else max(1, formatting['width'][0] - len(alias)))
        padding2 = (1 if formatting['width'][1] is None
                    else max(1, formatting['width'][1] - len(duration)))

        text = ('{commented}{alias}{padding1}{duration}{padding2}'
                '{description}'.format(
                    commented=commented_prefix,
                    alias=alias,
                    padding1=formatting['spacer'][0] * padding1,
                    duration=duration,
                    description=self.description,
                    padding2=formatting['spacer'][1] * padding2))

        return text


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
        r"^(?:(?P<flags>.+?) )?"
        r"(?P<alias>[\w_-]+) "
        r"(?:(?:(?P<start_time>(?:\d{1,2}):?(?:\d{1,2}))?-(?P<end_time>(?:(?:\d{1,2}):?(?:\d{1,2}))|\?))|(?P<duration>\d+(?:\.\d+)?)) "
        r"(?P<description>.+)$"
    )
    date_match_re = re.compile(r'(\d{1,2})\D(\d{1,2})\D(\d{4}|\d{2})')
    us_date_match_re = re.compile(r'(\d{4})\D(\d{1,2})\D(\d{1,2})')
    formatting_match_re = re.compile(r'([^\s]+\s+)([^\s]+\s+)')

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
        split_line = re.match(cls.entry_match_re, line)

        alias = split_line.group('alias').replace('?', '')
        if split_line.group('start_time') is not None:
            if split_line.group('start_time'):
                start_time = cls.parse_time(split_line.group('start_time'))
            else:
                start_time = None

            if split_line.group('end_time') == '?':
                end_time = None
            else:
                end_time = cls.parse_time(split_line.group('end_time'))

            duration = (start_time, end_time)

        if split_line.group('duration') is not None:
            duration = float(split_line.group('duration'))

        description = split_line.group('description')

        flags = set()

        # TODO
        if (split_line.group('alias').endswith('?') or
                (split_line.group('flags') and '?' in split_line.group('flags'))):
            flags.add(1)

        entry_line = EntryLine(alias, duration, description, line, flags)
        #entry_line.formatting = formatting

        return entry_line

    @staticmethod
    def split_line(line):
        split_line = line.split(None, 2)

        if len(split_line) != 3:
            raise ParseError("Couldn't split line into 3 chunks")

        return split_line

    @classmethod
    def detect_formatting(cls, line):
        """
        Extract the width (= number of columns) of the different components of
        the line as well as the time format. The returned data is a dictionary
        with 3 values, 'width' containing a 2-items tuple representing the
        width of the two first components of the line (alias and duration),
        'time_format' containing the format of the time as a string usable by
        strftime and 'spacer' containing a 2-items tuple representing the space
        format used for the two first components (either a space or a
        tabulation)
        """
        components = re.match(cls.formatting_match_re, line)
        split_line = cls.split_line(line)

        if components and len(components.groups()) == 2:
            width = tuple(len(separator) for separator in components.groups())
            spacer = tuple('\t' if separator[-1] == '\t' else ' '
                           for separator in components.groups())
        else:
            return None

        time_format = '%H:%M' if ':' in split_line[1] else '%H%M'

        return {
            'width': width,
            'time_format': time_format,
            'spacer': spacer
        }

    @classmethod
    def parse_time(cls, str_time):
        str_time = re.replace('[^\d]', '')
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
