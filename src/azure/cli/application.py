import argparse
import logging
from .parser import AzCliCommandParser
import argcomplete
import logging
from ._event_dispatcher import EventDispatcher
import azure.cli.extensions

class Session(EventDispatcher):
    """The session object tracks session specific data such
    as output formats, log settings as well as providing an
    event dispatch mechanism that allows us to make modifications
    during the execution of a command
    """
    def __init__(self):
        super(Session, self).__init__()
        self.log = logging.getLogger('az')
        self.output_format = 'list'

class Application(object):

    def __init__(self, session=None):
        self.session = session or Session()

        # Register presence of and handlers for global parameters
        self.session.register('GlobalParser.Created', self._register_builtin_arguments)
        self.session.register('CommandParser.Parsed', self._handle_builtin_arguments)

        # Let other extensions make their presence known
        azure.cli.extensions.register_extensions(self)

        self.global_parser = AzCliCommandParser(prog='az', add_help=False)
        self.session.raise_event('GlobalParser.Created', self.global_parser)

        self.parser = AzCliCommandParser(prog='az', parents=[self.global_parser])
        self.session.raise_event('CommandParser.Created', self.parser)

    def load_commands(self, argv):
        import azure.cli.commands as commands

        # Find the first noun on the command line and only load commands from that
        # module to improve startup time.
        for a in argv:
            if not a.startswith('-'):
                commands.add_to_parser(self.parser, self.session, a)
                break
        else:
            # No noun found, so load all commands.
            commands.add_to_parser(self.parser, self.session)

        self.session.raise_event('CommandParser.Loaded', self.parser)
        argcomplete.autocomplete(self.parser)

    def execute(self, argv):
        args = self.parser.parse_args(argv)
        self.session.raise_event('CommandParser.Parsed', args)

        # Consider - we are using any args that start with an underscore (_) as 'private'
        # arguments and remove them from the arguments that we pass to the actual function.
        # This does not feel quite right.
        params = dict([(key, value)
                       for key, value in args.__dict__.items() if not key.startswith('_')])
        result = args.func(params, {}) # TODO: Unexpected parameters passed in?
        return result

    def _register_builtin_arguments(self, name, parser):
        parser.add_argument('--subscription', dest='_subscription_id', help=argparse.SUPPRESS)
        parser.add_argument('--output', '-o', dest='_output_format', choices=['list', 'json'])

    def _handle_builtin_arguments(self, name, args):
        try:
            self.session.output_format = args._output_format #pylint: disable=protected-access
            del args._output_format
        except Exception:
            pass
