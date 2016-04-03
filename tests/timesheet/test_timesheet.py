# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import pytest

from freezegun import freeze_time

from taxi.aliases import aliases_database, Mapping
from taxi.timesheet import Timesheet
from taxi.timesheet.entry import (
    EntriesCollection, TimesheetEntry, UnknownDirectionError
)
from taxi.timesheet.utils import get_files


def _create_timesheet(text, add_date_to_bottom=False):
    aliases_database.update({
        'foo': Mapping(mapping=(123, 456), backend='test'),
        'bar': Mapping(mapping=(12, 34), backend='test'),
    })
    entries = EntriesCollection(text)
    entries.add_date_to_bottom = add_date_to_bottom

    return Timesheet(entries)


def test_empty_timesheet_has_zero_entries():
    t = _create_timesheet('')
    assert len(t.entries) == 0


def test_entry_with_question_mark_description_is_ignored():
    t = _create_timesheet('10.10.2012\nfoo 2 ?')
    assert list(t.entries.values())[0][0].is_ignored()


def test_entry_alias_is_extracted():
    contents = """10.10.2012
foo 09:00-10:00 baz"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].alias == 'foo'


def test_entry_description_is_extracted():
    contents = """10.10.2012
foo 09:00-10:00 baz"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].description == 'baz'


def test_entry_start_and_end_time_are_extracted():
    contents = """10.10.2012
foo 09:00-10:00 baz"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].duration == (datetime.time(9), datetime.time(10))


def test_entry_duration_is_extracted():
    contents = """10.10.2012
foo 1.25 baz"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].duration == 1.25


def test_entry_duration_looking_like_start_time_is_extracted():
    contents = """10.10.2012
foo 100 baz"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].duration == 100


def test_to_lines_returns_all_lines():
    contents = """10.10.2012
foo 09:00-10:00 baz
bar      -11:00 foobar"""

    t = _create_timesheet(contents, True)
    lines = t.entries.to_lines()
    assert lines == ['10.10.2012', 'foo 09:00-10:00 baz',
                     'bar      -11:00 foobar']


def test_to_lines_returns_appended_lines():
    contents = """10.10.2012
foo 09:00-10:00 baz
bar      -11:00 foobar"""

    t = _create_timesheet(contents, True)
    t.entries[datetime.date(2012, 9, 29)].append(
        TimesheetEntry('foo', (datetime.time(15, 0), None), 'bar')
    )
    lines = t.entries.to_lines()
    assert lines == ['10.10.2012', 'foo 09:00-10:00 baz',
                     'bar      -11:00 foobar', '', '29.09.2012', '',
                     'foo 15:00-? bar']


def test_entry_with_undefined_alias_can_be_added():
    contents = """10.10.2012
foo 0900-1000 baz"""

    t = _create_timesheet(contents)
    e = TimesheetEntry('baz', (datetime.time(10, 0), None), 'baz')
    t.entries[datetime.date(2012, 10, 10)].append(e)

    lines = t.entries.to_lines()
    assert lines == [
        '10.10.2012', 'foo 0900-1000 baz', 'baz 10:00-? baz'
    ]


def test_entry_without_start_time_is_set_previous_start_time():
    contents = """10.10.2012
foo 0900-1000 baz
bar     -1100 bar"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][1].duration == (None, datetime.time(11, 0))


def test_entry_without_start_time_after_entry_without_start_time_has_start_time_set():
    contents = """10.10.2012
foo 0900-1000 baz
bar     -1100 bar
foo     -1300 bar"""

    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][2].duration == (None, datetime.time(13, 0))


def test_entry_without_start_time_following_duration_is_ignored():
    contents = """10.10.2012
foo 0900-1000 baz
bar 2 bar
foo     -1200 bar"""
    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][2].is_ignored()


def test_entry_without_start_time_without_previous_entry_is_ignored():
    contents = """10.10.2012
foo -1000 baz"""
    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].is_ignored()


def test_entry_without_start_time_after_previous_entry_without_end_time_is_ignored():
    contents = """10.10.2012
foo 0900-1000 baz
bar 1000-? bar
foo     -1200 bar"""
    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][2].is_ignored()


def test_entry_without_end_time_is_ignored():
    contents = "10.10.2012\nfoo 1400-? Foo"
    t = _create_timesheet(contents)
    assert list(t.entries.values())[0][0].is_ignored()


def test_get_entries_excluding_unmapped_excludes_unmapped():
    contents = "10.10.2012\nbaz 2 Foo"
    t = _create_timesheet(contents)
    assert len(list(t.get_entries(exclude_unmapped=True).values())[0]) == 0


def test_get_entries_excluding_unmapped_includes_mapped():
    contents = "10.10.2012\nfoo 2 Foo"
    t = _create_timesheet(contents)
    assert len(list(t.get_entries(exclude_unmapped=True).values())[0]) == 1


def test_get_entries_excluding_ignored_excludes_ignored():
    contents = "10.10.2012\n? foo 2 Foo"
    t = _create_timesheet(contents)
    assert len(list(t.get_entries(exclude_ignored=True).values())[0]) == 0


def test_get_entries_excluding_ignored_includes_non_ignored():
    contents = "10.10.2012\nfoo 2 Foo"
    t = _create_timesheet(contents)
    assert len(list(t.get_entries(exclude_ignored=True).values())[0]) == 1


def test_entry_with_zero_duration_is_ignored():
    contents = "10.10.2012\nfoo 0 Foo"
    t = _create_timesheet(contents)
    assert list(t.get_entries().values())[0][0].is_ignored()


def test_is_top_down_with_single_date_raises_exception():
    contents = """31.03.2013
foo 2 bar
bar 0900-1000 bar"""

    t = _create_timesheet(contents)
    with pytest.raises(UnknownDirectionError):
        t.entries.is_top_down()


def test_is_top_down_returns_true_for_top_down_dates():
    contents = """31.03.2013
foo 2 bar
bar 0900-1000 bar
01.04.2013
foo 1 bar"""

    t = _create_timesheet(contents)
    assert t.entries.is_top_down()


def test_is_top_down_returns_false_for_down_top_dates():
    contents = """01.04.2013
foo 2 bar
bar 0900-1000 bar
31.03.2013
foo 1 bar"""

    t = _create_timesheet(contents)
    assert not t.entries.is_top_down()


def test_is_top_down_returns_false_for_down_top_dates_without_entries():
    contents = """01.04.2013
31.03.2013"""

    t = _create_timesheet(contents)
    assert not t.entries.is_top_down()


def test_to_lines_reports_push_flag():
    contents = """01.04.2013
foo 2 bar
bar 0900-1000 bar
31.03.2013
foo 1 bar"""

    t = _create_timesheet(contents)
    entries = t.get_entries(datetime.date(2013, 4, 1))

    for entry in list(entries.values())[0]:
        entry.pushed = True

    assert t.entries.to_lines() == [
        "01.04.2013", "= foo 2 bar", "= bar 0900-1000 bar", "31.03.2013",
        "foo 1 bar"
    ]


def test_add_date_with_add_date_to_bottom_adds_date_to_bottom():
    t = _create_timesheet('', add_date_to_bottom=True)
    t.entries[datetime.date(2013, 1, 1)] = []
    t.entries[datetime.date(2013, 1, 2)] = []

    assert t.entries.to_lines() == ["01.01.2013", "", "02.01.2013"]


def test_add_date_without_add_date_to_bottom_adds_date_to_top():
    t = _create_timesheet('', add_date_to_bottom=False)
    t.entries[datetime.date(2013, 1, 1)] = []
    t.entries[datetime.date(2013, 1, 2)] = []

    assert t.entries.to_lines() == ["02.01.2013", "", "01.01.2013"]


def test_regroup_doesnt_regroup_entries_with_different_alias():
    contents = """01.04.2013
foo 2 bar
bar 2 bar"""

    t = _create_timesheet(contents)
    entries = list(t.get_entries(regroup=True).values())[0]
    assert len(entries) == 2


def test_regroup_doesnt_regroup_entries_with_different_description():
    contents = """01.04.2013
foo 2 bar
foo 2 baz"""

    t = _create_timesheet(contents)
    entries = list(t.get_entries(regroup=True).values())[0]
    assert len(entries) == 2


def test_regroup_regroups_entries_with_same_alias_and_description():
    contents = """01.04.2013
foo 2 bar
foo 3 bar
bar 1 barz"""

    t = _create_timesheet(contents)
    entries = list(t.get_entries(regroup=True).values())[0]
    assert len(entries) == 2


def test_regroup_adds_time():
    contents = """01.04.2013
foo 2 bar
foo 3 bar"""

    t = _create_timesheet(contents)
    entries = list(t.get_entries(regroup=True).values())[0]
    assert entries[0].duration == 5


def test_regroup_adds_time_with_start_and_end_time():
    contents = """01.04.2013
foo 2 bar
foo 0900-1000 bar"""

    t = _create_timesheet(contents)
    entries = list(t.get_entries(regroup=True).values())[0]
    assert entries[0].duration == 3


def test_regroup_doesnt_regroup_ignored_entries_with_non_ignored_entries():
    contents = """01.04.2013
foo 2 bar
? foo 3 test"""

    t = _create_timesheet(contents)
    entries = list(t.get_entries(regroup=True).values())[0]
    assert len(entries) == 2


def test_regroup_regroups_entries_with_partial_time():
    contents = """01.04.2013
foo 2 bar
foo 0800-0900 bar
bar -1000 bar
foo -1100 bar"""
    t = _create_timesheet(contents)
    entries = t.get_entries(regroup=True)[datetime.date(2013, 4, 1)]
    assert len(entries) == 2
    assert entries[0].hours == 4


def test_set_pushed_flag_on_regrouped_entry_sets_flag_on_associated_entries():
    contents = """01.04.2013
foo 2 bar
bar 0900-1000 bar
foo 1 bar"""
    t = _create_timesheet(contents)
    entries = t.get_entries(regroup=True)[datetime.date(2013, 4, 1)]
    for entry in entries:
        entry.pushed = True
    lines = t.entries.to_lines()
    assert lines == ["01.04.2013", "= foo 2 bar", "= bar 0900-1000 bar",
                     "= foo 1 bar"]


def test_empty_timesheet():
    timesheet = Timesheet()
    assert len(timesheet.entries) == 0


def test_timesheet_with_entries():
    entries = EntriesCollection("""10.10.2014\nfoo 2 bar\n11.10.2014\nfoo 1 bar""")

    timesheet = Timesheet(entries)
    assert len(timesheet.entries) == 2


def test_get_entries():
    entries = EntriesCollection("""10.10.2014\nfoo 2 bar\n11.10.2014\nfoo 1 bar""")

    timesheet = Timesheet(entries)
    assert len(timesheet.get_entries(datetime.date(2014, 10, 10))) == 1


@freeze_time('2014-01-02')
def test_current_workday_entries():
    entries = EntriesCollection("""01.01.2014\nfoo 2 bar""")

    timesheet = Timesheet(entries)
    assert len(timesheet.get_non_current_workday_entries()) == 0


@freeze_time('2014-01-03')
def test_non_current_workday_entries():
    entries = EntriesCollection("""01.01.2014\nfoo 2 bar""")

    timesheet = Timesheet(entries)
    assert len(timesheet.get_non_current_workday_entries()) == 1


def test_non_current_workday_entries_ignored():
    entries = EntriesCollection("""04.01.2014\n? foo 2 bar""")

    timesheet = Timesheet(entries)
    assert len(timesheet.get_non_current_workday_entries()) == 0


def test_get_files_m_returns_previous_files():
    f = get_files('foo_%m', 2, datetime.date(2014, 3, 1))
    assert f == ['foo_03', 'foo_02', 'foo_01']


def test_get_files_m_spans_over_previous_year():
    f = get_files('foo_%m', 2, datetime.date(2014, 2, 1))
    assert f == ['foo_02', 'foo_01', 'foo_12']


def test_get_files_m_spans_over_previous_year_and_changes_year():
    f = get_files('foo_%m_%Y', 2, datetime.date(2014, 2, 1))
    assert f == ['foo_02_2014', 'foo_01_2014', 'foo_12_2013']


def test_get_files_Y_returns_previous_files():
    f = get_files('foo_%Y', 2, datetime.date(2014, 2, 1))
    assert f == ['foo_2014', 'foo_2013', 'foo_2012']


def test_get_entries_excluding_pushed_excludes_pushed():
    contents = """01.04.2013
foo 2 bar
= bar 0900-1000 bar
foo 1 bar"""
    entries = EntriesCollection(contents)
    timesheet = Timesheet(entries)
    timesheet_entries = timesheet.get_entries(exclude_pushed=True)

    assert len(list(timesheet_entries.values())[0]) == 2
