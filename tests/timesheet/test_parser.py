from __future__ import unicode_literals

import datetime
import pytest

from taxi.timesheet.parser import (
    DateLine, EntryLine, ParseError, TextLine, TimesheetParser
)


def test_extract_date_dot_separator():
    assert TimesheetParser.extract_date('1.1.2010') == datetime.date(2010, 1, 1)


def test_extract_date_slash_separator():
    assert TimesheetParser.extract_date('05/08/2012') == datetime.date(2012, 8, 5)


def test_extract_date_short_year():
    assert TimesheetParser.extract_date('05/08/12') == datetime.date(2012, 8, 5)


def test_extract_date_yyyy_mm_dd():
    assert TimesheetParser.extract_date('2013/08/09') == datetime.date(2013, 8, 9)


def test_extract_date_invalid_string():
    with pytest.raises(ValueError):
        assert TimesheetParser.extract_date('foobar')


def test_extract_date_incomplete_date():
    with pytest.raises(ValueError):
        assert TimesheetParser.extract_date('05/08')


def test_extract_date_missing_separator():
    with pytest.raises(ValueError):
        assert TimesheetParser.extract_date('05.082012')


def test_extract_date_missing_all_separators():
    with pytest.raises(ValueError):
        assert TimesheetParser.extract_date('05082012')


def test_extract_date_yyyy_mm_dd_missing_separator():
    with pytest.raises(ValueError):
        assert TimesheetParser.extract_date('2012/0801')


def test_parse_time_valid_decimal():
    assert TimesheetParser.parse_duration('1.75') == 1.75


def test_parse_time_valid_integer():
    assert TimesheetParser.parse_duration('3') == 3.0


def test_parse_time_valid_big_integer():
    assert TimesheetParser.parse_time('0900') == datetime.time(9, 0)


def test_parse_time_invalid_string():
    with pytest.raises(ValueError):
        TimesheetParser.parse_time('foo')


def test_parse_time_hours_out_of_range():
    with pytest.raises(ValueError):
        TimesheetParser.parse_time('-2500')


def test_parse_time_minutes_out_of_range():
    with pytest.raises(ValueError):
        TimesheetParser.parse_time('-1061')


def test_parse_time_separator_without_timespan():
    with pytest.raises(ValueError):
        TimesheetParser.parse_time('-')


def test_alias_before_date():
    content = """my_alias_1 1 foo bar
11.10.2013
my_alias 2 foo"""

    with pytest.raises(ParseError):
        TimesheetParser.parse(content)

    content = """# comment
11.10.2013
my_alias 2 foo"""

    lines = TimesheetParser.parse(content)
    assert len(lines) == 3


def test_invalid_date():
    with pytest.raises(ParseError):
        TimesheetParser.parse("1110.2013")
        TimesheetParser.parse("11102013")


def test_invalid_line():
    content = """10.01.2013
foobar 0900-1000 baz
foo"""
    with pytest.raises(ParseError):
        TimesheetParser.parse(content)


def test_parsing():
    contents = """01.01.13

foobar 0900-1000 baz
# comment
foo -1100 bar

2013/09/23
bar 10:00-? ?
? foo 2 foobar"""

    lines = TimesheetParser.parse(contents)

    assert len(lines) == 9
    assert isinstance(lines[0], DateLine)
    assert lines[0].date == datetime.date(2013, 1, 1)
    assert isinstance(lines[1], TextLine)
    assert lines[1].text == ''
    assert isinstance(lines[2], EntryLine)
    assert lines[2].alias == 'foobar'
    assert lines[2].duration == (datetime.time(9, 0), datetime.time(10, 0))
    assert lines[2].description == 'baz'
    assert isinstance(lines[3], TextLine)
    assert lines[3].text == '# comment'
    assert lines[4].alias == 'foo'
    assert lines[4].duration == (None, datetime.time(11, 0))
    assert lines[4].description == 'bar'
    assert isinstance(lines[6], DateLine)
    assert lines[6].date == datetime.date(2013, 9, 23)
    assert isinstance(lines[7], EntryLine)
    assert lines[7].duration == (datetime.time(10, 0), None)
    assert isinstance(lines[8], EntryLine)
    assert lines[8].alias == 'foo'
    assert lines[8].ignored


def test_empty():
    assert len(TimesheetParser.parse('')) == 0


def test_stripping_empty():
    lines = TimesheetParser.parse("""

""")
    assert len(lines) == 0


def test_stripping_not_empty():
    lines = TimesheetParser.parse("""

10.01.2013

foobar 0900-1000 baz

""")
    assert len(lines) == 3


def test_detect_formatting_no_alias_padding():
    line = EntryLine(
        'foobar', 4, 'description',
    )
    assert line.text == 'foobar 4 description'


def test_detect_formatting_padded_alias():
    line = EntryLine(
        'foobar', 4, 'description',
        text=('', '', 'foobar', '   ', '4', ' ', 'description')
    )
    assert line.text == 'foobar   4 description'


def test_detect_formatting_no_time_padding():
    line = EntryLine(
        'foobar', (datetime.time(15, 0), datetime.time(16, 0)), 'description',
        text=('', '', 'foobar', ' ', '1500-1600', ' ', 'description')
    )
    assert line.text == 'foobar 1500-1600 description'


def test_detect_formatting_padded_time():
    line = EntryLine(
        'foobar', (datetime.time(15, 0), datetime.time(16, 0)), 'description',
        text=('', '', 'foobar', ' ', '1500-1600', '   ', 'description')
    )
    assert line.text == 'foobar 1500-1600   description'


def test_detect_formatting_padded_time_and_alias():
    line = EntryLine(
        'foobar', (datetime.time(15, 0), datetime.time(16, 0)), 'description',
        text=('', '', 'foobar', '   ', '1500-1600', '   ', 'description')
    )
    line.duration = (datetime.time(14, 0), datetime.time(15, 0))
    assert line.text == 'foobar   14:00-15:00 description'


def test_parse_error_contains_line_number():
    try:
        TimesheetParser.parse("hello world")
    except ParseError as e:
        assert e.line_number == 1


def test_parse_time_valid_timespan():
    t = TimesheetParser.parse_entry_line('foo 0900-1015 Description')
    assert t.duration == (datetime.time(9, 0), datetime.time(10, 15))


def test_parse_time_valid_timespan_with_separators():
    t = TimesheetParser.parse_entry_line('foo 09:00-10:15 Description')
    assert t.duration == (datetime.time(9, 0), datetime.time(10, 15))


def test_parse_time_valid_timespan_without_end():
    t = TimesheetParser.parse_entry_line('foo 09:00-? Description')
    assert t.duration == (datetime.time(9, 0), None)


def test_parse_time_valid_timespan_without_start():
    t = TimesheetParser.parse_entry_line('foo -10:15 Description')
    assert t.duration == (None, datetime.time(10, 15))
