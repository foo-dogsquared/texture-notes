from datetime import date
from functools import reduce
import logging
from multiprocessing import cpu_count
from os import chdir, getcwd
from os.path import relpath
from shutil import copy, copytree, rmtree
from platform import system
from queue import Queue
import queue
import sqlite3
from string import Template
from subprocess import run, Popen, PIPE
from threading import Thread

# custom packages
import scripts.constants as constants
import scripts.exceptions as exceptions
from .helper import kebab_case, init_db, use_db, regex_match, deduplicate_list
from .manager import *


def print_to_console_and_log(msg, logging_level=logging.INFO):
    logging.log(level=logging_level, msg=msg)
    print(msg)


def add_note(note_metalist=None, subject_metalist=None, force=False, strict=False, **kwargs):
    """Add a subject or a note in the binder.

    :param note_metalist: A list that consists of lists with the subject as the first item and then the notes
                          as the second item and beyond.
    :type note_metalist: list[list][str]

    :param subject_metalist: A multidimensional list of subjects to be added.
    :type subject_metalist: list[list][str]

    :param force: Forces overwrite of notes that has been found to already exist. Turned off by default.
    :type force: bool

    :param strict: Exits at the first time it encounters an error (like an already existing note or a wrong type of
                   file for the specified filepath. Turned off by default.
    :type strict: bool
    :return: None
    """
    metadata = kwargs.get("metadata", None)

    if subject_metalist is not None:
        subject_set = reduce(lambda _set, subject_list: _set | set(subject_list), subject_metalist, set())

        for subject in subject_set:
            try:
                create_subject(subject, metadata=metadata)

                success_msg = f"Subject '{subject}' added in the binder."
                print_to_console_and_log(success_msg)
            except exceptions.SubjectAlreadyExists:
                print_to_console_and_log(f"Subject '{subject}' already exists.", logging.ERROR)
            except ValueError:
                print_to_console_and_log(f"Given subject name '{subject}' is invalid.", logging.ERROR)
        print()

    if note_metalist is not None:
        for subject_note_list in note_metalist:
            subject = subject_note_list[0]
            notes = subject_note_list[1:]

            print_to_console_and_log(f"Creating notes for subject '{subject}':")

            for note in notes:
                try:
                    create_subject_note(subject, note, metadata=metadata)
                    print_to_console_and_log(f"Note '{note}' under subject '{subject}' added in the binder.")
                except exceptions.NoSubjectFoundError:
                    print_to_console_and_log(f"Subject '{subject}' is not found in the binder. Moving on...",
                                             logging.ERROR)
                    break
                except exceptions.DanglingSubjectError:
                    print_to_console_and_log(f"Subject '{subject}' is in the binder but its files are missing. " \
                                             f"Deleting the subject entry in the binder.", logging.ERROR)
                    break
                except exceptions.SubjectNoteAlreadyExistError:
                    print_to_console_and_log(f"Note with the title '{note}' under subject '{subject}' "
                                             f"already exists in the binder.", logging.ERROR)
                except ValueError:
                    print_to_console_and_log(f"Note title '{note}' is invalid.", logging.ERROR)
            print()


def remove_note(note_metalist=None, subject_metalist=None, delete=False, **kwargs):
    """Removes a subject or a note from the binder.

    :param note_metalist: A multidimensional list of notes with the subject as the first item and
                          the title of the notes to be removed as the last.
    :type note_metalist: list[list]

    :param subject_metalist: A multidimensional list of subjects to be deleted.
    :type subject_metalist: list[list]

    :param delete: Delete the files on disk.
    :type delete: bool

    :return: An integer of 0 for success and non-zero for failure.
    """
    db = kwargs.get("db", None)
    metadata = kwargs.get("metadata")

    if delete:
        print_to_console_and_log("Deleting associated folders/files is enabled.\n")

    if subject_metalist is not None:
        subject_set = reduce(lambda _set, subject_list: _set | set(subject_list), subject_metalist, set())

        if ":all:" in subject_set:
            remove_all_subjects(delete, metadata=metadata)
            print_to_console_and_log("All subjects (and its notes) have been removed in the binder.")
            return

        for subject in subject_set:
            try:
                remove_subject(subject, delete, metadata=metadata)
                print_to_console_and_log(f"Subject '{subject}' has been removed from the binder.")
            except exceptions.NoSubjectFoundError:
                print_to_console_and_log(f"Subject '{subject}' doesn't exist in the database.", logging.ERROR)

        print()

    if note_metalist is not None:
        for subject_note_list in note_metalist:
            subject = subject_note_list[0]
            notes = subject_note_list[1:]

            print_to_console_and_log(f"Removing notes under subject '{subject}':")

            if ":all:" in notes:
                try:
                    remove_all_subject_notes(subject, delete, metadata=metadata)
                    print_to_console_and_log(f"All notes under '{subject}' have been removed from the binder.")
                except exceptions.NoSubjectFoundError:
                    print_to_console_and_log(f"Subject '{subject}' is not found in the database. Moving on...",
                                             logging.ERROR)
                except exceptions.DanglingSubjectError:
                    print_to_console_and_log(f"Subject '{subject}' is not found in the filesystem. Moving on...",
                                             logging.ERROR)
            else:
                for note in notes:
                    try:
                        remove_subject_note(subject, note, delete_on_disk=delete, metadata=metadata)
                        print_to_console_and_log(f"Note '{note}' under subject '{subject}' has been removed from the"
                                                 f"binder.")
                    except exceptions.NoSubjectFoundError:
                        print_to_console_and_log(f"Subject '{subject}' is not found in the database. Moving on...",
                                                 logging.ERROR)
                        break
                    except exceptions.DanglingSubjectError:
                        print_to_console_and_log(f"Subject '{subject}' is not found in the filesytem. Moving on...",
                                                 logging.ERROR)
                        break
                    except exceptions.NoSubjectNoteFoundError:
                        print_to_console_and_log(f"Note with the title '{note}' under subject '{subject}' "
                                                 f"does not exist in the binder.", logging.ERROR)
                    except exceptions.DanglingSubjectNoteFoundError:
                        print_to_console_and_log(f"Note with the title '{note}' under subject '{subject}' has its"
                                                 f"file missing. Deleting it in the binder.", logging.ERROR)
            print()

    return 0


# this serves as an environment for note compilation
class TempCompilingDirectory:
    def __init__(self, metadata=None):
        """
        Creates a temporary compilation environment. For now in order to build the compilation environment, the
        program simply copies the needed directories to the compilation environment.

        The compilation takes place in the temporary directory (constants.TEMP_DIRECTORY) assigned by the
        user.
        """
        # copy every main files to be copied in the temp dir
        self.metadata = metadata
        self.output_directory = metadata["profile"] / ".output"

        self.output_directory.mkdir(exist_ok=True)

        self.subjects = []

    def add_subject(self, subject, *notes):
        """
        Adds a subject to be noted within the compilation environment by adding it into the internal subject list and
        copy the appropriate directory into the temporary folder. It also adds an additional

        :param subject: The subject to be added. Take note that the subject data should contain the results from the
                        `get_subject()` function.
        :type subject: dict

        :param notes: A list of notes to be compiled. Take note that the notes data should come from the
                      `get_subject_notes()` (or similar function)

        :return: It's a void function.
        :rtype: None
        """
        try:
            subject = get_subject(subject, delete_in_db=True, metadata=self.metadata)
        except (exceptions.NoSubjectFoundError, exceptions.DanglingSubjectError) as error:
            raise error

        notes = deduplicate_list(notes)
        try:
            notes.remove(":main:")
            main = True
        except ValueError:
            main = False

        if ":all:" in notes:
            notes_query = get_all_subject_notes(subject["name"], metadata=self.metadata)[0]
        else:
            notes_query = []
            for note in notes:
                notes_query.append(get_subject_note(subject["name"], note))

        if main is True:
            create_main_note(subject["name"], metadata=self.metadata)

        subject["notes"] = notes_query
        subject["main"] = main
        self.subjects.append(subject)

    def compile_notes(self, output_directory=None):
        """
        Simply compiles the notes with the added subject notes.

        :param output_directory: The directory where the files of the notes will be sent.
        :type output_directory: Path

        :return: Has no return value
        :rtype: None
        """
        owd = getcwd()
        for subject in self.subjects:
            subject_output_directory = self.output_directory / subject['slug']

            print_to_console_and_log(f"Compiling notes under '{subject['name']}'. " \
                f"Output location is at {subject_output_directory.resolve()}.")

            subject_note_compile_queue = Queue()

            if subject["main"]:
                chdir(subject["path"].resolve())
                latex_compilation_process = Popen(["latexmk", constants.MAIN_SUBJECT_TEX_FILENAME, "-shell-escape",
                                                   "-pdf"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
                latex_cleanup_process = Popen(["latexmk", "-c", constants.MAIN_SUBJECT_TEX_FILENAME], stdin=PIPE, stdout=PIPE, stderr=PIPE)
                latex_compilation_process.communicate()
                latex_cleanup_process.communicate()
                chdir(owd)
                if latex_compilation_process.returncode is not 0:
                    print_to_console_and_log(f"Main note of subject '{subject['name']}' has failed to compile.")
                    copy(subject["path"] / "main.log", subject_output_directory)
                else:
                    print_to_console_and_log(f"Main note of subject '{subject['name']}' has been compiled")
                    copy(subject["path"] / "main.pdf", subject_output_directory)

            chdir(subject["path"].resolve())

            for note in subject["notes"]:
                latex_compilation_processes = Popen(["latexmk", note["path"].name, "-shell-escape", "-pdf"],
                                                     stdin=PIPE, stdout=PIPE, stderr=PIPE)

                subject_note_compile_queue.put((latex_compilation_processes, note))

            available_threads = cpu_count()

            for _thread in range(0, available_threads):
                thread = Thread(target=self._compile, args=(subject, subject_note_compile_queue, output_directory, owd))
                thread.daemon = True
                thread.start()

            subject_note_compile_queue.join()

            print()

    def _compile(self, subject, subject_note_compile_queue, output_directory, original_working_directory):
        """
        Continuously compile notes from a subject notes task queue where it contains both the note information and the
        compile command to be executed. Once the task queue is empty, that's where it will break out.

        :param subject: The subject of the note to be compiled.
        :type subject: dict

        :param subject_note_compile_queue: The task queue.
        :type subject_note_compile_queue: Queue

        :param output_directory: The output directory where the compiled file(s) will be sent.
        :type output_directory: Path

        :param original_working_directory: The original working directory of the process. This is needed in order to
                                           copy the files correctly.
        :type original_working_directory: Path

        :return: Has no return value.
        :rtype: None
        """
        while True:
            try:
                command_metadata = subject_note_compile_queue.get()
            except queue.Empty:
                break

            latex_compilation_process = command_metadata[0]
            note = command_metadata[1]

            logging.info(f"Compilation process of note '{note['title']}' has started...")
            latex_compilation_process.communicate()

            compile_cleanup_command = Popen(["latexmk", "-c" , f"{note['path'].name}"], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            compile_cleanup_command.communicate()
            if compile_cleanup_command.returncode is not 0:
                compile_cleanup_msg = f"Cleanup of '{note['path'].name}' has failed. Please delete it manually (or try the command \"latexmk -c {note['path'].name}\" again.)"
            else:
                compile_cleanup_msg = f"Cleanup of '{note['path'].name}' has been successful."

            logging.info(compile_cleanup_msg)
            print(compile_cleanup_msg)

            chdir(original_working_directory)
            note_output_filepath = self.output_directory / subject["path"].stem
            note_output_filepath.mkdir(exist_ok=True)

            subject_note_log_filename = note['path'].stem + ".log"
            subject_note_log = subject["path"] / subject_note_log_filename

            compiled_pdf_filename = note['path'].stem + ".pdf"
            compiled_pdf = subject["path"] / compiled_pdf_filename

            if latex_compilation_process.returncode is not 0:
                logging.error(f"Compilation process of note '{note['title']}' has failed. No PDF has been produced.")
                print(f"Note '{note['title']}' not being able to compile. Check the resulting log for errors.")
                compiled_pdf_output = note_output_filepath / compiled_pdf_filename
                if compiled_pdf_output.exists():
                    compiled_pdf_output.unlink()

                copy(subject_note_log, note_output_filepath)
                subject_note_compile_queue.task_done()
                continue

            compile_success_msg = f"Successfully compiled note '{note['title']}' into PDF."
            logging.info(compile_success_msg)
            print(compile_success_msg)
            
            subject_note_output_log = note_output_filepath / subject_note_log_filename
            if subject_note_output_log.exists():
                subject_note_output_log.unlink()

            copy(compiled_pdf, note_output_filepath)

            subject_note_compile_queue.task_done()
            continue


def compile_note(note_metalist, cache=False, **kwargs):
    metadata = kwargs.pop("metadata")
    temp_compile_dir = TempCompilingDirectory(metadata=metadata)

    for subject_note_list in note_metalist:
        subject = subject_note_list[0]
        notes = subject_note_list[1:]

        temp_compile_dir.add_subject(subject, *notes)

    temp_compile_dir.compile_notes()


def list_note(subjects, **kwargs):
    """
    Simply prints out a list of notes of a subject.
    :param subjects: A list of string of subjects to be searched for.
    :type subjects: list[str]

    :return:
    """

    profile_metadata = kwargs.pop("metadata")

    if ":all:" in subjects:
        subjects_query = get_all_subjects(sort_by="name", metadata=profile_metadata)[0]
    else:
        subjects_query = []
        for subject in subjects:
            subject_query = get_subject(subject, metadata=profile_metadata)

            if subject_query is None:
                continue

            subjects_query.append(subject_query)

    if len(subjects_query) == 0:
        print_to_console_and_log("There's no subjects listed in the database.")
        return None

    sort_by = kwargs.get("sort", "title")
    for subject in subjects_query:
        subject_notes_query = get_all_subject_notes(subject["name"], sort_by=sort_by, metadata=profile_metadata)[0]
        note_count = len(subject_notes_query)

        print_to_console_and_log(f"Subject \"{subject['name']}\" has "
                                 f"{note_count} {'notes' if note_count > 1 else 'note'}.")

        for note in subject_notes_query:
            logging.info(f"Subject '{subject['name']}': {note['title']}")
            print(f"  - ({note['id']}) {note['title']}")
        print()
    exit(0)


def open_note(note, **kwargs):
    """Simply opens a single note in the default text editor.

    :param note: A string of integer that represents a note ID.
    :type note: str

    :param kwargs: Keyword arguments for options.
    :keyword execute: A command string that serves as a replacement for opening the note, if given any. The title
                      of the note must be referred with '{note}'.

    :return: An integer of 0 for success and non-zero for failure.
    :rtype: int
    """
    metadata = kwargs.pop("metadata")
    
    try:
        note_query = get_subject_note_by_id(note, metadata=metadata)
    except exceptions.NoSubjectFoundError as error:
        print("No subject ")

    note_absolute_filepath = note_query["path"].absolute().__str__()

    execute_cmd = kwargs.pop("execute", None)
    if execute_cmd is not None:
        note_editor_instance = run(execute_cmd.format(note=note_absolute_filepath).split())
    else:
        note_editor_instance = run([constants.config["DEFAULT_NOTE_EDITOR"], note_absolute_filepath])

    if note_editor_instance.returncode is True:
        logging.info("Text editor has been opened.")
        exit(0)
    else:
        exit(1)
