from __future__ import unicode_literals

import datetime

import click

from ..aliases import Mapping, aliases_database
from ..exceptions import ParseError
from ..settings import Settings
from ..timesheet import Entry
from .base import cli, get_config_file, get_timesheet_collection_for_context, prepare, get_data_dir
from .alias import list_aliases


def complete_alias(ctx, args, incomplete):
    prepare(ctx, get_config_file(), get_data_dir())
    # config = get_config_file()
    # settings = Settings(config)
    # aliases_database.reset()
    # aliases_database.update(settings.get_aliases())
    # populate_aliases(settings.get_aliases())
    aliases_mappings = aliases_database.filter_from_alias(incomplete, backend=None)
    aliases = []
    for alias, m in aliases_mappings.items():
        activity = None
        if m.mapping is not None:
            project, activity = ctx.obj['projects_db'].mapping_to_project(m)
        else:
            project = None
        aliases.append((alias, activity, project, m))
    
    return [
        (alias, project.name if project else '')
        for alias, activity, project, mapping in aliases
    ]


@cli.command(short_help="Add entry with the current time to the entries file.")
@click.argument('alias', autocompletion=complete_alias)
@click.argument('description', nargs=-1)
@click.option('-f', '--file', 'f', type=click.Path(dir_okay=False),
              help="Path to the entries file to use.")
@click.pass_context
def start(ctx, alias, description, f):
    """
    Use it when you start working on the given activity. This will add the
    activity and the current time to your entries file. When you're finished,
    use the stop command.
    """
    today = datetime.date.today()

    try:
        timesheet_collection = get_timesheet_collection_for_context(ctx, f)
    except ParseError as e:
        ctx.obj['view'].err(e)
        return

    t = timesheet_collection.latest()

    # If there's a previous entry on the same date, check if we can use its
    # end time as a start time for the newly started entry
    today_entries = t.entries.filter(date=today)
    if(today in today_entries and today_entries[today]
            and isinstance(today_entries[today][-1].duration, tuple)
            and today_entries[today][-1].duration[1] is not None):
        new_entry_start_time = today_entries[today][-1].duration[1]
    else:
        new_entry_start_time = datetime.datetime.now()

    description = ' '.join(description) if description else '?'
    duration = (new_entry_start_time, None)

    e = Entry(alias, duration, description)
    t.entries[today].append(e)
    t.save()
