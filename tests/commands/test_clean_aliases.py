from freezegun import freeze_time

from taxi.projects import Activity, Project, ProjectsDb
from taxi.settings import Settings

from . import CommandTestCase


class CleanAliasesCommandTestCase(CommandTestCase):
    @freeze_time('2014-01-21')
    def test_project_status(self):
        config = self.default_config.copy()
        options = self.default_options.copy()

        config['dummy_aliases'] = {
            'alias_not_started': '0/0',
            'alias_active': '1/0',
            'alias_finished': '2/0',
            'alias_cancelled': '3/0',
        }

        options['force_yes'] = True

        projects_db = ProjectsDb(options['projects_db'])

        project_not_started = Project(0, 'not started project',
                                      Project.STATUS_NOT_STARTED)
        project_not_started.backend = 'dummy'
        project_not_started.activities.append(Activity(0, 'activity', 0))
        project_active = Project(1, 'active project', Project.STATUS_ACTIVE)
        project_active.backend = 'dummy'
        project_active.activities.append(Activity(0, 'activity', 0))
        project_finished = Project(2, 'finished project',
                                   Project.STATUS_FINISHED)
        project_finished.backend = 'dummy'
        project_finished.activities.append(Activity(0, 'activity', 0))
        project_cancelled = Project(3, 'cancelled project',
                                    Project.STATUS_CANCELLED)
        project_cancelled.backend = 'dummy'
        project_cancelled.activities.append(Activity(0, 'activity', 0))
        projects_db.update([
            project_not_started, project_active, project_finished,
            project_cancelled
        ])

        self.run_command('clean-aliases', options=options,
                         config_options=config)

        settings = Settings(self.config_file)
        self.assertEqual(settings.get_aliases().keys(), ['alias_active'])
