# native packages
from argparse import ArgumentParser, HelpFormatter
import logging
from pathlib import Path
import sys

# custom packages
import scripts.constants as constants
from .exceptions import ProfileAlreadyExistsError
from .helper import import_config
from .manager import create_profile, get_profile
from .interface import add_note, remove_note, compile_note, open_note, list_note


# Making between each option to have a newline for easier reading
# https://stackoverflow.com/q/29484443
class BlankLinesHelpFormatter(HelpFormatter):
    def _split_lines(self, text, width):
        return super()._split_lines(text, width) + ['']


def cli(arguments):
    argument_parser = ArgumentParser(description="A simple LaTeX notes manager "
                                                 "specifically created for my workflow.",
                                     prog=constants.SHORT_NAME,
                                     formatter_class=BlankLinesHelpFormatter)
    argument_parser.add_argument("--target", "-t", action="store", help="The notes directory target path.", default=constants.CURRENT_DIRECTORY)
    argument_parser.add_argument("--config", "-c", action="store", help="The config target path.", default=constants.CURRENT_DIRECTORY / "config.py")

    # add the parsers for the subcommands
    subparsers = argument_parser.add_subparsers(title="subcommands", dest=constants.SUBCOMMAND_ATTRIBUTE_NAME,
                                                help="You can append a help option (-h) for each subcommand "
                                                     "to see their arguments and available options.")

    # add the subcommand 'get'
    list_note_parser = subparsers.add_parser("list", formatter_class=BlankLinesHelpFormatter,
                                             help="Get a list of notes/subjects from the database.")
    list_note_parser.add_argument("subjects", nargs="*", type=str, metavar=("SUBJECT"), default=":all:",
                                  help="An array of subjects delimited by whitespace to list its notes in the "
                                       "database. You can list all of the subjects and their notes by providing "
                                       "one of the arguments to be \":all:\".")
    list_note_parser.add_argument("--sort", type=str, metavar="TYPE", default="title",
                                  help="Gives the result in a specified order. Can only accept limited keywords. Such "
                                       "keywords include \"title\", \"id\", and \"date\". By default, it lists the "
                                       "notes by title.")
    list_note_parser.set_defaults(subcmd_func=list_note, subcmd_parser=list_note_parser)

    # add the subcommand 'add'
    add_note_parser = subparsers.add_parser("add", formatter_class=BlankLinesHelpFormatter,
                                            help="Add a note/subject in the appropriate location "
                                                 "at the notes directory.")
    add_note_parser.add_argument("--note", "-n", action="append", nargs="+", type=str,
                                 metavar=("SUBJECT", "TITLE"), dest=constants.NOTE_ATTRIBUTE_NAME,
                                 help="Takes a subject as the first argument "
                                      "then the title of the note(s) to be added. \n\n"
                                      "This option can also be passed multiple times in one command query.")
    add_note_parser.add_argument("--subject", "-s", action="append", nargs="*", type=str,
                                 metavar=("SUBJECT"),
                                 dest=constants.SUBJECT_ATTRIBUTE_NAME,
                                 help="Takes a list of subjects to be added into the notes directory.")
    add_note_parser.add_argument("--force", action="store_true", help="Force to write the file if the note exists "
                                                                      "in the filesystem.")
    add_note_parser.set_defaults(subcmd_func=add_note, subcmd_parser=add_note_parser)

    # add the subcommand 'remove'
    remove_note_parser = subparsers.add_parser("remove", aliases=["rm"],
                                               formatter_class=BlankLinesHelpFormatter,
                                               help="Remove a subject/note from the binder.")
    remove_note_parser.add_argument("--note", "-n", action="append", nargs="+", type=str,
                                    metavar=("SUBJECT", "TITLE"), dest=constants.NOTE_ATTRIBUTE_NAME,
                                    help="Takes a subject as the first argument and the title of the note(s) "
                                         "to be deleted as the rest. You can delete all of the notes on a "
                                         "subject by providing one of the argument as ':all:'. "
                                         "This option can also be passed multiple times in one command query.")
    remove_note_parser.add_argument("--subject", "-s", action="append", nargs="*", type=str,
                                    metavar=("SUBJECT"), dest=constants.SUBJECT_ATTRIBUTE_NAME,
                                    help="Takes a list of subjects to be removed into the binder database.")
    remove_note_parser.add_argument("--delete", action="store_true", help="Delete the files on disk.")

    remove_note_parser.set_defaults(subcmd_func=remove_note, subcmd_parser=remove_note_parser)

    # add the subcommand 'compile'
    compile_note_parser = subparsers.add_parser("compile", aliases=["make"], formatter_class=BlankLinesHelpFormatter,
                                                help="Compile specified notes from a subject or a variety of them.")
    compile_note_parser.add_argument("--note", "-n", action="append", nargs="+", type=str,
                                     metavar=("SUBJECT", "TITLE"), dest=constants.NOTE_ATTRIBUTE_NAME,
                                     help="Takes a subject as the first argument then the title of the note(s) "
                                          "to be compiled which can vary in count. "
                                          "You can compile all of the notes by providing the argument ':all:' as the "
                                          "first argument (i.e., '--note :all:'). "
                                          "You can compile all of the notes under a subject by providing ':all:' as "
                                          "the second argument (i.e., '--note <SUBJECT_NAME> :all:'). "
                                          "This option can also be passed multiple times in one command query.")
    compile_note_parser.add_argument("--cache", action="store_true",
                                     help=f"Specifies if the build directory "
                                     f"(DEFAULT: {constants.TEMP_DIRECTORY_NAME}) should be kept after compilation "
                                     f"process has completed. This will help out in speeding up compilation time "
                                     f"especially if you're going to compile continuously.")

    compile_note_parser.set_defaults(subcmd_func=compile_note, subcmd_parser=compile_note_parser)

    # add the subcommand 'open'
    open_note_parser = subparsers.add_parser("open", formatter_class=BlankLinesHelpFormatter,
                                             help="Open up specified note with the default/configured text editor.")
    open_note_parser.add_argument("note", type=str, action="store",
                                  help="Takes a note ID of the note to be opened with "
                                       "the default/configured editor. Only accepts one note to be opened.")
    open_note_parser.add_argument("--execute", type=str, metavar=("COMMAND"),
                                  help=f"Replace the default text editor ({constants.config['DEFAULT_NOTE_EDITOR']}) with the "
                                  "given command. You have to indicate the note with \"{note}\" "
                                  "(i.e. \"code {note}\").")

    open_note_parser.set_defaults(subcmd_func=open_note, subcmd_parser=open_note_parser)

    args = vars(argument_parser.parse_args())
    passed_subcommand = args.pop(constants.SUBCOMMAND_ATTRIBUTE_NAME, None)
    if passed_subcommand is None or len(arguments) == 1:
        argument_parser.print_help()
        sys.exit(0)

    if passed_subcommand is not None:
        note_function = args.pop("subcmd_func", None)

        passed_subcommand_parser = args.pop("subcmd_parser", None)

        # Printing the help message if there's no value added
        if len(arguments) == 2:
            passed_subcommand_parser.print_help()
            sys.exit(0)

        # setting up the logger for the file
        logging.basicConfig(filename=constants.SHORT_NAME + ".log", filemode="w", level=logging.INFO,
                            format="%(levelname)s (%(asctime)s):\n%(message)s\n")
        logging.info("Subcommand: {subcmd}".format(subcmd=passed_subcommand))

        location = Path(args.pop("target", constants.CURRENT_DIRECTORY))
        profile_directory = location / constants.PROFILE_DIRECTORY_NAME
        notes_directory = profile_directory / "notes"

        config = args.pop("config", None)
        if config is not None:
            config = Path(config)

            if config.exists():
                user_config = import_config("config", config).config
                constants.config.update(user_config)

        if profile_directory.exists():
            profile_metadata = get_profile(location)
        else:
            profile_metadata = create_profile(location)

        note_function(**args, metadata=profile_metadata)
        profile_metadata["db"].close()
